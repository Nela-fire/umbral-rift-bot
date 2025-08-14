# main.py
import os
import json
import pytz
import random
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands
from icalendar import Calendar
from keep_alive import keep_alive
from discord.app_commands import BucketType
from discord.app_commands.checks import cooldown as slash_cooldown

# --- ENV / stałe ---
TOKEN = str(os.getenv("DISCORD_BOT_TOKEN") or "")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID") or 0)
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID") or 0)
R5_ROLE_ID = 1380924100742217748
R4_ROLE_ID = 1380924200985956353

# --- rifts load/save ---
def load_rifts():
    if os.path.exists("rifts.json"):
        with open("rifts.json", "r") as f:
            return json.load(f)
    else:
        return [
            "2025-07-30 08:00",
            "2025-08-01 20:00", "2025-08-03 08:00", "2025-08-05 20:00", "2025-08-07 08:00",
            "2025-08-09 20:00", "2025-08-11 08:00", "2025-08-13 20:00", "2025-08-15 08:00",
            "2025-08-17 20:00", "2025-08-19 08:00", "2025-08-21 20:00", "2025-08-23 08:00",
            "2025-08-25 20:00", "2025-08-27 08:00", "2025-08-29 20:00", "2025-08-31 08:00"
        ]

def save_rifts():
    with open("rifts.json", "w") as f:
        json.dump(rifts, f, indent=4)

# --- discord client ---
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)
tree = client.tree

rifts = load_rifts()
scheduled_tasks: dict[str, list[asyncio.Task]] = {}

# --- pomocnicze ---
def utc_parse(s: str) -> datetime.datetime:
    return pytz.utc.localize(datetime.datetime.strptime(s, "%Y-%m-%d %H:%M"))

def ts(dt: datetime.datetime) -> int:
    return int(dt.timestamp())

# --- cache kanałów, kolejka wysyłek, guard on_ready ---
_channel_cache: dict[int, discord.TextChannel] = {}
SEND_Q: asyncio.Queue = asyncio.Queue()
_started = False  # żeby nie dublować harmonogramu po reconnect

async def get_text_channel(ch_id: int) -> discord.TextChannel | None:
    if ch_id in _channel_cache:
        return _channel_cache[ch_id]
    ch = client.get_channel(ch_id)
    if isinstance(ch, discord.TextChannel):
        _channel_cache[ch_id] = ch
        return ch
    try:
        ch = await client.fetch_channel(ch_id)
        if isinstance(ch, discord.TextChannel):
            _channel_cache[ch_id] = ch
            return ch
    except Exception:
        return None
    return None

async def sender_loop():
    """Wysyłki przez kolejkę (~4 req/s) + retry po 429."""
    while True:
        func, args, kwargs = await SEND_Q.get()
        try:
            await func(*args, **kwargs)
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                await asyncio.sleep(5)
                try:
                    await func(*args, **kwargs)
                except Exception:
                    pass
        await asyncio.sleep(0.25)  # ~4/s

async def send_safe_message(channel: discord.abc.Messageable, *args, **kwargs):
    await SEND_Q.put((channel.send, args, kwargs))

async def respond_safe(interaction: discord.Interaction, content=None, *, embed=None, ephemeral=True):
    """Bezpieczna odpowiedź slash: defer + followup przez kolejkę (redukuje 429)."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
        async def _send_followup():
            await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        await SEND_Q.put((_send_followup, tuple(), {}))
    except discord.HTTPException:
        pass

# --- schedulery riftów ---
async def schedule_reminder(remind_time: datetime.datetime, rift_time: datetime.datetime, delta: int):
    await discord.utils.sleep_until(remind_time)
    channel = await get_text_channel(CHANNEL_ID)
    if not channel:
        return

    motivational = [
        "🔥 Let’s crush this Rift together!",
        "⚔️ Gear up, team — victory awaits!",
        "🚀 Push your limits. This is our moment!",
        "💥 Be legendary — show up and fight!",
        "🌟 Every Rift is a chance to shine. Let’s go!",
        "🏆 Together we conquer — don’t miss it!",
        "🛡️ This is what we trained for!",
        "🎯 Focus up! It’s Rift time soon!",
    ]
    templates = [
        (
            f"<@&{ROLE_ID}> 🌀 **Brace yourselves!**\n"
            f"⏰ Rift begins in **{int(delta/60)} minutes**\n"
            f"🕒 <t:{ts(rift_time)}:R> | <t:{ts(rift_time)}:t> UTC\n"
            f"{random.choice(motivational)}"
        ),
        (
            f"<@&{ROLE_ID}> ⚔️ **Prepare for battle!**\n"
            f"🕰️ Only **{int(delta/60)} minutes** to go!\n"
            f"📆 <t:{ts(rift_time)}:F>\n"
            f"{random.choice(motivational)}"
        ),
        (
            f"<@&{ROLE_ID}> 🛡️ **Incoming Rift alert!**\n"
            f"💣 Rift starts in **{int(delta/60)} minutes**\n"
            f"⏳ <t:{ts(rift_time)}:R>\n"
            f"{random.choice(motivational)}"
        ),
        (
            f"<@&{ROLE_ID}> ⚡ **War horns sound!**\n"
            f"📢 The Rift erupts in **{int(delta/60)} minutes**!\n"
            f"🕒 <t:{ts(rift_time)}:R> (UTC)\n"
            f"{random.choice(motivational)}"
        ),
    ]
    style_index = (ts(rift_time) + delta) % len(templates)
    await send_safe_message(channel, templates[style_index])

    # sprzątanie tasków
    rift_str = rift_time.strftime("%Y-%m-%d %H:%M")
    tasks = scheduled_tasks.get(rift_str, [])
    current_task = asyncio.current_task()
    if current_task in tasks:
        tasks.remove(current_task)
    if not tasks:
        scheduled_tasks.pop(rift_str, None)

async def schedule_all_rifts():
    scheduled_tasks.clear()
    now = datetime.datetime.now(pytz.utc)
    for rift_time_str in rifts:
        rift_time = utc_parse(rift_time_str)
        for delta in [3600, 1800, 900, 300]:
            remind_time = rift_time - datetime.timedelta(seconds=delta)
            if remind_time > now:
                t = asyncio.create_task(schedule_reminder(remind_time, rift_time, delta))
                scheduled_tasks.setdefault(rift_time_str, []).append(t)

# --- events ---
@client.event
async def on_ready():
    global _started
    print(f"✅ Bot is online as {client.user}")
    if not _started:
        _started = True
        client.loop.create_task(sender_loop())
        try:
            await tree.sync()  # raz, nie przy każdym reconnect
        except Exception:
            pass
        try:
            await schedule_all_rifts()
        except Exception as e:
            print(f"[schedule_all_rifts] error: {e}")

# --- komendy (z cooldownami i respond_safe) ---

@tree.command(name="nextrift", description="Show the next Rift event")
@cooldown(1, 3, key=BucketType.user)
async def nextrift(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    for rift_time_str in rifts:
        rift_time = utc_parse(rift_time_str)
        if rift_time > now:
            await respond_safe(
                interaction,
                f"🌀 The next Rift is <t:{ts(rift_time)}:F>\n⏳ <t:{ts(rift_time)}:R>",
                ephemeral=True
            )
            return
    await respond_safe(interaction, "No upcoming Rift found.", ephemeral=True)

@tree.command(name="weeklyrifts", description="Show all Rifts in the next 7 days")
@cooldown(1, 5, key=BucketType.user)
async def weeklyrifts(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    one_week = now + datetime.timedelta(days=7)
    upcoming = []
    for rift_time_str in rifts:
        rift_time = utc_parse(rift_time_str)
        if now <= rift_time <= one_week:
            upcoming.append(f"<t:{ts(rift_time)}:F>")
    if upcoming:
        await respond_safe(interaction, "📅 Rifts this week:\n" + "\n".join(upcoming), ephemeral=True)
    else:
        await respond_safe(interaction, "No Rifts scheduled for the next 7 days.", ephemeral=True)

@tree.command(name="lastrift", description="Show the last Rift from the schedule")
@cooldown(1, 3, key=BucketType.user)
async def lastrift(interaction: discord.Interaction):
    rift_time = utc_parse(rifts[-1])
    await respond_safe(interaction, f"📌 Last Rift in the schedule:\n<t:{ts(rift_time)}:F>", ephemeral=True)

@tree.command(name="timeleft", description="Show time left until next Rift")
@cooldown(1, 5, key=BucketType.user)
async def timeleft(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    for rift_time_str in rifts:
        rift_time = utc_parse(rift_time_str)
        if rift_time > now:
            delta = rift_time - now
            total = int(delta.total_seconds())
            hours, remainder = divmod(total, 3600)
            minutes = remainder // 60
            await respond_safe(interaction, f"⏰ Time left until next Rift: **{hours}h {minutes}m**", ephemeral=True)
            return
    await respond_safe(interaction, "No upcoming Rift found.", ephemeral=True)

@tree.command(name="mytime", description="Show your local time and UTC")
@cooldown(1, 5, key=BucketType.user)
async def mytime(interaction: discord.Interaction):
    now = datetime.datetime.now()
    utc_now = datetime.datetime.utcnow()
    await respond_safe(
        interaction,
        f"🕓 Your local time: **{now.strftime('%H:%M')}**\n🌍 UTC time: **{utc_now.strftime('%H:%M')}**",
        ephemeral=True
    )

@tree.command(name="help", description="Show all commands and bot details")
@cooldown(1, 5, key=BucketType.user)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Umbral Rift Bot — your silent Rift assistant",
        description=(
            "Never miss another Rift again. This bot watches the clock so you don’t have to.\n"
            "It quietly tracks all Umbral Rift events and gives you timely reminders — in your own timezone.\n\n"
            "**✨ What it does:**\n"
            "• Sends reminders: 1h / 30min / 15min / 5min before each Rift\n"
            "• Adjusts all times to your local timezone\n"
            "• Lets you check upcoming events with simple commands\n\n"
            "**📘 Commands:**\n"
            "`/nextrift` — Shows the next Rift (local time)\n"
            "`/weeklyrifts` — Rifts in the next 7 days\n"
            "`/lastrift` — Date & time of the last scheduled Rift\n"
            "`/timeleft` — Countdown to the next Rift (e.g. “2h 7m”)\n"
            "`/mytime` — Your local time + UTC\n"
            "`/help` — Shows this help message\n\n"
            "**🔔 Want to be notified?**\n"
            "Make sure you have the correct role to receive Rift reminders.\n"
            "You can grab the role in <#1385418864330014771>."
        ),
        color=0x5865F2
    )
    embed.set_footer(text="Let the Rift chaos begin 🔥")
    await respond_safe(interaction, embed=embed, ephemeral=True)

@tree.command(name="uploadics", description="Upload a .ics file to add new Rift events")
@app_commands.checks.has_any_role(R5_ROLE_ID, R4_ROLE_ID)
@cooldown(1, 10, key=BucketType.user)
async def uploadics(interaction: discord.Interaction, attachment: discord.Attachment):
    if not attachment.filename.endswith(".ics"):
        await respond_safe(interaction, "Please upload a valid .ics file.", ephemeral=True)
        return

    content = await attachment.read()
    try:
        cal = Calendar.from_ical(content)
        new_rifts = []
        for component in cal.walk():
            if component.name == "VEVENT":
                dtstart = component.get("dtstart").dt
                if isinstance(dtstart, datetime.datetime):
                    dtstart_utc = dtstart.astimezone(pytz.utc)
                    new_rifts.append(dtstart_utc.strftime("%Y-%m-%d %H:%M"))

        if new_rifts:
            global rifts
            old_count = len(rifts)
            rifts_set = set(rifts)
            rifts_set.update(new_rifts)
            rifts = sorted(rifts_set)
            save_rifts()

            await respond_safe(
                interaction,
                f"✅ Rift schedule updated. Added {len(rifts) - old_count} new events (now total {len(rifts)}).",
                ephemeral=True
            )

            channel = await get_text_channel(1398208622567227462)
            if channel:
                update_message = (
                    f"📢 **Rift schedule updated!**\n"
                    f"Uploaded by: {interaction.user.mention}\n"
                    f"Total events: **{len(rifts)}**\n"
                    f"Use `/weeklyrifts` or `/nextrift` to view the updated schedule."
                )
                await send_safe_message(channel, f"<@&{R5_ROLE_ID}> <@&{R4_ROLE_ID}>\n{update_message}")
        else:
            await respond_safe(interaction, "No valid Rift dates found in the file.", ephemeral=True)
    except Exception as e:
        await respond_safe(interaction, f"❌ Failed to parse .ics file: {e}", ephemeral=True)

@uploadics.error
async def uploadics_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await respond_safe(interaction, "You don't have permission to use this command.", ephemeral=True)
    else:
        await respond_safe(interaction, "An error occurred while processing the file.", ephemeral=True)

@tree.command(name="delay_next_rift", description="Shift the next Rift forward/backward by minutes")
@app_commands.describe(minutes="Positive = delay, negative = earlier")
@app_commands.checks.has_any_role(R5_ROLE_ID, R4_ROLE_ID)
@cooldown(1, 10, key=BucketType.user)
async def delay_next_rift(interaction: discord.Interaction, minutes: int):
    now = datetime.datetime.now(pytz.utc)
    for i, rift_time_str in enumerate(rifts):
        rift_time = utc_parse(rift_time_str)
        if rift_time > now:
            old_rift_str = rift_time_str

            # cancel starych tasków
            if old_rift_str in scheduled_tasks:
                for task in scheduled_tasks[old_rift_str]:
                    task.cancel()
                scheduled_tasks.pop(old_rift_str, None)

            new_time = rift_time + datetime.timedelta(minutes=minutes)
            new_rift_str = new_time.strftime("%Y-%m-%d %H:%M")
            rifts[i] = new_rift_str
            save_rifts()

            # zaplanuj nowe przypomnienia
            tasks = []
            for delta in [3600, 1800, 900, 300]:
                remind_time = new_time - datetime.timedelta(seconds=delta)
                if remind_time > now:
                    t = asyncio.create_task(schedule_reminder(remind_time, new_time, delta))
                    tasks.append(t)
            scheduled_tasks[new_rift_str] = tasks

            await respond_safe(
                interaction,
                f"✅ Rift moved to <t:{ts(new_time)}:F> ({minutes:+} min)",
                ephemeral=False
            )
            return

    await respond_safe(interaction, "No upcoming Rift found.", ephemeral=True)

@delay_next_rift.error
async def delay_next_rift_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await respond_safe(interaction, "You don't have permission to use this command.", ephemeral=True)
    else:
        await respond_safe(interaction, "An error occurred while trying to delay the Rift.", ephemeral=True)

# --- start ---
keep_alive()      # lekki endpoint /health i /
client.run(TOKEN) # BEZ while True – discord.py sam reconnectuje

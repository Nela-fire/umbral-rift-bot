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

# --- ENV / constants ---
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

# --- helper functions ---
def utc_parse(s: str) -> datetime.datetime:
    return pytz.utc.localize(datetime.datetime.strptime(s, "%Y-%m-%d %H:%M"))

def ts(dt: datetime.datetime) -> int:
    return int(dt.timestamp())

# --- channel cache, send queue, guard on_ready ---
_channel_cache: dict[int, discord.TextChannel] = {}
SEND_Q: asyncio.Queue = asyncio.Queue()
_started = False  # prevent duplicate scheduling on reconnect

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
    """Send messages through queue (~4 req/s) + retry on 429."""
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
    """Safe slash response: defer + followup through queue (reduces 429)."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
        async def _send_followup():
            await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        await SEND_Q.put((_send_followup, tuple(), {}))
    except discord.HTTPException:
        pass

# --- rift schedulers ---
async def schedule_reminder(remind_time: datetime.datetime, rift_time: datetime.datetime, delta: int):
    try:
        print(f"🕐 Task created: {int(delta/60)}min reminder for {rift_time.strftime('%Y-%m-%d %H:%M')} will fire at {remind_time.strftime('%H:%M:%S')}")
        await discord.utils.sleep_until(remind_time)
        print(f"🔔 Task woke up: {int(delta/60)}min reminder for {rift_time.strftime('%Y-%m-%d %H:%M')}")
        
        channel = await get_text_channel(CHANNEL_ID)
        if not channel:
            print(f"❌ Channel {CHANNEL_ID} not found for {int(delta/60)}min reminder")
            return

        motivational = [
            # Original lines
            "🔥 Let's crush this Rift together!",
            "⚔️ Gear up, team – victory awaits!",
            "🚀 Push your limits. This is our moment!",
            "💥 Be legendary – show up and fight!",
            "🌟 Every Rift is a chance to shine. Let's go!",
            "🏆 Together we conquer – don't miss it!",
            "🛡️ This is what we trained for!",
            "🎯 Focus up! It's Rift time soon!",
            
            # New battle-ready lines
            "💪 Time to show what we're made of!",
            "⚡ Unleash your power – the Rift calls!",
            "🗡️ Warriors assemble – glory beckons!",
            "💫 Make every moment count. Let's dominate!",
            "🔥 Bring the heat – it's go time!",
            "⭐ Champions rise to the challenge!",
            "🏹 Lock and load – victory is ours!",
            "💢 Maximum effort, maximum rewards!",
            
            # Team spirit lines
            "🤝 Stronger together – let's roll!",
            "✊ United we stand, divided they fall!",
            "🎖️ Squad up! Time to make history!",
            "🤜🤛 One team, one dream – let's get it!",
            "🫂 Rally the troops – we've got this!",
            "👥 Together we're unstoppable!",
            
            # Pump-up lines
            "🌪️ Storm the Rift – leave nothing behind!",
            "🎮 Game face on – it's showtime!",
            "⏰ The moment has arrived. Own it!",
            "🔔 Answer the call – greatness awaits!",
            "🚨 All hands on deck – let's move!",
            "📢 Sound the alarm – Rift warriors needed!",
            
            # Achievement-focused lines
            "🥇 First place has our name on it!",
            "📈 Time to climb those leaderboards!",
            "✨ Write your legend in the Rift!",
            "🎪 The stage is set – steal the show!",
            "🏅 Earn your stripes, claim your glory!",
            "🎊 Make this Rift one to remember!",
            
            # Energy/hype lines
            "🌋 Eruption imminent – get ready to explode!",
            "⚔️ Sharpen your skills – battle approaches!",
            "🎸 Let's rock this Rift!",
            "🔋 Full power! Maximum destruction!",
            "🌊 Ride the wave to victory!",
            "☄️ Impact incoming – brace for greatness!",
            
            # Confidence boosters
            "💯 You've got this – now prove it!",
            "🦁 Roar into battle – show no mercy!",
            "🏰 Defend our honor, seize the throne!",
            "⚓ Hold the line – victory is certain!",
            "🎖️ Heroes are made in moments like these!",
            "🦅 Soar above the rest – claim your destiny!",
        ]
        templates = [
            (
                f"<@&{ROLE_ID}> 🌀 **Brace yourselves!**\n"
                f"⏰ Rift begins in **{int(delta/60)} minutes**\n"
                f"🕐 <t:{ts(rift_time)}:R> | <t:{ts(rift_time)}:t>\n"  # Removed UTC label
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
                f"🕐 <t:{ts(rift_time)}:R>\n"  # Removed (UTC) label
                f"{random.choice(motivational)}"
            ),
        ]
        style_index = (ts(rift_time) + delta) % len(templates)
        
        print(f"💬 Sending {int(delta/60)}min reminder for {rift_time.strftime('%Y-%m-%d %H:%M')}")
        await send_safe_message(channel, templates[style_index])
        print(f"✅ Successfully sent {int(delta/60)}min reminder for {rift_time.strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        print(f"❌ Error in {int(delta/60)}min reminder for {rift_time.strftime('%Y-%m-%d %H:%M')}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always clean up, even if there was an error
        rift_str = rift_time.strftime("%Y-%m-%d %H:%M")
        tasks = scheduled_tasks.get(rift_str, [])
        current_task = asyncio.current_task()
        if current_task in tasks:
            tasks.remove(current_task)
            print(f"🧹 Cleaned up {int(delta/60)}min reminder task for {rift_time.strftime('%Y-%m-%d %H:%M')}")
        if not tasks:
            scheduled_tasks.pop(rift_str, None)

async def schedule_all_rifts():
    # Cancel all existing tasks before clearing
    for rift_str, tasks in scheduled_tasks.items():
        for task in tasks:
            if not task.cancelled():
                task.cancel()
                print(f"🚫 Cancelled old task for {rift_str}")
    
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
            await tree.sync()
            print("✅ Synced slash commands")
        except Exception as e:
            print(f"[tree.sync] error: {e}")
        
        # Schedule tasks only on first start
        try:
            print("🔄 Scheduling rift reminders...")
            await schedule_all_rifts()
            print(f"✅ Scheduled tasks for {len(scheduled_tasks)} rifts")
        except Exception as e:
            print(f"[schedule_all_rifts] error: {e}")
    else:
        # On reconnect, only reschedule if we've lost tasks
        active_task_count = sum(
            len([t for t in tasks if not t.cancelled()]) 
            for tasks in scheduled_tasks.values()
        )
        if active_task_count == 0:
            print("⚠️ No active tasks found on reconnect, rescheduling...")
            await schedule_all_rifts()
            print(f"✅ Rescheduled tasks for {len(scheduled_tasks)} rifts")
        else:
            print(f"📊 Reconnected with {active_task_count} active tasks still running")

# --- commands ---

@tree.command(name="nextrift", description="Show the next Rift event")
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
async def lastrift(interaction: discord.Interaction):
    rift_time = utc_parse(rifts[-1])
    await respond_safe(interaction, f"📌 Last Rift in the schedule:\n<t:{ts(rift_time)}:F>", ephemeral=True)

@tree.command(name="timeleft", description="Show time left until next Rift")
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
async def mytime(interaction: discord.Interaction):
    # Get current time using Discord's timestamp - it will show in user's local timezone
    now_utc = datetime.datetime.now(pytz.utc)
    now_ts = ts(now_utc)
    
    # Create message showing both times using Discord's timestamp formatting
    await respond_safe(
        interaction,
        f"🕐 Current time: <t:{now_ts}:t> (your local)\n"
        f"🌍 UTC time: {now_utc.strftime('%H:%M')} UTC\n"
        f"📅 Full date/time: <t:{now_ts}:F>",
        ephemeral=True
    )

@tree.command(name="help", description="Show all commands and bot details")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Umbral Rift Bot – your silent Rift assistant",
        description=(
            "Never miss another Rift again. This bot watches the clock so you don't have to.\n"
            "It quietly tracks all Umbral Rift events and gives you timely reminders – in your own timezone.\n\n"
            "**✨ What it does:**\n"
            "• Sends reminders: 1h / 30min / 15min / 5min before each Rift\n"
            "• Automatically shows all times in your local timezone\n"
            "• Lets you check upcoming events with simple commands\n\n"
            "**📘 Commands:**\n"
            "`/nextrift` – Shows the next Rift (in your timezone)\n"
            "`/weeklyrifts` – Rifts in the next 7 days\n"
            "`/lastrift` – Date & time of the last scheduled Rift\n"
            "`/timeleft` – Countdown to the next Rift (e.g. '2h 7m')\n"
            "`/mytime` – Shows current time in your timezone and UTC\n"
            "`/help` – Shows this help message\n\n"
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
async def delay_next_rift(interaction: discord.Interaction, minutes: int):
    now = datetime.datetime.now(pytz.utc)
    
    # Find the next rift
    next_rift_index = None
    next_rift_time = None
    for i, rift_time_str in enumerate(rifts):
        rift_time = utc_parse(rift_time_str)
        if rift_time > now:
            next_rift_index = i
            next_rift_time = rift_time
            break
    
    if next_rift_index is None:
        await respond_safe(interaction, "No upcoming Rift found.", ephemeral=True)
        return
    
    old_rift_str = rifts[next_rift_index]
    
    # Cancel old tasks for this specific rift
    if old_rift_str in scheduled_tasks:
        for task in scheduled_tasks[old_rift_str]:
            if not task.cancelled():
                task.cancel()
        # Remove from scheduled_tasks
        del scheduled_tasks[old_rift_str]
        print(f"Cancelled tasks for {old_rift_str}")
    
    # Calculate new time
    new_time = next_rift_time + datetime.timedelta(minutes=minutes)
    new_rift_str = new_time.strftime("%Y-%m-%d %H:%M")
    
    # Check if new time conflicts with existing rifts
    if new_rift_str in rifts and new_rift_str != old_rift_str:
        await respond_safe(
            interaction,
            f"⚠️ Cannot delay - conflicts with existing Rift at <t:{ts(new_time)}:F>",
            ephemeral=True
        )
        # Reschedule the original rift since we cancelled its tasks
        original_time = utc_parse(old_rift_str)
        tasks = []
        for delta in [3600, 1800, 900, 300]:
            remind_time = original_time - datetime.timedelta(seconds=delta)
            if remind_time > now:
                t = asyncio.create_task(schedule_reminder(remind_time, original_time, delta))
                tasks.append(t)
        if tasks:
            scheduled_tasks[old_rift_str] = tasks
        return
    
    # Update the rift time in the list
    rifts[next_rift_index] = new_rift_str
    save_rifts()
    
    # Schedule new reminders for the delayed rift
    tasks = []
    for delta in [3600, 1800, 900, 300]:
        remind_time = new_time - datetime.timedelta(seconds=delta)
        if remind_time > now:
            try:
                t = asyncio.create_task(schedule_reminder(remind_time, new_time, delta))
                tasks.append(t)
            except Exception as e:
                print(f"Error scheduling reminder for {new_rift_str}, delta {delta}: {e}")
    
    if tasks:
        scheduled_tasks[new_rift_str] = tasks
        print(f"Scheduled {len(tasks)} new tasks for {new_rift_str}")
        await respond_safe(
            interaction,
            f"✅ Rift moved from <t:{ts(next_rift_time)}:F> to <t:{ts(new_time)}:F> ({minutes:+} min)\n"
            f"🔔 {len(tasks)} reminders scheduled",
            ephemeral=False
        )
    else:
        await respond_safe(
            interaction,
            f"⚠️ Rift moved to <t:{ts(new_time)}:F> ({minutes:+} min) but no reminders could be scheduled (time may be too close)",
            ephemeral=False
        )

@delay_next_rift.error
async def delay_next_rift_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await respond_safe(interaction, "You don't have permission to use this command.", ephemeral=True)
    else:
        print(f"Error in delay_next_rift: {error}")
        await respond_safe(interaction, "An error occurred while trying to delay the Rift.", ephemeral=True)

@tree.command(name="debug_tasks", description="Show scheduled task status (admin only)")
@app_commands.checks.has_any_role(R5_ROLE_ID, R4_ROLE_ID)
async def debug_tasks(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    
    # Find next rift
    next_rift = None
    for rift_time_str in rifts:
        rift_time = utc_parse(rift_time_str)
        if rift_time > now:
            next_rift = rift_time_str
            break
    
    embed = discord.Embed(title="🔧 Task Debug Info", color=0x5865F2)
    
    # Show next rift
    if next_rift:
        next_time = utc_parse(next_rift)
        embed.add_field(
            name="Next Rift", 
            value=f"<t:{ts(next_time)}:F>\n<t:{ts(next_time)}:R>", 
            inline=False
        )
        
        # Show scheduled tasks for next rift
        if next_rift in scheduled_tasks:
            tasks = scheduled_tasks[next_rift]
            active_tasks = [t for t in tasks if not t.cancelled()]
            cancelled_tasks = [t for t in tasks if t.cancelled()]
            
            embed.add_field(
                name="Scheduled Reminders", 
                value=f"✅ Active: {len(active_tasks)}\n❌ Cancelled: {len(cancelled_tasks)}", 
                inline=True
            )
        else:
            embed.add_field(name="Scheduled Reminders", value="⚠️ No tasks found!", inline=True)
    else:
        embed.add_field(name="Next Rift", value="None found", inline=False)
    
    # Show total scheduled rifts
    total_scheduled = len(scheduled_tasks)
    embed.add_field(name="Total Rifts with Tasks", value=str(total_scheduled), inline=True)
    
    # Show recent rifts (last 3 that have passed)
    recent_rifts = []
    for rift_time_str in reversed(rifts):
        rift_time = utc_parse(rift_time_str)
        if rift_time <= now:
            recent_rifts.append(f"<t:{ts(rift_time)}:R>")
            if len(recent_rifts) >= 3:
                break
    
    if recent_rifts:
        embed.add_field(name="Recent Past Rifts", value="\n".join(recent_rifts), inline=False)
    
    await respond_safe(interaction, embed=embed, ephemeral=True)

@debug_tasks.error
async def debug_tasks_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await respond_safe(interaction, "You don't have permission to use this command.", ephemeral=True)

# --- start ---
keep_alive()      # lightweight endpoint /health and /
client.run(TOKEN) # NO while True - discord.py reconnects automatically

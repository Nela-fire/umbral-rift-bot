import discord
import asyncio
import datetime
import pytz
import os
import random
from discord import app_commands
from discord.ext import commands
from icalendar import Calendar
from keep_alive import keep_alive

TOKEN = str(os.getenv("DISCORD_BOT_TOKEN") or "")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID") or 0)
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID") or 0)
R5_ROLE_ID = 1380924100742217748
R4_ROLE_ID = 1380924200985956353

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)
tree = client.tree

rifts = [
    "2025-07-30 08:00",
    "2025-08-01 20:00", "2025-08-03 08:00", "2025-08-05 20:00", "2025-08-07 08:00",
    "2025-08-09 20:00", "2025-08-11 08:00", "2025-08-13 20:00", "2025-08-15 08:00",
    "2025-08-17 20:00", "2025-08-19 08:00", "2025-08-21 20:00", "2025-08-23 08:00",
    "2025-08-25 20:00", "2025-08-27 08:00", "2025-08-29 20:00", "2025-08-31 08:00"
]

@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")
    await tree.sync()
    now = datetime.datetime.now(pytz.utc)
    for rift_time_str in rifts:
        rift_time = datetime.datetime.strptime(rift_time_str, "%Y-%m-%d %H:%M")
        rift_time = pytz.utc.localize(rift_time)
        for delta in [3600, 1800, 900, 300]:
            remind_time = rift_time - datetime.timedelta(seconds=delta)
            if remind_time > now:
                asyncio.create_task(schedule_reminder(remind_time, rift_time, delta))

async def schedule_reminder(remind_time, rift_time, delta):
    await discord.utils.sleep_until(remind_time)
    channel = await client.fetch_channel(int(CHANNEL_ID))
    if channel:
        motivational = [
            "🔥 Let’s crush this Rift together!",
            "⚔️ Gear up, team — victory awaits!",
            "🚀 Push your limits. This is our moment!",
            "💥 Be legendary — show up and fight!",
            "🌟 Every Rift is a chance to shine. Let’s go!",
            "🏆 Together we conquer — don’t miss it!",
            "🛡️ This is what we trained for!", 
            "🎯 Focus up! It’s Rift time soon!"
        ]
        messages = [
            f"<@&{ROLE_ID}> 🌀 **Brace yourselves!**\n"
            f"⏰ Rift begins in **{int(delta/60)} minutes**\n"
            f"🕒 <t:{int(rift_time.timestamp())}:R> | <t:{int(rift_time.timestamp())}:t> UTC\n"
            f"🔥 Let’s crush this Rift together!",
        
            f"<@&{ROLE_ID}> ⚔️ **Prepare for battle!**\n"
            f"🕰️ Only **{int(delta/60)} minutes** to go!\n"
            f"📆 <t:{int(rift_time.timestamp())}:F>\n"
            f"🚀 Push your limits. This is our moment!",
        
            f"<@&{ROLE_ID}> 🛡️ **Incoming Rift alert!**\n"
            f"💣 Rift starts in **{int(delta/60)} minutes**\n"
            f"⏳ <t:{int(rift_time.timestamp())}:R>\n"
            f"🌟 Every Rift is a chance to shine. Let’s go!",
        
            f"<@&{ROLE_ID}> ⚡ **War horns sound!**\n"
            f"📢 The Rift erupts in **{int(delta/60)} minutes**!\n"
            f"🕒 <t:{int(rift_time.timestamp())}:R> (UTC)\n"
            f"🎯 Focus up! It’s Rift time soon!",
        
            f"<@&{ROLE_ID}> 🎇 **Get ready, warriors!**\n"
            f"⏰ In just **{int(delta/60)} minutes**, it begins.\n"
            f"🕰️ <t:{int(rift_time.timestamp())}:R> | <t:{int(rift_time.timestamp())}:t> UTC\n"
            f"🏆 Together we conquer — don’t miss it!",
        
            f"<@&{ROLE_ID}> 🔥 **Final countdown!**\n"
            f"⏳ Rift in **{int(delta/60)} minutes**.\n"
            f"📅 <t:{int(rift_time.timestamp())}:F> — mark it!\n"
            f"💥 Be legendary — show up and fight!"
        ]
        style_index = hash((rift_time.isoformat(), delta)) % len(messages)
        await channel.send(messages[style_index])

@tree.command(name="nextrift", description="Show the next Rift event")
async def nextrift(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    for rift_time_str in rifts:
        rift_time = pytz.utc.localize(datetime.datetime.strptime(rift_time_str, "%Y-%m-%d %H:%M"))
        if rift_time > now:
            await interaction.response.send_message(
                f"🌀 The next Rift is <t:{int(rift_time.timestamp())}:F>\n"
                f"⏳ <t:{int(rift_time.timestamp())}:R>", ephemeral=True)
            return
    await interaction.response.send_message("No upcoming Rift found.", ephemeral=True)

@tree.command(name="weeklyrifts", description="Show all Rifts in the next 7 days")
async def weeklyrifts(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    one_week = now + datetime.timedelta(days=7)
    upcoming = []
    for rift_time_str in rifts:
        rift_time = pytz.utc.localize(datetime.datetime.strptime(rift_time_str, "%Y-%m-%d %H:%M"))
        if now <= rift_time <= one_week:
            upcoming.append(f"<t:{int(rift_time.timestamp())}:F>")
    if upcoming:
        await interaction.response.send_message("📅 Rifts this week:\n" + "\n".join(upcoming), ephemeral=True)
    else:
        await interaction.response.send_message("No Rifts scheduled for the next 7 days.", ephemeral=True)

@tree.command(name="lastrift", description="Show the last Rift from the schedule")
async def lastrift(interaction: discord.Interaction):
    rift_time = pytz.utc.localize(datetime.datetime.strptime(rifts[-1], "%Y-%m-%d %H:%M"))
    await interaction.response.send_message(
        f"📌 Last Rift in the schedule:\n<t:{int(rift_time.timestamp())}:F>", ephemeral=True)

@tree.command(name="timeleft", description="Show time left until next Rift")
async def timeleft(interaction: discord.Interaction):
    now = datetime.datetime.now(pytz.utc)
    for rift_time_str in rifts:
        rift_time = pytz.utc.localize(datetime.datetime.strptime(rift_time_str, "%Y-%m-%d %H:%M"))
        if rift_time > now:
            delta = rift_time - now
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes = remainder // 60
            await interaction.response.send_message(
                f"⏰ Time left until next Rift: **{hours}h {minutes}m**", ephemeral=True)
            return
    await interaction.response.send_message("No upcoming Rift found.", ephemeral=True)

@tree.command(name="mytime", description="Show your local time and UTC")
async def mytime(interaction: discord.Interaction):
    now = datetime.datetime.now()
    utc_now = datetime.datetime.utcnow()
    await interaction.response.send_message(
        f"🕓 Your local time: **{now.strftime('%H:%M')}**\n"
        f"🌍 UTC time: **{utc_now.strftime('%H:%M')}**", ephemeral=True)

@tree.command(name="help", description="Show all commands and bot details")
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
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="uploadics", description="Upload a .ics file to add new Rift events")
@app_commands.checks.has_any_role(R5_ROLE_ID, R4_ROLE_ID)
async def uploadics(interaction: discord.Interaction, attachment: discord.Attachment):
    if not attachment.filename.endswith(".ics"):
        await interaction.response.send_message("Please upload a valid .ics file.", ephemeral=True)
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

            await interaction.response.send_message(
                f"✅ Rift schedule updated. Added {len(rifts) - old_count} new events (now total {len(rifts)}).",
                ephemeral=True
            )

            channel = await client.fetch_channel(1398208622567227462)
            if channel:
                update_message = (
                    f"📢 **Rift schedule updated!**\n"
                    f"Uploaded by: {interaction.user.mention}\n"
                    f"Total events: **{len(rifts)}**\n"
                    f"Use `/weeklyrifts` or `/nextrift` to view the updated schedule."
                )
                await channel.send(f"<@&{R5_ROLE_ID}> <@&{R4_ROLE_ID}>\n{update_message}")
        else:
            await interaction.response.send_message("No valid Rift dates found in the file.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to parse .ics file: {e}", ephemeral=True)

@uploadics.error
async def uploadics_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing the file.", ephemeral=True)

@tree.command(name="delay_next_rift", description="Shift the next Rift forward/backward by minutes")
@app_commands.describe(minutes="Positive = delay, negative = earlier")
@app_commands.checks.has_any_role(R5_ROLE_ID, R4_ROLE_ID)
async def delay_next_rift(interaction: discord.Interaction, minutes: int):
    now = datetime.datetime.now(pytz.utc)
    for i, rift_time_str in enumerate(rifts):
        rift_time = pytz.utc.localize(datetime.datetime.strptime(rift_time_str, "%Y-%m-%d %H:%M"))
        if rift_time > now:
            new_time = rift_time + datetime.timedelta(minutes=minutes)
            rifts[i] = new_time.strftime("%Y-%m-%d %H:%M")

            notify_channel = await client.fetch_channel(1398208622567227462)
            if notify_channel:
                await notify_channel.send(
                    f"🔧 **Rift manually adjusted!**\n"
                    f"<@&{R5_ROLE_ID}> <@&{R4_ROLE_ID}>\n"
                    f"⏰ New time: <t:{int(new_time.timestamp())}:F> | <t:{int(new_time.timestamp())}:R>\n"
                    f"➕ Adjustment: **{minutes:+} minutes**"
                )

            await interaction.response.send_message(
                f"✅ Rift moved to <t:{int(new_time.timestamp())}:F> ({minutes:+} min)",
                ephemeral=False
            )
            return

    await interaction.response.send_message("No upcoming Rift found to modify.", ephemeral=True)

@delay_next_rift.error
async def delay_next_rift_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while trying to delay the Rift.", ephemeral=True)

keep_alive()

while True:
    try:
        client.run(TOKEN)
    except Exception as e:
        print(f"Bot crashed with error: {e}")
        import time
        time.sleep(5)

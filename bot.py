import os

import bp_to_imgV2

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BP_FOLDER = os.getenv("BLUEPRINT_FOLDER")

#create bp_folder
if not os.path.exists(BP_FOLDER):
    os.mkdir(BP_FOLDER)
    

bot = commands.Bot(command_prefix = "!")

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    print(f"Connected to {len(bot.guilds)} guilds:")
    for guild in bot.guilds:
        print(f"{guild.name} (id: {guild.id})")

@bot.event
async def on_message(message):
    bpcount = await process_attachments(message)
    await bot.process_commands(message)


@bot.command(name="print", help="Print last blueprint uploaded to channel. Only checks last 30 messages.")
async def cmd_print(ctx):
    """Find and print last blueprint in channel"""
    print("Searching and printing last blueprint")
    async for message in ctx.history(limit=30, oldest_first=False):
        bpcount = await process_attachments(message)
        if bpcount != 0:
            break


@bot.event
async def on_reaction_add(reaction, user):
    """React to thumbs down reaction on image"""
    print("Found reaction", reaction, "from user", user)
    if reaction.message.author == bot.user:
        if reaction.emoji == "\U0001f44e":
            print("Thumbs down on bot mesasge")
    else:
        if reaction.emoji == "\U0001f44e":
            print("Thumbs down")


async def process_attachments(message):
    """Checks, processes and sends attachments of message.
    Returns processed blueprint count"""
    #skip messages from self
    if message.author == bot.user:
        return 0

    bpcount = 0
    #iterate attachments
    for attachm in message.attachments:
        if attachm.filename.endswith(".blueprint"):
            bpcount += 1
            try:
                content = await attachm.read()
            except discord.HTTPException:
                print("Downloading the attachment failed:", attachm.filename)
                continue
            except discord.Forbidden:
                print("You do not have permissions to access this attachment:", attachm.filename)
                continue
            except discord.NotFound:
                print("The attachment was deleted:", attachm.filename)
                continue

            #trigger typing
            await message.channel.trigger_typing()
            filename = BP_FOLDER + "/" + attachm.filename
            #save file
            with open(filename, "wb") as f:
                f.write(content)
            #process blueprint
            combined_img_file = await bp_to_imgV2.process_blueprint(filename)
            #files
            file = discord.File(combined_img_file)
            #upload
            await message.channel.send(file=file)
            #delete files
            os.remove(combined_img_file)
            os.remove(filename)

    return bpcount


bot.run(TOKEN)

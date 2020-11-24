import os

import bp_to_imgV2

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BP_FOLDER = os.getenv("BLUEPRINT_FOLDER")
#####AUTHOR = int(os.getenv("AUTHOR"))

#create bp_folder
if not os.path.exists(BP_FOLDER):
    os.mkdir(BP_FOLDER)

#guild/channel config manager
import guildconfig
GCM = guildconfig.GuildconfigManager()

bot = commands.Bot(command_prefix = "bp!")

def print_cmd(ctx):
    """Print command information"""
    print(f"[CMD] <{ctx.command}> invoked by '{ctx.author}' in channel '{ctx.channel}'", "" if ctx.guild is None else f"of guild '{ctx.guild}'")


async def cc_is_author(ctx):
    """Check if command sender is author."""
    return await bot.is_owner(ctx.author)


def cc_is_manager(ctx):
    """Check if command sender has channel managment permissions."""
    return (ctx.guild == None) or (ctx.author.permissions_in(ctx.channel).manage_channels)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    print(f"Connected to {len(bot.guilds)} guilds:")
    for guild in bot.guilds:
        print(f"{guild.name} (id: {guild.id})")

    #set activity text
    act = discord.Game("Create simplified images of blueprint files. Use bp!print to print last file. Use bp!help for commands. Private chat supported.")
    await bot.change_presence(status=discord.Status.online, activity=act)


@bot.event
async def on_message(message):
    """Handle all messages"""
    #skip all bot messages
    if message.author.bot:
        return 0

    #mode
    mode = GCM.getMode(message.guild, message.channel)
    if (mode == 1) or ( ((mode == 2) or (mode is None)) and bot.user.mentioned_in(message) ):
        bpcount = await process_attachments(message)

    #command processing
    await bot.process_commands(message)


@bot.command(name="print", help="Print last blueprint uploaded to channel. Only checks last 30 messages.")
async def cmd_print(ctx):
    """Find and print last blueprint in channel"""
    print_cmd(ctx)
    async for message in ctx.history(limit=30, oldest_first=False):
        bpcount = await process_attachments(message)
        if bpcount != 0:
            break


@bot.command(name="mode", help="Set mode for current channel.\nAllowed arguments:\noff   Turned off.\non  Turned on.\nmention  Only react if bot is mentioned.",
             require_var_positional=False, usage="off | on | mention")
@commands.check(cc_is_manager) 
async def cmd_mode(ctx, mode):
    """Select mode for channel"""
    print_cmd(ctx)
    if ctx.guild is None:
        return

    #check mode
    if not GCM.setMode(ctx.guild, ctx.channel, mode):
        raise commands.errors.BadArgument("Mode could not be set")
    
    await ctx.message.add_reaction("\U0001f197") #:ok:
    


@bot.command(name="test", help="For testing stuff. (Author only)")
@commands.check(cc_is_author)
async def cmd_test(ctx):
    """Testing function"""
    print_cmd(ctx)
    await ctx.channel.send("bp!print")


@bot.event
async def on_command_error(ctx, error):
    """Command error exception"""
    print(f"[ERR] <cmd:{type(error)}> {error}")
    #[print(k, v) for k,v in vars(error).items()]
    if type(error) == commands.errors.CheckFailure:
        #permission error
        await ctx.message.add_reaction("\U0001f4a9") #:poop:
    else:
        await ctx.message.add_reaction("\u2753") #:question:


@bot.event
async def on_reaction_add(reaction, user):
    """React to thumbs down reaction on image"""
    #print("Found reaction", reaction, "from user", user)
    if reaction.message.author == bot.user:
        if reaction.emoji == "\U0001f44e": #:thumbsdown:
            print("Thumbs down on bot mesasge")
    #else:
    #    if reaction.emoji == "\U0001f44e": #:thumbsdown:
    #        print("Thumbs down")


async def process_attachments(message):
    """Checks, processes and sends attachments of message.
    Returns processed blueprint count"""

    #already checked in on_message
    #skip messages from self
    #if message.author == bot.user:
    #    return 0
    #skip all bot messages
    #if message.author.bot:
    #    return 0

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

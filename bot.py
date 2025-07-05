import os
import sys, traceback

import bp_to_img
import re

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
DO_DEBUG = os.getenv("DO_DEBUG")
TOKEN = os.getenv("DISCORD_TOKEN") if not DO_DEBUG else os.getenv("DISCORD_TOKEN_DEBUG")
BP_FOLDER = os.getenv("BLUEPRINT_FOLDER")
#####AUTHOR = int(os.getenv("AUTHOR"))

# create bp_folder
if not os.path.exists(BP_FOLDER):
    os.mkdir(BP_FOLDER)

# guild/channel config manager
import guildconfig
GCM = guildconfig.GuildconfigManager()

# keyword search expression
keywords_re_dict = {"timing": re.compile(r"(?:^|[_*~`\s])(stats|statistics|timing|time)(?:[_*~`\s]|$)"),
                    "nocolor": re.compile(r"(?:^|[_*~`\s])(noc|nocol|nocolor|mat|material|materials)(?:[_*~`\s]|$)"),
                    "gif": re.compile(r"(?:^|[_*~`\s])(?:gif|anim)(?# match gif)"
                                      r"(?:[_*~`\s]+(rand|random))?(?# search rand)(?:[_*~`\s]|$)"),
                    "cut": re.compile(r"(?:^|[_*~`\s])cut(?:[_*~`\s]|$)(?# match cut)"
                                      r"(?:.*?(\d*[.,]\d*))?(?# search float once)"
                                      r"(?:.*?(\d*[.,]\d*))?(?# search float once)"
                                      r"(?:.*?(\d*[.,]\d*))?(?# search float once)"),
                    "aspect": re.compile(r"(?:^|[_*~`\s])(\d+):(\d+)(?:[_*~`\s]|$)")}

lastError = None

bot = commands.Bot(command_prefix = "bp!")


def print_cmd(ctx):
    """Print command information"""
    print(f"[CMD] <{ctx.command}> invoked in channel '{ctx.channel}'", "" if ctx.guild is None else f"of guild '{ctx.guild}'")


def convert_tupel_to_float(tpl):
    """Convert a tupel of strings and None to list of floats and None:
    ('1.23', None) -> [1.23, None]"""
    return [None if elem is None else float(elem) for elem in tpl]


async def cc_is_author(ctx):
    """Check if command sender is author."""
    return await bot.is_owner(ctx.author)


def cc_is_manager(ctx):
    """Check if command sender has channel managment permissions."""
    return (ctx.guild == None) or (ctx.author.permissions_in(ctx.channel).manage_channels)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    removed = GCM.removeUnused(bot.guilds)
    if removed > 0:
        print(f"Removed {removed} unconnected guilds.")
    print(f"Connected to {len(bot.guilds)} guilds:")
    for guild in bot.guilds:
        print(f"{guild.name} (id: {guild.id})")

    # set activity text
    act = discord.Game("Keywords: stats, nocolor, gif, cut. Use bp!print to print last file. "
                        "Use bp!help for commands. Private chat supported.")
    await bot.change_presence(status=discord.Status.online, activity=act)


@bot.event
async def on_guild_remove(guild):
    success = GCM.removeGuild(guild)
    if success:
        print(f"A Guild was removed.")
    else:
        print(f"Guild removal unsuccessful.")


@bot.event
async def on_message(message):
    """Handle all messages"""
    # skip all bot messages
    if message.author.bot:
        return 0

    # mode
    mode = GCM.getMode(message.guild, message.channel)
    if (mode == 1) or (((mode == 2) or (mode is None)) and bot.user.mentioned_in(message)):
        bpcount = await process_attachments(message)

    # command processing
    await bot.process_commands(message)


@bot.command(name="print", help="Print last blueprint uploaded to channel. Only checks last 30 messages.")
async def cmd_print(ctx):
    """Find and print last blueprint in channel"""
    print_cmd(ctx)
    async for message in ctx.history(limit=30, oldest_first=False):
        bpcount = await process_attachments(message, ctx)
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

    # check mode
    if not GCM.setMode(ctx.guild, ctx.channel, mode):
        raise commands.errors.BadArgument("Mode could not be set")
    
    await ctx.message.add_reaction("\U0001f197")  # :ok:
    

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
        # permission error
        await ctx.message.add_reaction("\U0001f4a9")  # :poop:
    else:
        await ctx.message.add_reaction("\u2753")  # :question:


@bot.event
async def on_reaction_add(reaction, user):
    """React to thumbs down reaction on image"""
    #print("Found reaction", reaction, "from user", user)
    if reaction.message.author == bot.user:
        if reaction.emoji == "\U0001f44e":  # :thumbsdown:
            print("Thumbs down on bot mesasge")
    #else:
    #    if reaction.emoji == "\U0001f44e":  # :thumbsdown:
    #        print("Thumbs down")


async def process_attachments(message, invokemessage=None):
    """Checks, processes and sends attachments of message.
    Returns processed blueprint count"""
    global lastError
    # already checked in on_message
    # skip messages from self
    #if message.author == bot.user:
    #    return 0
    # skip all bot messages
    #if message.author.bot:
    #    return 0

    bpcount = 0
    # iterate attachments
    for attachm in message.attachments:
        if attachm.filename.endswith(".blueprint") or attachm.filename.endswith(".blueprint_ba") or attachm.filename.endswith(".blueprint_bac"):
            bpcount += 1
            try:
                content = await attachm.read()
            except discord.Forbidden:
                print("You do not have permissions to access this attachment:", attachm.filename)
                continue
            except discord.NotFound:
                print("The attachment was deleted:", attachm.filename)
                continue
            except discord.HTTPException:
                print("Downloading the attachment failed:", attachm.filename)
                continue

            # trigger typing
            await message.channel.trigger_typing()
            filename = BP_FOLDER + "/" + attachm.filename
            # save file
            with open(filename, "wb") as f:
                f.write(content)
            # keyword search
            content_to_search = message.content if invokemessage is None else invokemessage.message.content
            content_to_search = content_to_search.lower()
            do_send_timing = keywords_re_dict["timing"].search(content_to_search) is not None
            do_player_color = keywords_re_dict["nocolor"].search(content_to_search) is None
            do_create_gif = keywords_re_dict["gif"].search(content_to_search)
            do_random_firing_order = -1 if do_create_gif is not None and do_create_gif.groups()[0] is not None else 2
            do_cut_args = keywords_re_dict["cut"].search(content_to_search)
            do_aspectratio_args = keywords_re_dict["aspect"].search(content_to_search)
            if do_cut_args is None:
                do_cut_args = (None, None, None)
            else:
                do_cut_args = convert_tupel_to_float(do_cut_args.groups())
                if do_cut_args[0] is None:
                    do_cut_args[0] = 0.5
            if do_aspectratio_args:
                do_aspectratio_args = do_aspectratio_args.groups()
                do_aspectratio_args = float(do_aspectratio_args[0]) / float(do_aspectratio_args[1])
            # process blueprint
            try:
                combined_img_file, timing = await bp_to_img.process_blueprint(filename,
                    use_player_colors=do_player_color, create_gif=do_create_gif, firing_order=do_random_firing_order,
                    cut_side_top_front=do_cut_args, force_aspect_ratio=do_aspectratio_args)
                # files
                file = discord.File(combined_img_file)
                # upload
                sendtiming = None
                if do_send_timing:
                    sendtiming = f"JSON parse completed in {timing[0]:.3f}s.\n" \
                                f"Conversion completed in {timing[1]:.3f}s.\n" \
                                f"View matrices completed in {timing[3]:.3f}s.\n" \
                                f"Image creation completed in {timing[4]:.3f}s.\n" \
                                f"Total time: {(timing[0]+timing[1]+timing[2]+timing[3]+timing[4]):.3f}s"
                await message.channel.send(content=sendtiming, file=file)
                # delete image file
                os.remove(combined_img_file)
            except:
                lastError = sys.exc_info()
                await handle_blueprint_error(message, lastError, attachm.filename, bp_to_img.bp_gameversion)
            
            # delete blueprint file
            os.remove(filename)

    return bpcount


async def handle_blueprint_error(message, error, bpfilename, bpgameverison):
    """Sends error notification to channel where message was received and error informations to bot owner."""
    def traceback_string():
        etype, value, tb = error
        exceptionList = traceback.format_exception_only(etype, value)
        tracebackList = traceback.extract_tb(tb)
        s = f"Traceback of `{bpfilename}` with game version {bpgameverison}:\n"
        for elem in tracebackList:
            s += f"File `{elem.filename}`, line {elem.lineno}, in `{elem.name}`\n```{elem.line}```"
        for elem in exceptionList:
            s += elem
        return s

    global bot
    # outdated game version warning
    warn_gv = ""
    if bpgameverison is None:
        bpgameverison = "?"
    else:
        if bpgameverison[0] < 2:
            warn_gv = "\nBlueprint is from an older game version. Consider re-saving and then re-uploading."
        bpgameverison = ".".join([str(e) for e in bpgameverison])

    # log to console
    traceback.print_exception(*error)
    # log to channel and bot owner chat
    ownerId = bot.owner_id
    if ownerId is None or ownerId == 0:
        appinfo = await bot.application_info()
        bot.owner_id = appinfo.owner.id
        ownerId = bot.owner_id
        if ownerId is None or ownerId == 0:
            await message.channel.send("You found an error! Could not send details to bot owner." + warn_gv)
            return
    # fetch owner
    try:
        ownerUser = await bot.fetch_user(ownerId)
    except (discord.NotFound, discord.HTTPException):
        await message.channel.send("You found an error! Could not send details to bot owner." + warn_gv)
        return
    # send
    await ownerUser.send(traceback_string())
    await message.channel.send(f"You found an error! Details were send to {ownerUser.name}." + warn_gv)


bot.run(TOKEN)

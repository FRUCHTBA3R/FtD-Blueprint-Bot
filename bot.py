#!/usr/bin/env python3.12

import os
import sys, traceback
from typing import Optional
import asyncio

import bp_to_img, settings, guildconfig
import re

import discord
from discord.ext import commands
from discord.app_commands import Range as PRange


log = settings.logging.getLogger("bot")

# guild/channel config manager
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


bot = commands.Bot(command_prefix = "bp!", intents=settings.get_bot_intents())


def print_cmd(ctx: commands.Context):
    """Print command information"""
    log.info(f"[CMD] <{ctx.command}> invoked in channel '{ctx.channel}'{"" if ctx.guild is None else f" of guild '{ctx.guild}'"}")


def convert_tupel_to_float(tpl):
    """Convert a tupel of strings and None to list of floats and None:
    ('1.23', None) -> [1.23, None]"""
    return [None if elem is None else float(elem) for elem in tpl]


def get_aspect_ratio(txt: str) -> float|None:
    res = keywords_re_dict["aspect"].search(txt)
    if res:
        res = res.groups()
        res = float(res[0])/float(res[1])
    return res


async def s_fetch_owner() -> None | discord.User:
    """Safely fetches owner as user. Returns None if failed."""
    try:
        # fetch owner if not set
        if not bot.owner_id and not bot.owner_ids:
            await bot.is_owner(None)
        if bot.owner_id:
            owner = await bot.fetch_user(bot.owner_id)
        else:
            # if only i wouldn't had to create a team
            for id in bot.owner_ids:
                break
            owner = await bot.fetch_user(id)
        log.info("Fetched owner %s %i", owner.global_name, owner.id)
        return owner
    except Exception as err:
        log.error("Fetching owner failed: %s", err)
    return None


async def autocomplete_aspect_ratio(interaction: discord.Interaction, txt: str) -> list[discord.app_commands.Choice[str]]:
    suggested_ratios = {"HDTV 16:9":"16:9", "SDTV 4:3":"4:3", "Square 1:1":"1:1", "Camera 3:2":"3:2", 
                        "Ultra Wide 21:9":"21:9", "Movie 16:10":"16:10", "Smartphone 6:13":"6:13"}
    return [discord.app_commands.Choice(name=key, value=val) for key, val in suggested_ratios.items() if txt.lower() in key.lower()]


class MessageOrInteraction():
    """Wrapper for Message or Interaction"""
    def __init__(self, m_or_i: discord.Message | discord.Interaction):
        self.moi = m_or_i
    
    def isMessage(self):
        return isinstance(self.moi, discord.Message)
    
    def isInteraction(self):
        return isinstance(self.moi, discord.Interaction)

    def wasResponded(self):
        return self.isInteraction() and self.moi.response.is_done()

    async def send(self, content: Optional[str] = None, file: Optional[discord.File] = None, ephemeral: bool = True):
        """Sends to channel of message or responds to interaction or sends followups to interaction"""
        kwargs = {}
        if content is not None: kwargs["content"] = content
        if file is not None: kwargs["file"] = file
        
        if self.isMessage():
            self.moi: discord.Message
            await self.moi.channel.send(**kwargs)
        elif self.isInteraction():
            self.moi: discord.Interaction
            if not self.moi.response.is_done():
                await self.moi.response.send_message(**kwargs, ephemeral=ephemeral)
            else:
                await self.moi.followup.send(**kwargs, ephemeral=ephemeral)
        else:
            raise TypeError("Did not get discord.Message or discord.Interaction")


class AutoRemoveFile(discord.File):
    """Discord file, which removes file on disk when going out of scope."""
    def __del__(self):
        log.info("Removing file: %s", self.filename)
        try:
            self.close()
            os.remove(self.fp.name)
        except:
            log.error("File could not be removed.")


#async def cc_is_author(ctx):
#    """Check if command sender is author."""
#    return await bot.is_owner(ctx.author)


#def cc_is_manager(ctx):
#    """Check if command sender has channel managment permissions."""
#    return (ctx.guild == None) or (ctx.channel.permissions_for(ctx.author) == discord.Permissions.manage_channels)


@bot.event
async def on_ready():
    log.info(f"{bot.user} has connected to Discord!")
    removed = GCM.removeUnused(bot.guilds)
    if removed > 0:
        log.info(f"Removed {removed} unconnected guilds.")
    log.info(f"Connected to {len(bot.guilds)} guilds:")
    for guild in bot.guilds:
        log.info(f"{guild.name} (id: {guild.id})")

    # set activity text
    act = discord.Game("Keywords: stats, nocolor, gif, cut. Use bp!print to print last file. "
                        "Use bp!help for commands. Private chat supported.")
    await bot.change_presence(status=discord.Status.online, activity=act)
    
    # commands
    slash_group = SlashCmdGroup(name="blueprint", description="...")
    bot.tree.add_command(slash_group)
    bot.synced_commands = await bot.tree.sync()
    if settings.DO_DEBUG:
        bot.tree.copy_global_to(guild=settings.DEBUG_SERVER)
        log.debug(str(bot.synced_commands))


@bot.event
async def on_guild_remove(guild):
    success = GCM.removeGuild(guild)
    if success:
        print(f"A Guild was removed.")
    else:
        print(f"Guild removal unsuccessful.")


@bot.event
async def on_message(message: discord.Message):
    """Handle all messages"""
    # skip all bot messages
    if message.author.bot:
        return 0

    # mode
    mode = GCM.getMode(message.guild, message.channel)
    if (mode == GCM.Mode.ON) or (((mode == GCM.Mode.MENTION) or (mode is None)) and bot.user.mentioned_in(message)):
        bpcount = await process_message_attachments(message)

    # command processing, remove all mentions and trim, so @mention can use commands
    for m in message.mentions:
        message.content = message.content.replace(m.mention, ' '*len(m.mention))
    message.content = message.content.strip()
    await bot.process_commands(message)

# TODO
@bot.command(name="print", help="DEPRECATED (use right click context menu, SOON). Print last blueprint uploaded to channel. Only checks last 30 messages.")
async def cmd_print(ctx: commands.Context):
    """Find and print last blueprint in channel"""
    await ctx.send("This command is no longer working. A right click context menu will be added soon.")
    #print_cmd(ctx)
    #async for message in ctx.history(limit=30, oldest_first=False):
    #    bpcount = await process_message_attachments(message, ctx)
    #    if bpcount != 0:
    #        break


class ModeTransformer(discord.app_commands.Transformer, commands.Converter):
    def get_choices(self):
        return [
            discord.app_commands.Choice(name="off", value=GCM.Mode.OFF.name),
            discord.app_commands.Choice(name="on", value=GCM.Mode.ON.name),
            discord.app_commands.Choice(name="private", value=GCM.Mode.PRIVATE.name),
        ]
    choices = property(get_choices)

    async def transform(self, interaction: discord.Interaction, value: str) -> guildconfig.Mode:
        # will only get a correct value from choices
        return GCM.Mode[value]

    async def convert(self, ctx: commands.Context, argument: str) -> guildconfig.Mode:
        # can get any string
        argument = argument.upper()
        if argument not in GCM.Mode._member_names_:
            return None
        return GCM.Mode[argument]


@bot.hybrid_command(name="mode", help="Set mode for current channel.\nAllowed arguments:\noff \t Turned off.\non \t Turned on.\nprivate \t Interaction only visible to user.",
            require_var_positional=False, usage="off | on | private")
@commands.has_permissions(manage_channels=True)
async def cmd_mode(ctx: commands.Context, mode: discord.app_commands.Transform[guildconfig.Mode,ModeTransformer]):
    """Select mode for channel"""
    print_cmd(ctx)
    if ctx.guild is None:
        return

    # check mode
    if not GCM.setMode(ctx.guild, ctx.channel, mode):
        raise commands.errors.BadArgument("Mode could not be set")

    if ctx.interaction is None:
        await ctx.message.add_reaction("\U0001f197")  # :ok:
    else:
        await ctx.interaction.response.send_message(f"Mode for this channel was set to {mode.name}", ephemeral=True)


@bot.command(name="pp&tos", help="Send links to privacy policy and terms of service.")
async def cmd_pptos(ctx: commands.Context):
    """Send PP and TOS links to chat"""
    print_cmd(ctx)
    await ctx.send("[Privacy Policy](https://fruchtba3r.github.io/FtD-Blueprint-Bot/datenschutz/)\n"
    "[Terms of Service](https://fruchtba3r.github.io/FtD-Blueprint-Bot/tos/)")


@bot.command(name="test", help="For testing stuff. (Author only)")
@commands.is_owner()
async def cmd_test(ctx: commands.Context, args: str = ""):
    """Testing function"""
    print_cmd(ctx)
    await ctx.channel.send("bp!print")  # recursion test

    try:
        args = discord.Object(int(args))
    except:
        args = None

    ownerUser = await s_fetch_owner()
    if not ownerUser:
        return
    txt = "## Synced Cmds"
    for cmd in bot.synced_commands:
        cmd: discord.app_commands.AppCommand
        perms = "no guild id"
        if args:
            try:
                perms = await cmd.fetch_permissions(args)
            except Exception as err:
                perms = err
        txt += f"\nname `{cmd}` id `{cmd.id}` perms `{perms}`"
        
    await ownerUser.send(txt)



@bot.command(name="notifydeprecated", help="Sends deprecation notification to channels where bot is in mode 'on'")
@commands.is_owner()
async def cmd_notify_deprecated(ctx: commands.Context):
    count = 0
    for i in range(0, 5):
        await asyncio.sleep(5)
        for guild_id in GCM:
            channels = GCM.getChannelsWithMode(guild_id, guildconfig.Mode.ON)
            if i < len(channels):
                count += 1
                channel = await bot.fetch_channel(channels[i])
                await channel.send(
                    "This bot will soon be using slash commands and @mention only.\n" \
                    "This channel is currently in mode `on` which will no longer work the same way.\n" \
                    "Please take a look at the github page for more information.\n"\
                    "(Right click context menu is planned)")
    await ctx.channel.send(f"Notified total of {count} channels")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Command error exception"""
    log.error("[ERR] <cmd:%s> %s", str(type(error)), str(error))
    #[print(k, v) for k,v in vars(error).items()]
    if ctx.interaction is not None:
        await ctx.interaction.response.send_message(error, ephemeral=True)
        return
    if type(error) in (commands.errors.MissingPermissions, commands.errors.NotOwner):
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
            print("Thumbs down on bot message")
    #else:
    #    if reaction.emoji == "\U0001f44e":  # :thumbsdown:
    #        print("Thumbs down")


# TODO: context menu actions: public|private: simple blueprint, simple gif, interactive blueprint creation
#@bot.tree.context_menu(name="Blueprint")
#async def cm_print(interaction: discord.Interaction, message: discord.Message):
#    await process_message_attachments(message)
#    #await interaction.response.send_message(f"Message: ```{message.content}```\nwith {len(message.attachments)} Attachments")



class SlashCmdGroup(discord.app_commands.Group):
    __default_perms = discord.Permissions()
    __default_perms.read_messages = True
    __default_perms.send_messages = True

    @discord.app_commands.command(name="img", description="Create image from blueprint.")
    @discord.app_commands.describe(
        blueprint="File",
        cut_side="Side cut. From 1.0 (closest, all) to 0.0",
        cut_top="Top cut. From 1.0 (closest, all) to 0.0",
        cut_front="Front cut. From 1.0 (closest, all) to 0.0",
        no_color="Disable custom ship color",
        timing="Show processing times",
        aspect_ratio="Output aspect ratio <x>:<y> e.g. 16:9"
    )
    @discord.app_commands.autocomplete(aspect_ratio=autocomplete_aspect_ratio)
    @discord.app_commands.default_permissions(__default_perms)
    async def slash_blueprint(self,
        interaction: discord.Interaction,
        blueprint: discord.Attachment,
        cut_side: PRange[float,0.0,1.0] = None, 
        cut_top: PRange[float,0.0,1.0] = None, 
        cut_front: PRange[float,0.0,1.0] = None,
        no_color: bool = False, 
        timing: bool = False, 
        aspect_ratio: str = ""):
        # mode
        mode = GCM.getMode(interaction.guild, interaction.channel)
        if mode == GCM.Mode.OFF:
            await interaction.response.send_message("Channel is set to OFF", ephemeral=True)
            await asyncio.sleep(1)
            await interaction.delete_original_response()
            return
        moi = MessageOrInteraction(interaction)
        file, content = await process_attachment(moi, blueprint, timing, cut_side_top_front=(cut_side, cut_top, cut_front),
            use_player_colors=not no_color, force_aspect_ratio=get_aspect_ratio(aspect_ratio))
        if content is not None or file is not None:
            await moi.send(content=content, file=file, ephemeral=(mode==GCM.Mode.PRIVATE))


    @discord.app_commands.command(name="gif", description="Create gif from blueprint.")
    @discord.app_commands.describe(
        blueprint="File",
        firing_order="Order in which weapons are fired",
        cut_side="Side cut. From 1.0 (closest, all) to 0.0",
        cut_top="Top cut. From 1.0 (closest, all) to 0.0",
        cut_front="Front cut. From 1.0 (closest, all) to 0.0",
        no_color="Disable custom ship color",
        timing="Show processing times",
        aspect_ratio="Output aspect ratio <x>:<y> e.g. 16:9"
    )
    @discord.app_commands.choices(firing_order=[
        discord.app_commands.Choice(name="Front to Back", value=2),
        discord.app_commands.Choice(name="Random", value=-1),
        discord.app_commands.Choice(name="All at once", value=-2),
        discord.app_commands.Choice(name="Back to Front", value=5),
        discord.app_commands.Choice(name="Top to Bottom", value=1),
        discord.app_commands.Choice(name="Bottom to Top", value=4),
        discord.app_commands.Choice(name="Left to Right", value=3),
        discord.app_commands.Choice(name="Right to Left", value=0),
    ])
    @discord.app_commands.autocomplete(aspect_ratio=autocomplete_aspect_ratio)
    @discord.app_commands.default_permissions(__default_perms)
    async def slash_gif(self,
        interaction: discord.Interaction,
        blueprint: discord.Attachment,
        firing_order: discord.app_commands.Choice[int] = 2,
        cut_side: PRange[float,0.0,1.0] = None, 
        cut_top: PRange[float,0.0,1.0] = None, 
        cut_front: PRange[float,0.0,1.0] = None,
        no_color: bool = False, 
        timing: bool = False, 
        aspect_ratio: str = ""):
        # mode
        mode = GCM.getMode(interaction.guild, interaction.channel)
        if mode == GCM.Mode.OFF:
            await interaction.response.send_message("Channel is set to OFF", ephemeral=True)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
            return
        moi = MessageOrInteraction(interaction)
        if isinstance(firing_order, discord.app_commands.Choice):
            firing_order = firing_order.value
        file, content = await process_attachment(moi, blueprint, timing, create_gif=True,
            firing_order=firing_order, cut_side_top_front=(cut_side, cut_top, cut_front),
            use_player_colors=not no_color, force_aspect_ratio=get_aspect_ratio(aspect_ratio))
        if content is not None or file is not None:
            await moi.send(content=content, file=file, ephemeral=(mode==GCM.Mode.PRIVATE))



async def process_attachment(moi: MessageOrInteraction, attachment: discord.Attachment, do_timing:bool, **kwargs: any
                        #make_gif: bool, firing_order: int|None, cut_stf: tuple[float, float, float]|None,
                        #nocol: bool, timing: bool, aspect_ratio: float|None
                    ) -> tuple[str,discord.File] | tuple[None, None]:
    try:
        fname = os.path.join(settings.BP_FOLDER, attachment.filename)
        img_fname, timing = await bp_to_img.process_blueprint([fname, await attachment.read()], **kwargs)
    except:
        # TODO
        lastError = sys.exc_info()
        await handle_blueprint_error(moi, lastError, attachment.filename, bp_to_img.bp_gameversion)
        # TODO: check if a file was created and delete
        return None, None
    img_file = AutoRemoveFile(img_fname)
    timing_content = None
    if do_timing:
        timing_content = f"JSON parse completed in {timing[0]:.3f}s.\n" \
            f"Conversion completed in {timing[1]:.3f}s.\n" \
            f"View matrices completed in {timing[3]:.3f}s.\n" \
            f"Image creation completed in {timing[4]:.3f}s.\n" \
            f"Total time: {(timing[0]+timing[1]+timing[2]+timing[3]+timing[4]):.3f}s"
    return img_file, timing_content



async def process_message_attachments(message: discord.Message, invokemessage=None):
    """Checks, processes and sends attachments of message.
    Returns processed blueprint count"""
    global lastError

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
            await message.channel.typing()
            filename = settings.BP_FOLDER + "/" + attachm.filename
            # save file  # NO use bytes object directly
            #with open(filename, "wb") as f:
            #    f.write(content)
            # keyword search
            content_to_search = message.content if invokemessage is None else invokemessage.message.content
            content_to_search = content_to_search.lower()
            do_send_timing = keywords_re_dict["timing"].search(content_to_search) is not None
            do_player_color = keywords_re_dict["nocolor"].search(content_to_search) is None
            do_create_gif = keywords_re_dict["gif"].search(content_to_search)
            do_random_firing_order = -1 if do_create_gif is not None and do_create_gif.groups()[0] is not None else 2
            do_cut_args = keywords_re_dict["cut"].search(content_to_search)
            do_aspectratio_args = get_aspect_ratio(content_to_search)
            if do_cut_args is None:
                do_cut_args = (None, None, None)
            else:
                do_cut_args = convert_tupel_to_float(do_cut_args.groups())
                if do_cut_args[0] is None:
                    do_cut_args[0] = 0.5
            # process blueprint
            #try:
            combined_img_file, timing = await process_attachment(MessageOrInteraction(message), attachm, 
                    do_send_timing, use_player_colors=do_player_color,
                    create_gif=do_create_gif, firing_order=do_random_firing_order, cut_side_top_front=do_cut_args,
                    force_aspect_ratio=do_aspectratio_args)
                #combined_img_file, timing = await bp_to_img.process_blueprint([filename, content],
                #    use_player_colors=do_player_color, create_gif=do_create_gif, firing_order=do_random_firing_order,
                #    cut_side_top_front=do_cut_args, force_aspect_ratio=do_aspectratio_args)
                # files
                #file = discord.File(combined_img_file)
                # upload
                #sendtiming = None
                #if do_send_timing:
                #    sendtiming = f"JSON parse completed in {timing[0]:.3f}s.\n" \
                #                f"Conversion completed in {timing[1]:.3f}s.\n" \
                #                f"View matrices completed in {timing[3]:.3f}s.\n" \
                #                f"Image creation completed in {timing[4]:.3f}s.\n" \
                #                f"Total time: {(timing[0]+timing[1]+timing[2]+timing[3]+timing[4]):.3f}s"
            await message.channel.send(content=timing, file=combined_img_file)
                # delete image file
            #    os.remove(combined_img_file)
            #except:
            #    lastError = sys.exc_info()
            #    await handle_blueprint_error(message, lastError, attachm.filename, bp_to_img.bp_gameversion)
            
            # delete blueprint file
            #os.remove(filename)

    return bpcount


async def handle_blueprint_error(moi: MessageOrInteraction, error, bpfilename: str, bpgameverison: str):
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
    try:
        log.exception(traceback.format_exception(*error))
    except Exception as err:
        log.critical(f"Couldn't log blueprint error: {err}")
    # log to channel and bot owner chat
    ownerUser = await s_fetch_owner()
    if not ownerUser:
        await moi.send("You found an error! Could not send details to bot owner." + warn_gv)
        return
    # send
    await ownerUser.send(traceback_string())
    await moi.send(f"You found an error! Details were send to {ownerUser.name}." + warn_gv)


bot.run(settings.TOKEN(), root_logger=True)

#!/usr/bin/env python3.12

import os
import sys, traceback
import asyncio
import re

import discord
from discord.ext import commands
from discord.app_commands import Range as PRange

import bp_to_img, settings, guildconfig
from classes import MessageOrInteraction, InteractiveBlueprint, firing_order_options, aspect_ratio_options


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
            await bot.is_owner(discord.Object(0))
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
    return [discord.app_commands.Choice(name=key, value=val) for key, val in aspect_ratio_options.items() if txt.lower() in key.lower()]



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
    act = discord.Game("/blueprint or @mention - Keywords: stats, nocolor, gif, cut. "
                        "Use bp!help for commands. Private chat supported.")
    await bot.change_presence(status=discord.Status.online, activity=act)
    
    # commands
    slash_group = SlashCmdGroup(name="blueprint", description="...")
    try:
        bot.tree.add_command(slash_group)
        bot.synced_commands = await bot.tree.sync()
        if settings.DO_DEBUG:
            bot.tree.copy_global_to(guild=settings.DEBUG_SERVER)
            log.debug(str(bot.synced_commands))
    except discord.app_commands.CommandAlreadyRegistered as err:
        pass
    except Exception as err:
        log.error(str(err))


@bot.event
async def on_guild_remove(guild):
    success = GCM.removeGuild(guild)
    if success:
        log.info(f"A Guild was removed.")
    else:
        log.info(f"Guild removal unsuccessful.")


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

    if args:
        # sync to guild
        synced_commands = await bot.tree.sync(guild=args)
        # get commands from guild
        fetched_commands = await bot.tree.fetch_commands(guild=args)
        # get globals
        fetched_global_commands = await bot.tree.fetch_commands()

    # get permissions of command for guild
    perms_for_humans = lambda l: [f"{p.target}:{p.permission}" for p in l]
    guild_name = bot.get_guild(args.id).name if args else "?"
    txt = [f"## Cmds for „{guild_name}“"]
    headings = ["bot.synced_cmds", "synced_cmds", "fetched_cmds", "fetched_global_cmds"]
    for i, synced_cmds in enumerate([bot.synced_commands, synced_commands, fetched_commands, fetched_global_commands]):
        txt.append(f"### {headings[i]}")
        for cmd in synced_cmds:
            cmd: discord.app_commands.AppCommand
            perms = "no guild id"
            if args:
                try:
                    perms = (await cmd.fetch_permissions(args)).permissions
                    perms = perms_for_humans(perms)
                except Exception as err:
                    perms = err
            txt.append(f"name `{cmd}` id `{cmd.id}` perms `{perms}`")

    ownerUser = await s_fetch_owner()
    if not ownerUser:
        return
    content = ""
    # limit to less than 2000 chars per message
    for line in txt:
        if 1999 > len(content) + len(line):  # "\n" gives +1
            content += "\n" + line
        else:
            await ownerUser.send(content)
            content = line
    else:
        await ownerUser.send(content)



@bot.command(name="omode")
@commands.is_owner()
async def cmd_owner_mode(ctx: commands.Context, *args: str):
    """List or set mode for channels. For debugging and testing.
    
    Parameters:
    args: guildID [channelID [on|private|off]]"""
    print_cmd(ctx)
    log.info("with args %s", args)

    if 0 >= len(args) or 3 < len(args):
        await ctx.send("Invalid args")
        return

    # make sure guilds and channels actually exist
    try:
        guild = bot.get_guild(int(args[0]))
    except Exception as err:
        await ctx.send(str(err))
        return

    channel = None
    if 2 <= len(args):
        try:
            channel = guild.get_channel(int(args[1]))
        except Exception as err:
            await ctx.send(str(err))
            return
    
    # set mode
    if 3 == len(args):
        mode = await ModeTransformer.convert(None, ctx, args[2])
        if mode is None:
            await ctx.send("Invalid mode")
            return
        success = GCM.setMode(guild, channel, mode)
        await ctx.send(f"{["FAILED","SUCCESS"][int(success)]}: {guild.name} < {channel.name} < Mode:{mode.name}")
        return
    
    # list all saved modes
    if channel is None:
        txt = [f"## Listing: {guild.name} >"]
        channels = GCM.get(args[0], {})
        for channel_id in channels.keys():
            channel = guild.get_channel(int(channel_id))
            if channel is None:
                txt.append(f"Non existing channel with id: {channel_id}")
            else:
                mode = GCM.getMode(guild, channel)
                mode = mode.name if mode is not None else "None"
            txt.append(f"{channel.name} > Mode:{mode}")
        await ctx.send("\n".join(txt))
        return
    
    # list mode for channel
    mode = GCM.getMode(guild, channel)
    mode = mode.name if mode is not None else "None"
    await ctx.send(f"{guild.name} > {channel.name} > Mode:{mode}")



@bot.command(name="notifydeprecated", help="Sends deprecation notification to channels where bot is in mode 'on'")
@commands.is_owner()
async def cmd_notify_deprecated(ctx: commands.Context, confirm: str = ""):
    confirm = confirm == "confirm"
    dep_message = "This bot is now using slash commands and @mention only.\n" \
        "This channel is currently in mode `on` which will no longer work the same way.\n" \
        "If slash commands aren't showing up, check the permissions and try reinviting the bot and reloading Discord.\n" \
        "Please take a look at the github page for more information.\n" \
        "(Right click context menu is planned)"
    count = 0
    failed_count = 0
    for i in range(0, 5):
        await asyncio.sleep(5)
        for guild_id in GCM:
            channels = GCM.getChannelsWithMode(guild_id, GCM.Mode.ON)
            if i < len(channels):
                count += 1
                try:
                    channel = await bot.fetch_channel(channels[i])
                    if confirm:
                        await channel.send(dep_message)
                except Exception as err:
                    log.warning(f"Failed for channel {channels[i]} with {err}")
                    failed_count += 1
    if not confirm:
        await ctx.channel.send(dep_message)
    await ctx.channel.send(f"{"" if confirm else "(Would have) "}Notified total of {count-failed_count} channels, with {failed_count} failed")


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
            log.info("Thumbs down on bot message")
    #else:
    #    if reaction.emoji == "\U0001f44e":  # :thumbsdown:
    #        print("Thumbs down")


default_perms_app_command = discord.Permissions()
default_perms_app_command.read_messages = True
default_perms_app_command.send_messages = True

async def check_mode(interaction: discord.Interaction) -> guildconfig.Mode | None:
    mode = GCM.getMode(interaction.guild, interaction.channel)
    if mode == GCM.Mode.OFF:
        await interaction.response.send_message("Channel is set to OFF", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.delete_original_response()
        return None
    return mode


class SlashCmdGroup(discord.app_commands.Group):

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
    @discord.app_commands.default_permissions(default_perms_app_command)
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
        mode = await check_mode(interaction)
        if mode is None:
            return
        moi = MessageOrInteraction(interaction)
        await moi.defer(ephemeral=(mode==GCM.Mode.PRIVATE), thinking=True)
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
        timing="Show processing times"
    )
    @discord.app_commands.choices(firing_order=[
        discord.app_commands.Choice(name=elem["name"], value=elem["value"])
        for elem in firing_order_options
    ])
    @discord.app_commands.default_permissions(default_perms_app_command)
    async def slash_gif(self,
        interaction: discord.Interaction,
        blueprint: discord.Attachment,
        firing_order: discord.app_commands.Choice[int] = 2,
        cut_side: PRange[float,0.0,1.0] = None, 
        cut_top: PRange[float,0.0,1.0] = None, 
        cut_front: PRange[float,0.0,1.0] = None,
        no_color: bool = False, 
        timing: bool = False):
        # mode
        mode = await check_mode(interaction)
        if mode is None:
            return
        moi = MessageOrInteraction(interaction)
        moi.defer(ephemeral=(mode==GCM.Mode.PRIVATE), thinking=True)
        if isinstance(firing_order, discord.app_commands.Choice):
            firing_order = firing_order.value
        file, content = await process_attachment(moi, blueprint, timing, create_gif=True,
            firing_order=firing_order, cut_side_top_front=(cut_side, cut_top, cut_front),
            use_player_colors=not no_color)
        if content is not None or file is not None:
            await moi.send(content=content, file=file, ephemeral=(mode==GCM.Mode.PRIVATE))


@bot.tree.context_menu(name="Simple Blueprint")
@discord.app_commands.default_permissions(default_perms_app_command)
async def cm_print(interaction: discord.Interaction, message: discord.Message):
    if (await check_mode(interaction)) is None:
        return
    no_loop = True
    # only first 3 valid attachments will get processed
    for attachment in get_valid_attachments(message.attachments)[:3]:
        await SlashCmdGroup.slash_blueprint.callback(None, interaction, attachment)
        no_loop = False
    if no_loop:
        try:
            await interaction.response.send_message("No valid files in message attachments, maybe try Interactive Blueprint.", delete_after=5, ephemeral=True)
        except:
            log.warning("Interaction response failed")


@bot.tree.context_menu(name="Simple Gif")
@discord.app_commands.default_permissions(default_perms_app_command)
async def cm_gif(interaction: discord.Interaction, message: discord.Message):
    if (await check_mode(interaction)) is None:
        return
    no_loop = True
    # only first 3 valid attachments will get processed
    for attachment in get_valid_attachments(message.attachments)[:3]:
        await SlashCmdGroup.slash_gif.callback(None, interaction, attachment)
        no_loop = False
    if no_loop:
        try:
            await interaction.response.send_message("No valid files in message attachments, maybe try Interactive Blueprint.", delete_after=5, ephemeral=True)
        except:
            log.warning("Interaction response failed")


@bot.tree.context_menu(name="Interactive Blueprint")
@discord.app_commands.default_permissions(default_perms_app_command)
async def cm_interactive(interaction: discord.Interaction, message: discord.Message):
    if len(message.attachments) == 0:
        await interaction.response.send_message("No attachments found.", delete_after=2, ephemeral=True)
        return

    mode = await check_mode(interaction)
    if mode is None:
        return

    interactive_bp = InteractiveBlueprint(mode, [m.filename for m in message.attachments])
    await interactive_bp.show(interaction)
    timed_out = await interactive_bp.wait()
    if timed_out:
        log.debug("Interactive Blueprint timed out")
        try:
            await interaction.delete_original_response()
        except:
            pass
        return

    moi = MessageOrInteraction(interaction)
    for i in interactive_bp.selected_files:
        file, content = await process_attachment(moi, message.attachments[i],
            do_timing=interactive_bp.do_timing,
            create_gif=interactive_bp.create_gif,
            firing_order=interactive_bp.firing_order,
            cut_side_top_front=interactive_bp.cut_side_top_front,
            use_player_colors=interactive_bp.use_player_colors,
            force_aspect_ratio=get_aspect_ratio(interactive_bp.aspect_ratio_string)
        )
        if content is not None or file is not None:
            await moi.send(content=content, file=file, ephemeral=(mode==GCM.Mode.PRIVATE))



async def process_attachment(moi: MessageOrInteraction, attachment: discord.Attachment, do_timing:bool, **kwargs: any
                        #make_gif: bool, firing_order: int|None, cut_stf: tuple[float, float, float]|None,
                        #nocol: bool, timing: bool, aspect_ratio: float|None
                    ) -> tuple[AutoRemoveFile, str] | tuple[None, None]:
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


def get_valid_attachments(attachments: list[discord.Attachment]) -> list[discord.Attachment]:
    """Returns list with all valid attachments"""
    res = [
        attachment 
        for attachment in attachments 
        if is_valid_filename(attachment.filename)
    ]
    return res

def is_valid_filename(filename: str) -> bool:
    """Returns true if filename is a blueprint file"""
    _, ext = os.path.splitext(filename)
    return ext in [".blueprint", ".blueprint_ba", ".blueprint_bac"]


async def process_message_attachments(message: discord.Message, invokemessage=None):
    """Checks, processes and sends attachments of message.
    Returns processed blueprint count"""
    global lastError

    bpcount = 0
    # iterate attachments
    for attachm in message.attachments:
        if is_valid_filename(attachm.filename):
            bpcount += 1
            try:
                content = await attachm.read()
            except discord.Forbidden:
                log.warning("You do not have permissions to access this attachment: %s", attachm.filename)
                continue
            except discord.NotFound:
                log.warning("The attachment was deleted: %s", attachm.filename)
                continue
            except discord.HTTPException:
                log.warning("Downloading the attachment failed: %s", attachm.filename)
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

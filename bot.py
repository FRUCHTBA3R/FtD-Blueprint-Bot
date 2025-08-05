#!/usr/bin/env python3.12

import os
import sys, traceback
import asyncio
import re

import discord
from discord.ext import commands
from discord.app_commands import Range as PRange

import bp_to_img, settings, guildconfig
from classes import MessageOrInteraction, InteractiveBlueprint, firing_order_options, aspect_ratio_options, PermissionState


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
        if settings.DO_DEBUG:
            bot.tree.copy_global_to(guild=settings.DEBUG_SERVER)
        bot.synced_commands = await bot.tree.sync()
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
@bot.command(name="print", help="DEPRECATED (use right click context menu). Print last blueprint uploaded to channel. Only checks last 30 messages.")
async def cmd_print(ctx: commands.Context):
    """Find and print last blueprint in channel"""
    await ctx.send("This command is no longer supported. Use right click context menu instead.")
    #print_cmd(ctx)
    #async for message in ctx.history(limit=30, oldest_first=False):
    #    bpcount = await process_message_attachments(message, ctx)
    #    if bpcount != 0:
    #        break



@bot.hybrid_command(name="mode", help="Set mode for current channel.\nAllowed arguments:\noff \t Turned off.\non \t Turned on.\nprivate \t Interaction only visible to user.",
            require_var_positional=False, usage="off | on | private")
@commands.has_permissions(manage_channels=True)
@discord.app_commands.default_permissions(discord.Permissions(manage_channels=True))
async def cmd_mode(ctx: commands.Context, mode: discord.app_commands.Transform[guildconfig.Mode,guildconfig.ModeTransformer]):
    """Select mode for channel"""
    print_cmd(ctx)
    if ctx.guild is None:
        return # TODO this will fail the interaction

    # check mode
    if not GCM.setMode(ctx.guild, ctx.channel, mode):
        raise commands.errors.BadArgument("Mode could not be set")

    if ctx.interaction is None:
        await ctx.message.add_reaction("\U0001f197")  # :ok:
    else:
        await ctx.interaction.response.send_message(f"Mode for this channel was set to {mode.name}", ephemeral=True)



async def send_permission_list_embed(moi: MessageOrInteraction, perm_includes_text: str):
    embed = discord.Embed(
        color=discord.Color.blurple(),
        title="Permission Evaluation",
        description=f"No permissions including `{perm_includes_text}` in their name were found.\n"
            "You can find some inspiration in the [discord.py documentation]"
            "(https://discordpy.readthedocs.io/en/stable/api.html?#discord.Permissions)",
        url="https://discordpy.readthedocs.io/en/stable/api.html?#discord.Permissions"
    )
    await moi.send(ephemeral=False, embed=embed)



async def fetch_guild_channel_from_name_or_id(guild: discord.Guild|None, to_find: str) -> discord.abc.GuildChannel|None:
    """
    Fetch channel by ID (global!) or search for channel in guild with name containing to_find.

    Args:
        guild (discord.Guild | None): Guild to get channels from or None
        to_find (str): ID or part of channel name

    Raises:
        ValueError: Invalid to_find
        and Errors of bot.fetch_channel

    Returns:
        discord.abc.GuildChannel|None: The found channel or None if not found
    """
    try:
        to_find = int(to_find)
    except:
        pass
    if isinstance(to_find, str):
        if guild is None: return None
        found_index = 999
        found_channel: discord.abc.GuildChannel = None
        for channel in guild.channels:
            channel:discord.abc.GuildChannel
            if isinstance(channel, discord.CategoryChannel):
                continue
            index = channel.name.find(to_find)
            if -1 < index and index < found_index:
                found_index = index
                found_channel = channel
        return found_channel
    elif isinstance(to_find, int):
        channel = await bot.fetch_channel(to_find)
        return channel
    raise ValueError



def str_ansi_colored(text: any, state_to_color: any, bold: bool = False, underline: bool = False):
    """Creates red, yellow or green text with bold and underline if wanted"""
    if not isinstance(text, str): text = str(text)
    if isinstance(state_to_color, PermissionState): state_to_color = state_to_color.state
    color = {False: "31", True: "32", None: "33", "None": "1"}[state_to_color]
    return f"\u001b[{(bold and "1;") or ""}{(underline and "4;") or ""}{color}m{text}\u001b[0;0m"



def evaluate_permissions_to_embed(
        embed:discord.Embed,
        search_for: str,
        perms_guild: discord.Permissions,
        perms_in_channel: discord.Permissions,
        perms_overwrite: discord.PermissionOverwrite,
        limit: int = 3
) -> tuple[PermissionState, int]:
    """Evaluates guild and channel permissions and stores result in embed.
    Returns state (True if all permissions are granted, False if all are denied, None if mixed)
    and number of matching permissions.

    Args:
        embed (Embed): Fields will be added to this
        search_for (str): Text to search in permission name
        perms_guild (Permissions): The global permissions in the guild (from roles and @everyone)
        perms_in_channel (Permissions): The permissions in the channel (completely resolved)
        perms_overwrite (PermissionOverwrite): The permission overwrites of the channel
        limit (int, optional): The maximum number of matching permissions to evaluate. Defaults to 3.

    Returns:
        tuple(PermissionState, int): (state, matches)
    """
    found = 0
    flag_allowed = False
    flag_denied = False
    for perm_name, value_channel in iter(perms_in_channel):
        if -1 == perm_name.find(search_for):
            continue
        found += 1
        if limit < found:
            continue
        flag_allowed |= value_channel
        flag_denied |= not value_channel
        value_gild = getattr(perms_guild, perm_name)
        value_gild = str_ansi_colored(PermissionState(value_gild), value_gild)
        value_overwrite = getattr(perms_overwrite, perm_name)
        value_overwrite = str_ansi_colored(PermissionState(value_overwrite), value_overwrite)
        value_channel = str_ansi_colored(PermissionState(value_channel), value_channel, True, True)
        embed.add_field(name=f"Permission: {perm_name}", inline=False, value=f"```ansi\n"
            f"• Guild (Roles): {value_gild}\n"
            f"• Channel overwrite: {value_overwrite}\n"
            f"• In Channel: {value_channel}```")
    return PermissionState(flag_allowed, flag_denied), found



def evaluate_command_permission_list(
        cmd_perm_list: list[discord.app_commands.AppCommandPermissions],
        channel: discord.abc.GuildChannel,
        member: discord.Member
) -> tuple[PermissionState, PermissionState, PermissionState]:
    """Evaluates permissions list for a command in respect to channel and member.
    Returns state for channel, role and member. With state being True if allowed, 
    False if denied, None if unchanged.

    Args:
        cmd_perm_list (list[AppCommandPermissions]): list of permissions for command
        channel (GuildChannel): Channel to check permissions for
        member (Member): Member to check permissions for

    Returns:
        states (tuple[bool | None, bool | None, bool | None]): State for channel, State for role, State for member
    """
    state_channel = PermissionState(None)
    state_member = PermissionState(None)
    state_role = PermissionState(None)
    if cmd_perm_list is None:
        return state_channel, state_role, state_member
    t = discord.AppCommandPermissionType
    for perm in cmd_perm_list:
        if t.channel ==  perm.type:
            if perm.id == channel.id:
                state_channel.set(perm.permission)
            elif perm.id == channel.guild.id - 1 and state_channel.unchanged:
                state_channel.set(perm.permission)
        elif t.user == perm.type:
            if perm.id == member.id:
                state_member.set(perm.permission)
        elif t.role == perm.type:
            if perm.target in member.roles:
                # assume that any role set to allowed will allow
                state_role = state_role.any(PermissionState(perm.permission))
    return state_channel, state_role, state_member



async def _application_command_fetch_guild_permissions(
    state: discord.state.ConnectionState,
    guild: discord.abc.Snowflake
) -> list[discord.app_commands.GuildAppCommandPermissions]:
    """Gets global application command permissions"""
    if not state.application_id:
        raise discord.MissingApplicationID
    
    data_list = await state.http.get_guild_application_command_permissions(
        application_id=state.application_id,
        guild_id=guild.id
    )
    return [discord.app_commands.GuildAppCommandPermissions(data=data, state=state, command=None) for data in data_list]



async def evaluate_command_permission_to_embed(
        embed: discord.Embed,
        command_start: str,
        member: discord.Member,
        channel: discord.abc.GuildChannel,
        state_use_app_cmd: PermissionState
) -> tuple[PermissionState, int]:
    """Evaluates application command permissions and adds result as embed field.
    Returns state of all found commands, True if all are allowed, False if all are denied, else None.
    And number of found commands.

    Args:
        embed (Embed): Embed to add fields to
        command_start (str): String the command starts with
        member (Member): Member to check permissions for
        channel (GuildChannel): Channel to check permissions for
        state_use_app_cmd (PermissionState): Result of use_application_commands check for channel

    Returns:
        (PermissionState, int): Unified state and #found commands
    """
    flag_allowed = False
    flag_denied = False
    count = 0
    
    # we will not search other applications as this would require manage_channels permission
    # prepare cmds
    global_commands = await bot.tree.fetch_commands()
    guild_commands = await bot.tree.fetch_commands(guild=channel.guild)
    commands_to_merge = []
    for global_cmd in global_commands:
        found = False
        for guild_cmd in guild_commands:
            found |= (global_cmd.id == guild_cmd.id)
        if not found:
            commands_to_merge.append(global_cmd)
    guild_commands.extend(commands_to_merge)
    global_commands = commands_to_merge = None
    
    # search cmd, limit to 4
    guild_commands = [cmd for cmd in guild_commands if cmd.name.startswith(command_start)]
    count = len(guild_commands)
    guild_commands = guild_commands[:4]
    
    # fetch all permissions
    guild_cmd_permissions_list = await _application_command_fetch_guild_permissions(bot.tree._state, channel.guild)
    guild_cmd_permissions_list = {perm.id:perm for perm in guild_cmd_permissions_list}
    
    # global cmd permissions
    global_cmd_perms = guild_cmd_permissions_list.get(bot.application_id)
    if global_cmd_perms:
        global_cmd_perms = global_cmd_perms.permissions
    global_state_channel, global_state_role, global_state_member = evaluate_command_permission_list(global_cmd_perms, channel, member)
    # assume member overrides role (confirmed)
    global_state_final = global_state_role.overwrite(global_state_member).both(global_state_channel)
    
    # get per command permissions
    permission_tuple_list = []
    for cmd in guild_commands:
        cmd_perms = guild_cmd_permissions_list.get(cmd.id)
        if cmd_perms: cmd_perms = cmd_perms.permissions
        cmd_perms_default = cmd.default_member_permissions
        permission_tuple_list.append((cmd_perms, cmd_perms_default))
    
    # compare
    perms_in_channel = channel.permissions_for(member)
    for i, cmd in enumerate(guild_commands):
        cmd_perms, cmd_perms_default = permission_tuple_list[i]
        txt_value = ""
        state_final = state_default_final = PermissionState(None)
        
        # default required perms
        if cmd_perms_default is not None:
            txt_value += "\n" + str_ansi_colored("Default Required Permissions", "None", True, True) + "\n"
            perms_ok = (perms_in_channel & cmd_perms_default)
            perms_missing = (~perms_in_channel & cmd_perms_default)
            missing_default_perm = False
            for perm_name, value in iter(perms_ok):
                if value:
                    txt_value += f"• Has {str_ansi_colored(perm_name, True)}\n"
            for perm_name, value in iter(perms_missing):
                if value:
                    missing_default_perm = True
                    txt_value += f"• {str_ansi_colored("MISSING", False)} {perm_name}\n"
            flag_denied |= missing_default_perm
            flag_allowed |= not missing_default_perm
            state_default_final = PermissionState(not missing_default_perm)
        
        # global cmd perms
        if global_cmd_perms is not None:
            txt_value += "\n" + str_ansi_colored("Global Command Permissions", "None", True, True) + "\n"
            txt_value += f"• In Channel: {str_ansi_colored(global_state_channel, global_state_channel)}\n" \
                f"• For Member: {str_ansi_colored(global_state_member, global_state_member)}\n" \
                f"• For Member's Roles: {str_ansi_colored(global_state_role, global_state_role)}\n" \
                f"• Together -> {str_ansi_colored(global_state_final, global_state_final, True, True)}\n"
        
        # per-cmd perms
        if cmd_perms is not None:
            txt_value += "\n" + str_ansi_colored("Per-Command Permissions", "None", True, True) + "\n"
            state_channel, state_role, state_member = evaluate_command_permission_list(cmd_perms, channel, member)
            # assume member overrides role
            state_final = state_role.overwrite(state_member).both(state_channel)
            flag_allowed |= state_final.allowed
            flag_denied |= state_final.denied
            txt_value += f"• In Channel: {str_ansi_colored(state_channel, state_channel)}\n" \
                f"• For Member's Roles: {str_ansi_colored(state_role, state_role)}\n" \
                f"• For Member: {str_ansi_colored(state_member, state_member)}\n" \
                f"• Together -> {str_ansi_colored(state_final, state_final, True, True)}\n"
        
        # the final result, I promise
        # ((global cmd perms AND default required perms) OverWritten by per-cmds perms for member/role) AND per-cmds perms for channel
        state_all_final = global_state_final.both(state_default_final).overwrite(state_role.overwrite(state_member)).both(state_channel)
        state_can_be_used = state_use_app_cmd.both(state_all_final)
        txt_value += "\n" + str_ansi_colored(f"This Command {"Is" if not state_use_app_cmd.denied else "Would Be"}: ", state_can_be_used, True, False)
        txt_value +=  str_ansi_colored(state_all_final, state_all_final, True, False) + "\n"
        if state_use_app_cmd.denied:
            txt_value += str_ansi_colored("But is DENIED by missing use_application_commands permission anyway!", False, True)
        
        embed.add_field(name=f"Command: {cmd.name}", value=f"```ansi\n{txt_value}```", inline=False)
    return PermissionState(flag_allowed, flag_denied), count



def PermissionOverwrite_any(self: discord.PermissionOverwrite, other: discord.PermissionOverwrite) -> discord.PermissionOverwrite:
    """Merges two PermissionOverwrites. Any Allow will allow."""
    res = discord.PermissionOverwrite()
    for key, val in iter(self):
        val_other = other._values.get(key)
        if val is None and val_other is None:
            continue
        elif val is None:
            res._values[key] = val_other
        elif val_other is None:
            res._values[key] = val
        else:
            res._values[key] = val or val_other
    return res
discord.PermissionOverwrite.any = PermissionOverwrite_any


@bot.hybrid_command(name="whycant", help="Helps with permissions conflict resolution.",
                    require_var_positional=False)
@discord.app_commands.describe(
    member="Member ID or i for yourself",
    do="Text to search for in permission name OR /command_starts_with_text",
    channel="Channel ID or here for current channel"
)
async def cmd_whycant(ctx: commands.Context, member: str="I", do: str="use_application_commands", channel: str="here"):
    """Evaluates member permissions and app command permissions.
    
    Parameters:
        member: Member ID or i for yourself
        do: Text to search for in permission name OR /command_starts_with_text
        channel: Channel (ID | partial name) OR here for current channel"""
    print_cmd(ctx)
    
    moi = MessageOrInteraction(ctx.message if ctx.interaction is None else ctx.interaction)
    
    # if this is not invoked in a guild, allow only owner
    if ctx.guild is None:
        ownerUser = await s_fetch_owner()
        if ownerUser is None:
            await moi.send("Couldn't check if you're the owner")
            return
        if ctx.author != ownerUser:
            await moi.send("Not allowed")
            return
    
    # get channel
    if "here" != channel.lower():
        try:
            channel = await fetch_guild_channel_from_name_or_id(ctx.guild, channel)
        except Exception as err:
            await moi.send(str(err))
            return
    elif ctx.guild is not None:
        channel = ctx.channel
    else:
        # not in a gild channel and no channel id given
        await moi.send("No channel id was given")
        return
    if ctx.guild != channel.guild:
        # allow only owner to query other guilds
        ownerUser = await s_fetch_owner()
        if ctx.author != ownerUser:
            await moi.send("Querying other guilds is not allowed")
            return
    channel: discord.abc.MessageableChannel
    
    # get member
    if member in ["i", "I"]:
        member = ctx.author.id
    try:
        member = await channel.guild.fetch_member(int(member))
    except Exception as err:
        await moi.send(str(err))
        return
    member: discord.Member
    
    # gather member permissions
    perms_guild = member.guild_permissions
    channel_overwrites = channel.overwrites
    perms_overwrite = channel_overwrites.get(member, discord.PermissionOverwrite())
    for role in member.roles:
        perms_overwrite = perms_overwrite.any(channel_overwrites.get(role, discord.PermissionOverwrite()))
    perms_in_channel = channel.permissions_for(member)
    
    # create embed
    embed = discord.Embed(
        color=discord.Color.red(),
        title="Permission Evaluation",
        description=f"For member: {member.display_name} `{member.id}`\nin channel: {channel.name} `{channel.id}`\nof guild: {channel.guild.name} `{channel.guild.id}`"
    )
    
    # check commands
    eval_res_cmd = None
    found_cmd = -1
    if do.startswith("/"):
        do = do.lstrip("/")
        eval_res, found = evaluate_permissions_to_embed(embed, "use_application_commands", perms_guild, perms_in_channel, perms_overwrite)
        eval_res_cmd, found_cmd = await evaluate_command_permission_to_embed(embed, do, member, channel, eval_res)
        eval_res = eval_res.both(eval_res_cmd)
    else:
        # evaluate guild and channel permissions
        eval_res, found = evaluate_permissions_to_embed(embed, do, perms_guild, perms_in_channel, perms_overwrite)
    
    # TODO found == 0 and found_cmd == 0 ERROR
    
    # send 'informative' message when no permission was found
    if 0 == found:
        await send_permission_list_embed(moi, do)
        return
    
    # finalize embed
    embed.colour = {
        True: discord.Color.green(),
        False: discord.Color.red(),
        None: discord.Color.yellow()
    }[eval_res.state]
    if 3 < found:
        embed.set_footer(text=f"Skipped {found - 3} more permission{"s" if 4 < found else ""}")
    
    try:
        await moi.send(ephemeral=False, embed=embed)
    except Exception as err:
        await moi.send(f"Couldn't send embed, do I have embed links permission?\n{err}")



@bot.command(name="pp&tos", help="Send links to privacy policy and terms of service.")
async def cmd_pptos(ctx: commands.Context):
    """Send PP and TOS links to chat"""
    print_cmd(ctx)
    await ctx.send("[Privacy Policy](https://fruchtba3r.github.io/FtD-Blueprint-Bot/datenschutz/)\n"
    "[Terms of Service](https://fruchtba3r.github.io/FtD-Blueprint-Bot/tos/)")



async def send_limited(sender: commands.Context|discord.User, text_list: list[str], sep="\n"):
    """Sends text_list in chunks of max 2000 chars (lines in text_list must not exceed limit)"""
    content = None
    for line in text_list:
        if content is None:
            content = line
            continue
        if 2000 > len(content) + len(line) + len(sep):
            content += sep + line
        else:
            await sender.send(content)
            content = line
    else:
        await sender.send(content)



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
    await send_limited(ownerUser, txt)



@bot.command(name="operms")
@commands.is_owner()
async def cmd_owner_perms(ctx: commands.Context, channel_id: str, member_id: str = "", filter: str = ""):
    """Lists (filtered) permissions for member/role in the channel. Or lists all roles.
    
    Parameters:
    channel_id: Channel ID
    member_id: optional Member ID
    filter: optional, only permissions listed where name starts with filter"""
    print_cmd(ctx)
    log.info(f"with args '{channel_id}' '{member_id}'")

    try:
        channel = bot.get_channel(int(channel_id))
    except Exception as err:
        ctx.send(str(err))
        return
    
    if "" == member_id:
        try:
            roles = await channel.guild.fetch_roles()
        except Exception as err:
            await ctx.send(str(err))
            return
        txt = [f"## Roles for: {channel.guild.name}"]+[f"{role.name}:`{role.id}`" for role in roles]
        
        await send_limited(ctx, txt)
        return
    
    try:
        member = await channel.guild.fetch_member(int(member_id))
    except Exception as err:
        try:
            member = await channel.guild.fetch_role(int(member_id))
        except Exception as err_role:
            await ctx.send(f"No Role or Member found\n{str(err)}\n{str(err_role)}")
            return
    
    perms = channel.permissions_for(member)
    txt = "\n".join([f"{perm}:{value}" for perm, value in iter(perms) if perm.startswith(filter)])
    await ctx.send(f"## Permissions for: {channel.guild.name} > {channel.name} > {member.name}\n" + txt)



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

    # make sure guild and channel actually exist
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
        mode = await guildconfig.ModeTransformer.convert(None, ctx, args[2])
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
    
    @staticmethod
    async def do_slash_command(*,
        create_gif: bool,
        interaction: discord.Interaction,
        blueprint: discord.Attachment,
        cut_side: float, 
        cut_top: float, 
        cut_front: float,
        no_color: bool, 
        timing: bool, 
        no_link: bool,
        aspect_ratio: str = "",
        firing_order: discord.app_commands.Choice[int] = 2,
    ):
        """Handles gif and image slash command"""
        # get and check mode
        mode = await check_mode(interaction)
        if mode is None:
            return
        # defer and 'think'
        moi = MessageOrInteraction(interaction)
        await moi.defer(ephemeral=(mode==GCM.Mode.PRIVATE), thinking=True)
        file, content = await process_attachment(
            moi, blueprint, timing,
            create_gif=create_gif,
            firing_order=firing_order,
            cut_side_top_front=(cut_side, cut_top, cut_front),
            use_player_colors=not no_color,
            force_aspect_ratio=get_aspect_ratio(aspect_ratio)
        )
        # finally
        if content is None and file is None:
            return
        if blueprint.url and not no_link:
            content = (content or "") + f"\n||{blueprint.url}||"
        await moi.send(content=content, file=file, ephemeral=(mode==GCM.Mode.PRIVATE))
    
    
    @discord.app_commands.command(name="img", description="Create image from blueprint.")
    @discord.app_commands.describe(
        blueprint="File",
        cut_side="Side cut. From 1.0 (closest, all) to 0.0",
        cut_top="Top cut. From 1.0 (closest, all) to 0.0",
        cut_front="Front cut. From 1.0 (closest, all) to 0.0",
        no_color="Disable custom ship color",
        timing="Show processing times",
        aspect_ratio="Output aspect ratio <x>:<y> e.g. 16:9",
        no_link="Do not put a download link to the blueprint in response"
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
        aspect_ratio: str = "",
        no_link: bool = False
    ):
        await SlashCmdGroup.do_slash_command(
            create_gif=False,
            interaction=interaction,
            blueprint=blueprint,
            cut_side=cut_side,
            cut_top=cut_top,
            cut_front=cut_front,
            no_color=no_color,
            timing=timing,
            aspect_ratio=aspect_ratio,
            no_link=no_link
        )


    @discord.app_commands.command(name="gif", description="Create gif from blueprint.")
    @discord.app_commands.describe(
        blueprint="File",
        firing_order="Order in which weapons are fired",
        cut_side="Side cut. From 1.0 (closest, all) to 0.0",
        cut_top="Top cut. From 1.0 (closest, all) to 0.0",
        cut_front="Front cut. From 1.0 (closest, all) to 0.0",
        no_color="Disable custom ship color",
        timing="Show processing times",
        no_link="Do not put a download link to the blueprint in response"
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
        timing: bool = False,
        no_link: bool = False
    ):
        if isinstance(firing_order, discord.app_commands.Choice):
            firing_order = firing_order.value
        await SlashCmdGroup.do_slash_command(
            create_gif=True,
            interaction=interaction,
            blueprint=blueprint,
            firing_order=firing_order,
            cut_side=cut_side,
            cut_top=cut_top,
            cut_front=cut_front,
            no_color=no_color,
            timing=timing,
            no_link=no_link
        )



@bot.tree.context_menu(name="Simple Blueprint")
@discord.app_commands.default_permissions(default_perms_app_command)
async def cm_print(interaction: discord.Interaction, message: discord.Message):
    if (await check_mode(interaction)) is None:
        return
    no_loop = True
    # only first 3 valid attachments will get processed
    for attachment in get_valid_attachments(message.attachments)[:3]:
        await SlashCmdGroup.slash_blueprint.callback(None, interaction, attachment, no_link=True)
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
        await SlashCmdGroup.slash_gif.callback(None, interaction, attachment, no_link=True)
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

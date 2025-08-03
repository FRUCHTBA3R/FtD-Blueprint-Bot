import json
import os
from discord import Guild, app_commands, Interaction
from discord.abc import GuildChannel
from discord.ext import commands
from enum import Enum
import logging

_log = logging.getLogger("bot")
GUILDCONFIG_FILE = "guildconfig.json"



class Mode(Enum):
    OFF = 0
    """no @mention, no slash cmds, no context menu, only needed commands"""
    ON = 1
    """responses to interactions are public, visible to all, @mention enabled"""
    MENTION = 2
    """deprecated"""
    PRIVATE = 3
    """default, responses to interactions are private, visible only to interaction user, @mention disabled"""



class ModeTransformer(app_commands.Transformer, commands.Converter):
    def get_choices(self):
        return [
            app_commands.Choice(name="off", value=Mode.OFF.name),
            app_commands.Choice(name="on", value=Mode.ON.name),
            app_commands.Choice(name="private", value=Mode.PRIVATE.name),
        ]
    choices = property(get_choices)

    async def transform(self, interaction: Interaction, value: str) -> Mode:
        # will only get a correct value from choices
        return Mode[value]

    async def convert(self, ctx: commands.Context, argument: str) -> Mode:
        # can get any string
        argument = argument.upper()
        if argument not in Mode._member_names_:
            return None
        return Mode[argument]



class GuildconfigManager():
    Mode = Mode

    def __init__(self):
        if not os.path.isfile(GUILDCONFIG_FILE):
            with open(GUILDCONFIG_FILE, "x") as f:
                f.write("{}")
            _log.info("Created guildconfig.json")
        with open(GUILDCONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                _log.error("<guildconfig> guildconfig.json unreadable.")
                config = {}
        self.config: dict[str, dict[str, int]] = config
        #self.modes = {"off": 0, "on": 1, "mention": 2}


    def __str__(self):
        return self.config.__str__()


##    def __getitem__(self, key):
##        """Get self.config[key] or self.config[key[0]][key[1]]..."""
##        d = self.config
##        if isinstance(key, tuple):
##            for k in key:
##                d = d[k]
##        else:
##            d = d[key]
##        if hasattr(d, "__setitem__"):
##            raise IndexError("Accessing lists/dicts/.. is not allowed. Use [keyA,keyB,..] or .get(key) instead.")
##        return d


##    def __setitem__(self, key, value):
##        """Set self.config[key] to value and save to file."""
##        d = self.config
##        if isinstance(key, tuple):
##            for i in range(len(key)-1):
##                k = key[i]
##                if k not in d:
##                    d[k] = {}
##                d = d[k]
##            key = key[-1]
##        d[key] = value
##        self.saveConfig()

    def __len__(self):
        return len(self.config)

    def __iter__(self):
        return self.config.__iter__()

    def __contains__(self, key):
        d = self.config
        if isinstance(key, tuple):
            for k in key:
                if not d.__contains__(k):
                    return False
                d = d[k]
            return True
        else:
            return d.__contains__(key)

    def get(self, key, default = None):
        """Returns self.config.get(key, default)."""
        return self.config.get(key, default)

    def setMode(self, guild: Guild, channel: GuildChannel, mode: Mode):
        """Set mode for channel of guild. Return True if success"""
        if guild is None or channel is None:
            return False
        guild_id = guild.id
        channel_id = channel.id
        if guild_id is None or channel_id is None:
            return False
        guild_id = str(guild_id)
        channel_id = str(channel_id)
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if type(mode) != Mode:
            return False
        self.config[guild_id][channel_id] = mode.value
        self.saveConfig()
        return True

    def getMode(self, guild: Guild, channel: GuildChannel) -> Mode | None:
        """Get mode for channel of guild. Defaults to PRIVATE if channel wasn't found or None if guild wasn't found."""
        if guild is None:
            return Mode.ON
        if channel is None:
            return None
        guild_id = guild.id
        channel_id = channel.id
        if guild_id is None or channel_id is None:
            return None
        g = self.config.get(str(guild_id))
        if g is None:
            return None
        return Mode(g.get(str(channel_id), Mode.PRIVATE.value))

    def getChannelsWithMode(self, guild: Guild|str|int, mode: Mode) -> list[str]:
        """Gets all channels of given guild with equal mode"""
        if type(guild) is Guild:
            guild = guild.id
        if type(guild) is int:
            guild = str(guild)
        if type(guild) is not str or type(mode) is not Mode:
            return []
        channels = self.config.get(guild)
        if channels is None:
            return []
        res = []
        for key, val in channels.items():
            if Mode(val) == mode:
                res.append(key)
        return res

    def removeGuild(self, guild: Guild):
        """Removes guild"""
        if guild is None:
            return False
        if str(guild.id) not in self.config:
            return False
        del self.config[str(guild.id)]
        self.saveConfig()
        return True

    def removeUnused(self, active_guilds: list[Guild]):
        """Remove guild configurations if id is not in active_guilds list.
        Returns number of removed guilds."""
        if active_guilds is None or len(active_guilds) == 0:
            return 0
        for guild in active_guilds:
            if str(guild.id) in self.config:
                self.config[str(guild.id)]["active"] = 1
        count = 0
        for key in list(self.config.keys()):
            if "active" in self.config[key]:
                del self.config[key]["active"]
            else:
                del self.config[key]
                count += 1
        if count > 0:
            self.saveConfig()
        return count

    def saveConfig(self):
        """Save config to file"""
        with open(GUILDCONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent="\t")



if __name__ == "__main__":
    print("Guildconfig Manager Test")
    GUILDCONFIG_FILE = "guildconfig_test.json"
    with open(GUILDCONFIG_FILE, "w") as f:
        pass
    GCM = GuildconfigManager()
    GCM["g1"] = "one"
    GCM["g2"] = {}
    GCM["g2","c1"] = 0
    GCM["g2","c2"] = 1
    GCM["g2","c3","a","b"] = "ab"
    try:
        GCM["g2"]["c3"] = 2
    except IndexError as err:
        print(err)
    print(GCM["g2","c1"])
    print(GCM)
    print("g2" in GCM)
    print([(i,k) for i,k in enumerate(GCM)])
    print("len", len(GCM))

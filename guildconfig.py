import json

GUILDCONFIG_FILE = "guildconfig.json"


class GuildconfigManager():
    def __init__(self):
        with open(GUILDCONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                print("[ERR] <guildconfig> guildconfig.json unreadable.")
                config = {}
        self.config = config
        self.modes = {"off": 0, "on": 1, "mention": 2}
    
    
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

    def get(self, key):
        """Get self.config[key]."""
        return self.config[key]

    def setMode(self, guild, channel, mode):
        """Set mode (int or str) for channel of guild. Return True if success"""
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
        if type(mode) != int:
            mode = self.modes.get(mode)
        elif mode not in range(3):
            mode = None
        if mode is None:
            return False
        self.config[guild_id][channel_id] = mode
        self.saveConfig()
        return True

    def getMode(self, guild, channel):
        """Get mode (int) for channel of guild."""
        if guild is None:
            return self.modes["on"]
        if channel is None:
            return None
        guild_id = guild.id
        channel_id = channel.id
        if guild_id is None or channel_id is None:
            return None
        g = self.config.get(str(guild_id))
        if g is None:
            return None
        return g.get(str(channel_id))

    def removeGuild(self, guild):
        """Removes guild"""
        if guild is None:
            return False
        if str(guild.id) not in self.config:
            return False
        del self.config[str(guild.id)]
        self.saveConfig()
        return True

    def removeUnused(self, active_guilds):
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

# FtD-Blueprint-Bot
***This readme is still beeing worked on***

Discord bot for the game [From The Depths](https://fromthedepthsgame.com/) which creates top, front and side view of an uploaded .blueprint file.

### Quick Guide
You can use the following keywords in your upload message:
- `gif [rand|random]` to create a front-to-back (or random) firing animation.
- `cut [<side> [<top> [<front>]]]` where `<side>`, `<top>` and `<front>` are floating point numbers from 0 to 1. This will create a cross section view. Using only `cut` is the same as `cut 0.5`, cutting only the side view at half depth.
- `noc|nocol|nocolor` to not show the color of painted blocks.
- `stats|time` to show how long different stages of processing the blueprint took.

### Installation
Add it to your server with this [invite link](https://discord.com/api/oauth2/authorize?client_id=759429992521662464&permissions=34880&scope=bot).

### Configuration
The bot has three modes:
- "on": Any uploaded [valid blueprint file](#supported-file-formats) will be converted to an image.
- "mention": Only uploads which mention the bot (@FtD BluePrinter Bot) will be converted.
- "off": Turned off in current channel. Only [bp!print](#commands) will convert the last uploaded blueprint.

The default mode for each guild channel is "mention".
To change the current mode of a channel write `bp!mode <on|mention|off>` to the channel (requires you to have channel management permission).

The mode for direct messages is "on". This can not be changed.

### Commands
List of all commands:
- `bp!help`
- `bp!print`
- `bp!mode`

Only-for-me commands:
- `bp!test`

### Supported file formats
Bot will only accept *.blueprint*, *.blueprint_ba* and *.blueprint_bac* files.

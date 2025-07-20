# FtD-Blueprint-Bot
<picture>
  <img src="/example/PreDread_Example_Screenshot.png" alt="Ship Screenshot" style="height:300px">
</picture>
<picture>
  <img src="/example/PreDread_Example_view.gif" alt="Ship Blueprint" style="height:300px">
</picture>

Discord bot for the game [From The Depths](https://fromthedepthsgame.com/) which creates top, front and side view of an uploaded .blueprint file.

### Important / Upcoming Changes
Introducing slash commands! (better later than never) <br/>
Un-introducing bp!print and the active listening mode.

As the bot does not have access to all message content anymore, just uploading your blueprint file to a channel with mode `on` will not work. Instead you'll have to *@mention* the bot in your upload message. Or just use `/blueprint`, it will show you all possible arguments right at your fingertips.

When using the slash command, uploaded files will not be available for other users in the channel. But sharing is caring, so next to *@mention*, I am planning to add a right click context menu that can be used on any message with a blueprint (maybe it will even be interactive). This will be an effective replacement for bp!print.

#### Slash Commands Not Showing Up?
Check your server settings -> Apps/Integrations -> Bots and Apps -> FtD Blueprint to Img , if the permissions are set correctly \[[SUGGESTION](#suggested-server-config)\]. If there are no slash commands listed there, you probably have to reinvite the bot to your server. After that, make sure to reload Discord: `ctrl + r` for the app or refresh for the browser AND reconfigure the mode for channels, if you don't want them to all be `private`.<br/>
Still no slash commands? Call Houston. Nah, create an Issue or contact me on Discord.

#### Suggested Server Config
I would suggest giving everyone who is allowed to read/write messages the permission to use `/blueprint` in every channel. As the default mode is `private` no messages will show up publicly.
Set one or more channels to mode `on` for users to share their files and images.<br/>
The `/mode` command will always only be available to users with **manage channels** permission, so you shouldn't have to worry about setting up any permissions for it.

### Quick Guide
Use `/blueprint img|gif` to create an image or a gif from your file.

Or: You can use the following keywords in your upload message which has to *@mention* the bot:
- `gif [rand|random]` to create a front-to-back (or random) firing animation.
- `cut [<side> [<top> [<front>]]]` where `<side>`, `<top>` and `<front>` are floating point numbers from 0 to 1. This will create a cross section view. Using only `cut` is the same as `cut 0.5`, cutting only the side view at half depth.
- `noc|nocol|nocolor` to not show the color of painted blocks.
- `stats|time` to show how long different stages of processing the blueprint took.
- `<number>:<number>` to set an aspect ratio for the image (e.g. 16:9). Doesn't work with gifs.

### Installation
Add it to your server [here](https://fruchtba3r.github.io/FtD-Blueprint-Bot/).

### Configuration
The bot has three modes:
- `on`: Slash commands and context menu responses will be visible for all users. Any message mentioning the bot with an uploaded [valid blueprint file](#supported-file-formats) will be converted to an image.
- ~~`mention`: Only uploads which mention the bot (@FtD BluePrinter Bot) will be converted.~~
- `private`: Slash commands and context menu responses will only be visible for the user. The bot will not react to being mentioned.
- `off`: Turned off in current channel.

The default mode for each guild channel is `private`.
To change the current mode of a channel use `/mode` or write `bp!mode <on|mention|off>` and *@mention* the bot to the channel. This requires you to have **channel management** permission.

The mode for direct messages is "on". This can not be changed.

### Commands
List of all commands (these require *@mentioning* the bot):
- `bp!help`
- ~~`bp!print`~~
- `bp!mode`

### Supported file formats
Bot will only accept *.blueprint*, *.blueprint_ba* and *.blueprint_bac* files.

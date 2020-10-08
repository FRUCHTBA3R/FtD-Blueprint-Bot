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
    if message.author == bot.user:
        return

    for attachm in message.attachments:
        if attachm.filename.endswith(".blueprint"):
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
            combined_img_file = bp_to_imgV2.process_blueprint(filename)
            #files
            file = discord.File(combined_img_file)
            #upload
            await message.channel.send(file=file)
            #delete files
            os.remove(combined_img_file)
            os.remove(filename)
            
    await bot.process_commands(message)

#command testing
@bot.command(name="print", help="testing print")
async def cmd_print(ctx):
    await ctx.send("print test")



bot.run(TOKEN)

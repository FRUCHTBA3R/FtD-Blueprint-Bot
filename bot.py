import os

import bp_to_img

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BP_FOLDER = os.getenv("BLUEPRINT_FOLDER")

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
        #print("Self response suppressed")
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
            bp_name, img_file_front, img_file_top, img_file_side = bp_to_img.print_blueprint(filename)
            #files
            markspoiler=False
            file_front = discord.File(img_file_front, filename="Front of " + bp_name + ".png",
                                      spoiler=markspoiler)
            file_top = discord.File(img_file_top, filename="Top of " + bp_name + ".png",
                                      spoiler=markspoiler)
            file_side = discord.File(img_file_side, filename="Side of " + bp_name + ".png",
                                      spoiler=markspoiler)
            #upload
            await message.channel.send(files=[file_front, file_top, file_side])
            #delete files
            os.remove(img_file_front)
            os.remove(img_file_top)
            os.remove(img_file_side)
            os.remove(filename)
            
    await bot.process_commands(message)
    
@bot.command(name="print", help="testing print")
async def cmd_print(ctx):
    await ctx.send("i shall print")



bot.run(TOKEN)

import logging.config
import os
import logging
from dotenv import load_dotenv
from discord import Object as dObject
from discord import Intents as dIntents
from discord.utils import _ColourFormatter

load_dotenv()

DO_DEBUG = os.getenv("DO_DEBUG")
BP_FOLDER = os.getenv("BLUEPRINT_FOLDER")
if DO_DEBUG:
    TOKEN = lambda: os.getenv("DISCORD_TOKEN_DEBUG")
    DEBUG_SERVER = dObject(os.getenv("DEBUG_SERVER_ID"))
else:  # load encrypted credential provided with systemd-creds
    def __token():
        with open(os.getenv("CREDENTIALS_DIRECTORY") + "/discord_token", "r") as f:
            return f.read()
    TOKEN = __token

# create bp_folder
if not os.path.exists(BP_FOLDER):
    os.mkdir(BP_FOLDER)

def get_bot_intents():
    res = dIntents()
    res.messages = True
    res.typing = True
    res.reactions = True
    res.guilds = True
    # for compatibility, will be removed soon TODO
    res.message_content = True
    return res

# add file:lineno to console when debugging, change levelname length to 4
_ColourFormatter.FORMATS = {
    level: logging.Formatter(
        f'\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-4s\x1b[0m {"%(filename)s:%(lineno)d " if DO_DEBUG else ""}\x1b[35m%(name)s\x1b[0m %(message)s',
        '%Y-%m-%d %H:%M:%S',
    )
    for level, colour in _ColourFormatter.LEVEL_COLOURS
}

# class _VerboseColourFormatter(_ColourFormatter):
#     FORMATS = {
#         level: logging.Formatter(
#             f'\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-4s\x1b[0m %(filename)s:%(lineno)d \x1b[35m%(name)s\x1b[0m %(message)s',
#             '%Y-%m-%d %H:%M:%S',
#         )
#         for level, colour in _ColourFormatter.LEVEL_COLOURS
#     }

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "class": "discord.utils._ColourFormatter"
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DO_DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "bot": {
            "handlers": ["console"],
            "level": "DEBUG" if DO_DEBUG else "INFO",
            "propagate": False
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logging.addLevelName(logging.DEBUG, "DBUG")
logging.addLevelName(logging.INFO, "INFO")
logging.addLevelName(logging.WARNING, "WARN")
logging.addLevelName(logging.ERROR, "EROR")
logging.addLevelName(logging.CRITICAL, "CRIT")
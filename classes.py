import discord
from discord import ui
from typing import Optional

from guildconfig import Mode
from numpy.random import randint
import re
import logging

_log = logging.getLogger("bot")

firing_order_options = [
    {"name": "Front to Back", "value": 2, "default": True},
    {"name": "Random", "value": -1},
    {"name": "All at once", "value": -2},
    {"name": "Back to Front", "value": 5},
    {"name": "Top to Bottom", "value": 1},
    {"name": "Bottom to Top", "value": 4},
    {"name": "Left to Right", "value": 3},
    {"name": "Right to Left", "value": 0},
]

aspect_ratio_options = {
    "HDTV 16:9":"16:9",
    "SDTV 4:3":"4:3",
    "Square 1:1":"1:1",
    "Camera 3:2":"3:2",
    "Ultra Wide 21:9":"21:9",
    "Movie 16:10":"16:10",
    "Smartphone 6:13":"6:13"
}

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

    async def send(self, content: Optional[str] = None, file: Optional[discord.File] = None, ephemeral: bool = True, **kwargs):
        """Sends to channel of message or responds to interaction or sends followups to interaction"""
        #kwargs = {}
        if content is not None: kwargs["content"] = content
        if file is not None: kwargs["file"] = file
        
        if self.isMessage():
            moi: discord.Message = self.moi
            await moi.channel.send(**kwargs)
        elif self.isInteraction():
            moi: discord.Interaction = self.moi
            if not moi.response.is_done():
                await moi.response.send_message(**kwargs, ephemeral=ephemeral)
            else:
                if "delete_after" in kwargs: del kwargs["delete_after"]
                await moi.followup.send(**kwargs, ephemeral=ephemeral)
        else:
            raise TypeError("Did not get discord.Message or discord.Interaction")

    async def defer(self, ephemeral: bool, thinking: bool) -> bool:
        """defers if interaction and not responded"""
        if self.isInteraction():
            self.moi: discord.Interaction
            if not self.moi.response.is_done():
                await self.moi.response.defer(ephemeral=ephemeral, thinking=thinking)
                return True
        return False

    async def edit_message(self, **kwargs):
        """edits interaction response or message"""
        if self.isInteraction():
            await self.moi.response.edit_message(**kwargs)
        elif self.isMessage():
            self.moi: discord.Message
            await self.moi.edit(**kwargs)
        else:
            raise TypeError("Did not get discord.Message or discord.Interaction")



class StoringSelect(ui.Select):
    """ui.Select with auto storing"""

    def store_selection(self: ui.Select):
        """Assigns selected value as default value, so view doesn't reset on edit"""
        for option in self.options:
            option.default = (option.value in self.values)

    async def callback_stored(self):
        ...

    async def callback(self, interaction: discord.Interaction):
        """Callback which stores selection, defers interaction response and calls callback_stored"""
        try:
            await interaction.response.defer()
        except:
            _log.warning("Deferring interaction response failed")
            # just continue anyway
        self.store_selection()
        await self.callback_stored()


class FileSelect(StoringSelect):
    """Select dropdown for files"""
    def __init__(self, filenames: list[str]):
        options = [
            discord.SelectOption(
                label=name,
                value=str(i),
            )
            for i, name in enumerate(filenames)
        ]
        super().__init__(
            placeholder="Select attachments (max 3)",
            min_values=1,
            max_values=3,
            options=options,
            row=0
        )
    
    async def callback_stored(self):
        self.view: InteractiveBlueprint
        self.view.selected_files = [int(v) for v in self.values]


class FiringOrderSelect(StoringSelect):
    """Select dropdown for firing order"""
    def __init__(self):
        options = [
            discord.SelectOption(
                label=elem["name"],
                value=str(elem["value"]),
                default=elem.get("default", False)
            )
            for elem in firing_order_options
        ]
        super().__init__(
            row=2,
            placeholder="Firing order for gif",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback_stored(self):
        self.view: InteractiveBlueprint
        self.view.firing_order = int(self.values[0])


class AspectRatioSelect(StoringSelect):
    """
    Select dropdown for an assortment of aspect ratios"""
    def __init__(self):
        options = [discord.SelectOption(label="Aspect ratio: Unchanged", value="None", default=True)] + [
            discord.SelectOption(
                label=key,
                value=val,
                default=False
            )
            for key, val in aspect_ratio_options.items()
        ]
        self.custom_option = discord.SelectOption(label="Custom Aspect Ratio", value="custom", default=True)
        self.custom_value = ""
        super().__init__(
            row=2,
            placeholder="Aspect ratio",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback_stored(self):
        self.view: InteractiveBlueprint
        if self.values[0] == "None":
            self.view.aspect_ratio_string = ""
            self.view.children[1].style = discord.ButtonStyle.blurple
        elif self.values[0] == "custom":
            self.view.aspect_ratio_string = self.custom_value
            self.view.children[1].style = discord.ButtonStyle.green
        else:
            self.view.aspect_ratio_string = self.values[0]
            self.view.children[1].style = discord.ButtonStyle.grey
        await self.view.redraw()

    def set_to_custom(self):
        self.custom_value = self.view.aspect_ratio_string
        self.custom_option.label = f"Custom Aspect Ratio: {self.custom_value}"
        for option in self.options:
            option.default = False
        if self.custom_option not in self.options:
            self.append_option(self.custom_option)
        else:
            self.custom_option.default = True


class ImageTypeSelect(StoringSelect):
    """Select dropdown for image type"""
    def __init__(self):
        options=[
            discord.SelectOption(label="Image", value="img", default=True),
            discord.SelectOption(label="Gif", value="gif")
        ]
        super().__init__(
            placeholder="Image type",
            row=1,
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback_stored(self):
        self.view: InteractiveBlueprint
        self.view.create_gif = self.values[0] == "gif"
        # switch firing_order_select and aspect_ratio_select visibility
        if "img" == self.values[0]:
            self.view.create_gif = False
            self.view.remove_item(self.view.firing_order_select)
            self.view.add_item(self.view.aspect_ratio_select)
        else:
            self.view.create_gif = True
            self.view.remove_item(self.view.aspect_ratio_select)
            self.view.add_item(self.view.firing_order_select)
        await self.view.redraw()#interaction)


# views don't support text input, so here's a modal
class CutModal(ui.Modal, title="Cut Side Top Front"):
    cut_side = ui.TextInput(
        label="Side",
        style=discord.TextStyle.short,
        placeholder="1.0 to 0.0",
        required=False,
        max_length=4
    )
    cut_top = ui.TextInput(
        label="Top",
        style=discord.TextStyle.short,
        placeholder="1.0 to 0.0",
        required=False,
        max_length=4
    )
    cut_front = ui.TextInput(
        label="Front",
        style=discord.TextStyle.short,
        placeholder="1.0 to 0.0",
        required=False,
        max_length=4
    )
    re_pattern = re.compile(r"([01]?[,.]\d{0,3}|[01])")
    def convert_value(self, value: str) -> float | None:
        if value == "":
            value = None
        res = value and self.re_pattern.search(value)
        if res:
            res = float(res.groups()[0].replace(",", "."))
        return res
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except:
            _log.warning("Cut modal could not defer response")
        cut_side = self.convert_value(self.cut_side.value)
        cut_top = self.convert_value(self.cut_top.value)
        cut_front = self.convert_value(self.cut_front.value)
        self.result = (cut_side, cut_top, cut_front)


# and another one
class AspectRatioModal(ui.Modal, title="Custom Aspect Ratio"):
    aspect_ratio = ui.TextInput(
        label="Aspect ratio",
        style=discord.TextStyle.short,
        placeholder="e.g. 12:9",
        required=True,
        max_length=11
    )
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except:
            _log.warning("Aspect ratio modal could not defer response")
        self.result = self.aspect_ratio.value


# modals only support text inputs, so view it is
class InteractiveBlueprint(ui.View):
    """Interactive blueprint creation view for context menu"""

    def __init__(self, mode: Mode, attachment_names: list[str], *, timeout = 180):
        super().__init__(timeout=timeout)
        if len(attachment_names) == 0:
            self.stop()
            return
        self.__mode = mode
        self.original_message: discord.InteractionMessage = None

        # row 0: File Select or Empty
        _log.debug(f"Got filenames: {attachment_names}")
        if len(attachment_names) > 1:
            self.file_select = FileSelect(attachment_names)
            self.add_item(self.file_select)
        # row 1: Image Type Select
        self.image_type_select = ImageTypeSelect()
        self.add_item(self.image_type_select)
        # row 2: Aspect Ratio Select or Firing Order Select, when gif is selected
        self.firing_order_select = FiringOrderSelect()
        self.aspect_ratio_select = AspectRatioSelect()
        self.add_item(self.aspect_ratio_select)
        # row 3: Cut Button and Custom Aspect Ratio Button
        # row 4: Toggle Color Button, Toggle Timing Button and Create Button

        # default result
        self.selected_files = [0]
        self.do_timing = False
        self.create_gif = False
        self.firing_order = firing_order_options[0]["value"]
        self.cut_side_top_front: tuple[float|None,float|None,float|None] = (None, None, None)
        self.use_player_colors = True
        self.aspect_ratio_string = ""

    async def show(self, interaction: discord.Interaction):
        """Show this view as response to interaction, always ephemeral"""
        try:
            await interaction.response.send_message(view=self, ephemeral=True)
            self.original_message = await interaction.original_response()
        except Exception as err:
            _log.warning("Could't show view InteractiveBlueprint: %s", err)
            self.stop()

    async def redraw(self):#, moi: MessageOrInteraction| discord.Message | discord.Interaction):
        if self.original_message is None:
            raise Exception("InteractiveBlueprint has no original message, was .show() called?")
        try:
            await self.original_message.edit(view=self)
        except Exception as err:
            _log.error("InteractiveBlueprint redraw failed: %s", err)
            self.stop()


    @ui.button(
            label="Cut",
            style=discord.ButtonStyle.blurple,
            row=3
    )
    async def on_cut_button(self, interaction: discord.Interaction, button: ui.Button):
        cut_modal = CutModal(timeout=60)
        try:
            await interaction.response.send_modal(cut_modal)
        except:
            _log.warning("Cut button could not show modal")
            return
        if not await cut_modal.wait():
            # not timed out
            self.cut_side_top_front = cut_modal.result
        # set button text to include values
        button.label = "Cut"
        if self.cut_side_top_front[0] is not None:
            button.label += f" Side {self.cut_side_top_front[0]:.2f}"
        if self.cut_side_top_front[1] is not None:
            button.label += f" Top {self.cut_side_top_front[1]:.2f}"
        if self.cut_side_top_front[2] is not None:
            button.label += f" Front {self.cut_side_top_front[2]:.2f}"
        await self.redraw()


    @ui.button(
            label="Custom Aspect Ratio",
            style=discord.ButtonStyle.blurple,
            row=3
    )
    async def on_aspect_button(self, interaction: discord.Interaction, button: ui.Button):
        aspect_modal = AspectRatioModal(timeout=60)
        try:
            await interaction.response.send_modal(aspect_modal)
        except:
            _log.warning("Aspect button could not show modal")
            return
        if not await aspect_modal.wait():
            # not timed out
            self.aspect_ratio_string = aspect_modal.result
            button.style = discord.ButtonStyle.green
            self.aspect_ratio_select.set_to_custom()
            await self.redraw()


    @ui.button(
            label="Player Colors",
            style=discord.ButtonStyle.green,
            row=4
    )
    async def on_color_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await interaction.response.defer()
        except:
            _log.warning("Color button could not defer response")
        self.use_player_colors = not self.use_player_colors
        if self.use_player_colors:
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.grey
        await self.redraw()


    @ui.button(
            label="Timing",
            style=discord.ButtonStyle.grey,
            row=4
    )
    async def on_timing_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await interaction.response.defer()
        except:
            _log.warning("Timing button could not defer response")
        self.do_timing = not self.do_timing
        if self.do_timing:
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.grey
        await self.redraw()


    @ui.button(
        label="Create",
        style=discord.ButtonStyle.danger,
        row=4
    )
    async def on_submit_button(self, interaction: discord.Interaction, button: ui.Button):
        content = ["Raising Anchor ...", "CRAMing Shells ...", "Obfuscating PID ...", "Unspinning Spin-Blocks ..."]
        try:
            await interaction.response.edit_message(
                content=content[randint(0, len(content))],
                delete_after=1,
                view=None
            )
        except:
            _log.warning("Submit button could not edit response")
        self.stop()

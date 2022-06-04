import json
import math

from PIL import ImageFont, ImageDraw, Image

# load font
bahnschrift = ImageFont.truetype("bahnschrift.ttf", 30)
bahnschrift.set_variation_by_axes([300, 85])  # start at 75, the smallest width


def generate():
    """Generate legend image from materials configuration."""
    # load material file
    with open("materials.json", "r") as f:
        materials = json.load(f)

    # font setup
    max_width = 0
    for k in materials:
        # get size
        max_width = max(max_width, bahnschrift.getlength(k, "L"))

    max_width = math.ceil(max_width)
    max_height, max_baseline = bahnschrift.getmetrics()
    max_height += max_baseline

    # image setup
    front_space = 15
    back_space = 10
    top_space = 15
    bottom_space = 15
    background_color = [255, 118, 33]  # "blueprint" blue
    img_size = (front_space + max_height + 5 + max_width + back_space,
                top_space + max(len(materials) - 1, 0) * 5 + len(materials) * max_height + bottom_space)
    pilimg = Image.new("RGB", img_size, tuple(background_color[::-1]))
    draw = ImageDraw.Draw(pilimg)

    # image creation
    current_y = top_space
    text_loc_x = front_space + max_height + 5
    for k in materials:
        # fill square with material color
        draw.rectangle((front_space, current_y, front_space+max_height, current_y+max_height),
                       fill=tuple(materials[k]["Color"][::-1]))
        # text
        #width = bahnschrift.getlength(k, "L")
        #bahnschrift.set_variation_by_axes([300, max_width / width * 75])
        draw.text((text_loc_x, current_y), k, font=bahnschrift)
        # next
        current_y += 5 + max_height

    # show / save
    #pilimg.show()
    pilimg.save("legend.png")


if __name__ == "__main__":
    generate()
    exit()

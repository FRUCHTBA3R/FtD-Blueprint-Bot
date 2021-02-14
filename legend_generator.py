import json
import numpy as np
import cv2


def generate():
    """Generate legend image from materials configuration."""
    # load material file
    with open("materials.json", "r") as f:
        materials = json.load(f)

    # font setup
    fontFace = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.8 #0.4375  # as seen in bp_to_img > __create_images

    max_width = 0
    max_height = 0
    max_baseline = 0
    for k in materials:
        # get size
        (width, height), baseline = cv2.getTextSize(k, fontFace, fontScale, 2)
        height += baseline
        max_width = max(max_width, width)
        max_height = max(max_height, height)
        max_baseline = max(max_baseline, baseline)

    # image setup
    front_space = 15
    back_space = 10
    top_space = 15
    bottom_space = 15
    background_color = np.array([255, 118, 33])  # "blueprint" blue
    img_size = (top_space + max(len(materials) - 1, 0) * 5 + len(materials) * max_height + bottom_space,
                front_space + max_height + 5 + max_width + back_space,
                3)
    img = np.full(img_size, background_color, dtype=np.uint8)

    # image creation
    current_y = top_space
    text_loc_x = front_space + max_height + 5
    text_loc_y = max_height - max_baseline
    for k in materials:
        # fill square with material color
        img[current_y:current_y+max_height, front_space:front_space+max_height] = materials[k]["Color"]
        # put text
        cv2.putText(img, k, (text_loc_x, current_y + text_loc_y), fontFace, fontScale, (255, 255, 255), 2)
        # next
        current_y += 5 + max_height

    # show / save
    cv2.imwrite("legend.png", img)


if __name__ == "__main__":
    generate()
    exit()

from PIL import ImageFont
import matplotlib.pyplot as plt
import numpy as np
from numpy.polynomial.polynomial import Polynomial


def get_text_length_and_metric(text, font_size, variation=[300, 85]):
    # load font
    font = ImageFont.truetype("bahnschrift.ttf", font_size)
    font.set_variation_by_axes(variation)
    return font.getlength(text, "L"), font.getmetrics()


def collect_data(text, font_size_start, font_size_end):
    res_length = np.zeros(font_size_end - font_size_start + 1, dtype=float)
    res_height = np.zeros(font_size_end - font_size_start + 1, dtype=float)
    for i in range(font_size_end - font_size_start + 1):
        font_size = font_size_start + i
        res_length[i], metric = get_text_length_and_metric(text, font_size)
        res_height[i] = metric[0] + metric[1]
    return res_length, res_height


def multi_height_plt(text_list, font_size_start, font_size_end):
    x = np.arange(font_size_start, font_size_end + 1)
    for elem in text_list:
        length, _ = collect_data(elem, font_size_start, font_size_end)
        plt.plot(x, length, label=elem)
        plt.legend()
    plt.show()


def ratio_multi_plt(text_list, font_size_start, font_size_end, font_size_compare):
    x = np.arange(font_size_start, font_size_end + 1)
    for elem in text_list:
        length, _ = collect_data(elem, font_size_start, font_size_end)
        compare_length, _ = get_text_length_and_metric(elem, font_size_compare)
        f = x * compare_length / font_size_compare
        poly = Polynomial.fit(x, length, 1, domain=[0, font_size_end + 1], window=[0, font_size_end + 1])
        print(poly, "\n", compare_length / font_size_compare)
        print()
        plt.plot(x, poly(x), color="black")
        plt.plot(x, x * compare_length / font_size_compare, color="red")
        plt.plot(x, length, ".", label=elem if len(elem) < 11 else elem[:11])
        plt.legend()
    plt.show()


def compare_length(text_list, font_size):
    for elem in text_list:
        length_dense, _ = get_text_length_and_metric(elem, font_size, [300, 75])
        length_sparse, _ = get_text_length_and_metric(elem, font_size, [300, 100])
        print(length_dense / length_sparse * 100)


texts = ["Ich liebe Kuchen.",
         "Levi haart sehr viel.",
         "3.14156",
         "Keks ist ganz schön schwer.",
         "123141414 42543656454",
         "123141414142543656454",
         "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet."]
ratio_multi_plt(texts, 0, 100, 20)
compare_length(texts, 30)
# results:
# width scales length linear
# font size scales length linear,
# approximation with lower font size overestimates length of bigger font sizes (that's good)

# -*- coding: utf-8 -*-
"""
ANSI escape code utilities, see
http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-048.pdf
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd-party libs
from salt.ext import six

graph_prefix = "\x1b["
graph_suffix = "m"
codes = {
    "reset": "0",
    "bold": "1",
    "faint": "2",
    "italic": "3",
    "underline": "4",
    "blink": "5",
    "slow_blink": "5",
    "fast_blink": "6",
    "inverse": "7",
    "conceal": "8",
    "strike": "9",
    "primary_font": "10",
    "reset_font": "10",
    "font_0": "10",
    "font_1": "11",
    "font_2": "12",
    "font_3": "13",
    "font_4": "14",
    "font_5": "15",
    "font_6": "16",
    "font_7": "17",
    "font_8": "18",
    "font_9": "19",
    "fraktur": "20",
    "double_underline": "21",
    "end_bold": "21",
    "normal_intensity": "22",
    "end_italic": "23",
    "end_fraktur": "23",
    "end_underline": "24",  # single or double
    "end_blink": "25",
    "end_inverse": "27",
    "end_conceal": "28",
    "end_strike": "29",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "extended": "38",
    "default": "39",
    "fg_black": "30",
    "fg_red": "31",
    "fg_green": "32",
    "fg_yellow": "33",
    "fg_blue": "34",
    "fg_magenta": "35",
    "fg_cyan": "36",
    "fg_white": "37",
    "fg_extended": "38",
    "fg_default": "39",
    "bg_black": "40",
    "bg_red": "41",
    "bg_green": "42",
    "bg_yellow": "44",
    "bg_blue": "44",
    "bg_magenta": "45",
    "bg_cyan": "46",
    "bg_white": "47",
    "bg_extended": "48",
    "bg_default": "49",
    "frame": "51",
    "encircle": "52",
    "overline": "53",
    "end_frame": "54",
    "end_encircle": "54",
    "end_overline": "55",
    "ideogram_underline": "60",
    "right_line": "60",
    "ideogram_double_underline": "61",
    "right_double_line": "61",
    "ideogram_overline": "62",
    "left_line": "62",
    "ideogram_double_overline": "63",
    "left_double_line": "63",
    "ideogram_stress": "64",
    "reset_ideogram": "65",
}


class TextFormat(object):
    """
    ANSI Select Graphic Rendition (SGR) code escape sequence.
    """

    def __init__(self, *attrs, **kwargs):
        """
        :param attrs: are the attribute names of any format codes in `codes`

        :param kwargs: may contain

        `x`, an integer in the range [0-255] that selects the corresponding
        color from the extended ANSI 256 color space for foreground text

        `rgb`, an iterable of 3 integers in the range [0-255] that select the
        corresponding colors from the extended ANSI 256^3 color space for
        foreground text

        `bg_x`, an integer in the range [0-255] that selects the corresponding
        color from the extended ANSI 256 color space for background text

        `bg_rgb`, an iterable of 3 integers in the range [0-255] that select
        the corresponding colors from the extended ANSI 256^3 color space for
        background text

        `reset`, prepend reset SGR code to sequence (default `True`)

        Examples:

        .. code-block:: python

            red_underlined = TextFormat('red', 'underline')

            nuanced_text = TextFormat(x=29, bg_x=71)

            magenta_on_green = TextFormat('magenta', 'bg_green')
            print(
                '{0}Can you read this?{1}'
                ).format(magenta_on_green, TextFormat('reset'))
        """
        self.codes = [
            codes[attr.lower()] for attr in attrs if isinstance(attr, six.string_types)
        ]

        if kwargs.get("reset", True):
            self.codes[:0] = [codes["reset"]]

        def qualify_int(i):
            if isinstance(i, int):
                return i % 256  # set i to base element of its equivalence class

        def qualify_triple_int(t):
            if isinstance(t, (list, tuple)) and len(t) == 3:
                return qualify_int(t[0]), qualify_int(t[1]), qualify_int(t[2])

        if kwargs.get("x", None) is not None:
            self.codes.extend((codes["extended"], "5", qualify_int(kwargs["x"])))
        elif kwargs.get("rgb", None) is not None:
            self.codes.extend((codes["extended"], "2"))
            self.codes.extend(*qualify_triple_int(kwargs["rgb"]))

        if kwargs.get("bg_x", None) is not None:
            self.codes.extend((codes["extended"], "5", qualify_int(kwargs["bg_x"])))
        elif kwargs.get("bg_rgb", None) is not None:
            self.codes.extend((codes["extended"], "2"))
            self.codes.extend(*qualify_triple_int(kwargs["bg_rgb"]))

        # pylint: disable=string-substitution-usage-error
        self.sequence = "%s%s%s" % (graph_prefix, ";".join(self.codes), graph_suffix,)
        # pylint: enable=string-substitution-usage-error

    def __call__(self, text, reset=True):
        """
        Format :param text: by prefixing `self.sequence` and suffixing the
        reset sequence if :param reset: is `True`.

        Examples:

        .. code-block:: python

            green_blink_text = TextFormat('blink', 'green')
            'The answer is: {0}'.format(green_blink_text(42))
        """
        end = TextFormat("reset") if reset else ""
        return "%s%s%s" % (self.sequence, text, end)  # pylint: disable=E1321

    def __str__(self):
        return self.sequence

    def __repr__(self):
        return self.sequence

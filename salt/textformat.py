# -*- coding: utf-8 -*-
'''
ANSI escape code utilities, see
http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-048.pdf
'''
from __future__ import absolute_import

# Import 3rd-party libs
from salt.ext import six

graph_prefix = u'\x1b['
graph_suffix = u'm'
codes = {
    u'reset': u'0',

    u'bold': u'1',
    u'faint': u'2',
    u'italic': u'3',
    u'underline': u'4',
    u'blink': u'5',
    u'slow_blink': u'5',
    u'fast_blink': u'6',
    u'inverse': u'7',
    u'conceal': u'8',
    u'strike': u'9',

    u'primary_font': u'10',
    u'reset_font': u'10',
    u'font_0': u'10',
    u'font_1': u'11',
    u'font_2': u'12',
    u'font_3': u'13',
    u'font_4': u'14',
    u'font_5': u'15',
    u'font_6': u'16',
    u'font_7': u'17',
    u'font_8': u'18',
    u'font_9': u'19',
    u'fraktur': u'20',

    u'double_underline': u'21',
    u'end_bold': u'21',
    u'normal_intensity': u'22',
    u'end_italic': u'23',
    u'end_fraktur': u'23',
    u'end_underline': u'24',  # single or double
    u'end_blink': u'25',
    u'end_inverse': u'27',
    u'end_conceal': u'28',
    u'end_strike': u'29',

    u'black': u'30',
    u'red': u'31',
    u'green': u'32',
    u'yellow': u'33',
    u'blue': u'34',
    u'magenta': u'35',
    u'cyan': u'36',
    u'white': u'37',
    u'extended': u'38',
    u'default': u'39',

    u'fg_black': u'30',
    u'fg_red': u'31',
    u'fg_green': u'32',
    u'fg_yellow': u'33',
    u'fg_blue': u'34',
    u'fg_magenta': u'35',
    u'fg_cyan': u'36',
    u'fg_white': u'37',
    u'fg_extended': u'38',
    u'fg_default': u'39',

    u'bg_black': u'40',
    u'bg_red': u'41',
    u'bg_green': u'42',
    u'bg_yellow': u'44',
    u'bg_blue': u'44',
    u'bg_magenta': u'45',
    u'bg_cyan': u'46',
    u'bg_white': u'47',
    u'bg_extended': u'48',
    u'bg_default': u'49',

    u'frame': u'51',
    u'encircle': u'52',
    u'overline': u'53',
    u'end_frame': u'54',
    u'end_encircle': u'54',
    u'end_overline': u'55',

    u'ideogram_underline': u'60',
    u'right_line': u'60',
    u'ideogram_double_underline': u'61',
    u'right_double_line': u'61',
    u'ideogram_overline': u'62',
    u'left_line': u'62',
    u'ideogram_double_overline': u'63',
    u'left_double_line': u'63',
    u'ideogram_stress': u'64',
    u'reset_ideogram': u'65'
}


class TextFormat(object):
    '''
    ANSI Select Graphic Rendition (SGR) code escape sequence.
    '''

    def __init__(self, *attrs, **kwargs):
        '''
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
        '''
        self.codes = [codes[attr.lower()] for attr in attrs if isinstance(attr, six.string_types)]

        if kwargs.get(u'reset', True):
            self.codes[:0] = [codes[u'reset']]

        def qualify_int(i):
            if isinstance(i, int):
                return i % 256  # set i to base element of its equivalence class

        def qualify_triple_int(t):
            if isinstance(t, (list, tuple)) and len(t) == 3:
                return qualify_int(t[0]), qualify_int(t[1]), qualify_int(t[2])

        if kwargs.get(u'x', None) is not None:
            self.codes.extend((codes[u'extended'], u'5', qualify_int(kwargs[u'x'])))
        elif kwargs.get(u'rgb', None) is not None:
            self.codes.extend((codes[u'extended'], u'2'))
            self.codes.extend(*qualify_triple_int(kwargs[u'rgb']))

        if kwargs.get(u'bg_x', None) is not None:
            self.codes.extend((codes[u'extended'], u'5', qualify_int(kwargs[u'bg_x'])))
        elif kwargs.get(u'bg_rgb', None) is not None:
            self.codes.extend((codes[u'extended'], u'2'))
            self.codes.extend(*qualify_triple_int(kwargs[u'bg_rgb']))

        self.sequence = u'%s%s%s' % (graph_prefix,  # pylint: disable=E1321
                                    u';'.join(self.codes),
                                    graph_suffix)

    def __call__(self, text, reset=True):
        '''
        Format :param text: by prefixing `self.sequence` and suffixing the
        reset sequence if :param reset: is `True`.

        Examples:

        .. code-block:: python

            green_blink_text = TextFormat('blink', 'green')
            'The answer is: {0}'.format(green_blink_text(42))
        '''
        end = TextFormat(u'reset') if reset else u''
        return u'%s%s%s' % (self.sequence, text, end)  # pylint: disable=E1321

    def __str__(self):
        return self.sequence

    def __repr__(self):
        return self.sequence

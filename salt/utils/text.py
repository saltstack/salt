# coding=utf-8
'''
All text work utilities (formatting messages, layout etc).
'''
from __future__ import absolute_import, unicode_literals, print_function
import textwrap


def cli_info(data, title='Info'):
    '''
    Prints an info on CLI with the title.
    Useful for infos, general errors etc.

    :param data:
    :param title:
    :return:
    '''

    wrapper = textwrap.TextWrapper()
    wrapper.initial_indent = ' ' * 4
    wrapper.subsequent_indent = wrapper.initial_indent

    return '{title}:\n\n{text}'.format(title=title, text=wrapper.fill(data))

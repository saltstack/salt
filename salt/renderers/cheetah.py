# -*- coding: utf-8 -*-
'''
Cheetah Renderer for Salt
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd party libs
try:
    from Cheetah.Template import Template
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Import salt libs
from salt.ext import six


def render(cheetah_data, saltenv='base', sls='', method='xml', **kws):
    '''
    Render a Cheetah template.

    :rtype: A Python data structure
    '''
    if not HAS_LIBS:
        return {}

    if not isinstance(cheetah_data, six.string_types):
        cheetah_data = cheetah_data.read()

    if cheetah_data.startswith('#!'):
        cheetah_data = cheetah_data[(cheetah_data.find('\n') + 1):]
    if not cheetah_data.strip():
        return {}

    return six.text_type(Template(cheetah_data, searchList=[kws]))

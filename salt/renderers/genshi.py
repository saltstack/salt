# -*- coding: utf-8 -*-
'''
Genshi Renderer for Salt
'''

from __future__ import absolute_import

# Import 3rd party libs
try:
    from genshi.template import MarkupTemplate
    from genshi.template import NewTextTemplate
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Import salt libs
from salt._compat import string_types


def render(genshi_data, saltenv='base', sls='', method='xml', **kws):
    '''
    Render a Genshi template. A method should be passed in as part of the
    kwargs. If no method is passed in, xml is assumed. Valid methods are:

    .. code-block:

        - xml
        - xhtml
        - html
        - text
        - newtext
        - oldtext

    Note that the ``text`` method will call ``NewTextTemplate``. If ``oldtext``
    is desired, it must be called explicitly

    :rtype: A Python data structure
    '''
    if not HAS_LIBS:
        return {}

    if not isinstance(genshi_data, string_types):
        genshi_data = genshi_data.read()

    if genshi_data.startswith('#!'):
        genshi_data = genshi_data[(genshi_data.find('\n') + 1):]
    if not genshi_data.strip():
        return {}

    if method == 'text' or method == 'newtext':
        from genshi.template import NewTextTemplate
        tmpl = NewTextTemplate(tmplstr)
    elif method == 'oldtext':
        from genshi.template import OldTextTemplate
        tmpl = OldTextTemplate(tmplstr)
    else:
        from genshi.template import MarkupTemplate
        tmpl = MarkupTemplate(tmplstr)

    return tmpl.generate(**context).render(method)

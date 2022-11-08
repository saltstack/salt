"""
Genshi Renderer for Salt
"""


try:
    from genshi.template import MarkupTemplate, NewTextTemplate, OldTextTemplate

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


def render(genshi_data, saltenv="base", sls="", method="xml", **kws):
    """
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
    """
    if not HAS_LIBS:
        return {}

    if not isinstance(genshi_data, str):
        genshi_data = genshi_data.read()

    if genshi_data.startswith("#!"):
        genshi_data = genshi_data[(genshi_data.find("\n") + 1) :]
    if not genshi_data.strip():
        return {}

    if method == "text" or method == "newtext":
        tmpl = NewTextTemplate(genshi_data)
    elif method == "oldtext":
        tmpl = OldTextTemplate(genshi_data)
    else:
        tmpl = MarkupTemplate(genshi_data)

    return tmpl.generate(**kws).render(method)

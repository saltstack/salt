"""
Cheetah Renderer for Salt
"""

try:
    from Cheetah.Template import Template

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


def render(cheetah_data, saltenv="base", sls="", method="xml", **kws):
    """
    Render a Cheetah template.

    :rtype: A Python data structure
    """
    if not HAS_LIBS:
        return {}

    if not isinstance(cheetah_data, str):
        cheetah_data = cheetah_data.read()

    if cheetah_data.startswith("#!"):
        cheetah_data = cheetah_data[(cheetah_data.find("\n") + 1) :]
    if not cheetah_data.strip():
        return {}

    return str(Template(cheetah_data, searchList=[kws]))

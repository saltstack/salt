"""
Mako Renderer for Salt
"""


import io

import salt.utils.templates
from salt.exceptions import SaltRenderError


def render(template_file, saltenv="base", sls="", context=None, tmplpath=None, **kws):
    """
    Render the template_file, passing the functions and grains into the
    Mako rendering system.

    :rtype: string
    """
    tmp_data = salt.utils.templates.MAKO(
        template_file,
        to_str=True,
        salt=__salt__,
        grains=__grains__,
        opts=__opts__,
        pillar=__pillar__,
        saltenv=saltenv,
        sls=sls,
        context=context,
        tmplpath=tmplpath,
        **kws
    )
    if not tmp_data.get("result", False):
        raise SaltRenderError(
            tmp_data.get("data", "Unknown render error in mako renderer")
        )
    return io.StringIO(tmp_data["data"])

# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.templates
from salt.exceptions import SaltRenderError

# Import salt libs
from salt.ext import six


def render(template_file, saltenv="base", sls="", argline="", context=None, **kws):
    """
    Render the data passing the functions and grains into the rendering system

    :rtype: string
    """
    tmp_data = salt.utils.templates.WEMPY(
        template_file,
        to_str=True,
        salt=__salt__,
        grains=__grains__,
        opts=__opts__,
        pillar=__pillar__,
        saltenv=saltenv,
        sls=sls,
        context=context,
        **kws
    )
    if not tmp_data.get("result", False):
        raise SaltRenderError(
            tmp_data.get("data", "Unknown render error in the wempy renderer")
        )
    return six.moves.StringIO(tmp_data["data"])

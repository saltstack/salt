# -*- coding: utf-8 -*-
"""
Renderer to test argline handling in jinja renderer

See: https://github.com/saltstack/salt/issues/55124
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.stringio


def render(gpg_data, saltenv="base", sls="", argline="", **kwargs):
    """
    Renderer which returns the text value of the SLS file, instead of a
    StringIO object.
    """
    if salt.utils.stringio.is_readable(gpg_data):
        return gpg_data.getvalue()
    else:
        return gpg_data

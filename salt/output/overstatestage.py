# -*- coding: utf-8 -*-
"""
Display clean output of an overstate stage
==========================================

This outputter is used to display :ref:`Orchestrate Runner
<orchestrate-runner>` stages, and should not be called directly.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.color

# Import 3rd-party libs
from salt.ext import six

# [{'group2': {'match': ['fedora17-2', 'fedora17-3'],
#              'require': ['group1'],
#              'sls': ['nginx', 'edit']}
#              }
#              ]


def output(data, **kwargs):  # pylint: disable=unused-argument
    """
    Format the data for printing stage information from the overstate system
    """
    colors = salt.utils.color.get_colors(
        __opts__.get("color"), __opts__.get("color_theme")
    )
    ostr = ""
    for comp in data:
        for name, stage in six.iteritems(comp):
            ostr += "{0}{1}: {2}\n".format(colors["LIGHT_BLUE"], name, colors["ENDC"])
            for key in sorted(stage):
                ostr += "    {0}{1}: {2}{3}\n".format(
                    colors["LIGHT_BLUE"], key, stage[key], colors["ENDC"]
                )
    return ostr

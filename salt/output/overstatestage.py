"""
Display clean output of an overstate stage
==========================================

This outputter is used to display :ref:`Orchestrate Runner
<orchestrate-runner>` stages, and should not be called directly.
"""


import salt.utils.color

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
        for name, stage in comp.items():
            ostr += "{}{}: {}\n".format(colors["LIGHT_BLUE"], name, colors["ENDC"])
            for key in sorted(stage):
                ostr += "    {}{}: {}{}\n".format(
                    colors["LIGHT_BLUE"], key, stage[key], colors["ENDC"]
                )
    return ostr

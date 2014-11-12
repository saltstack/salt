# -*- coding: utf-8 -*-
'''
Display clean output of an overstate stage
==========================================

This outputter is used to display :ref:`OverState <states-overstate>` stages,
and should not be called directly.
'''
from __future__ import absolute_import


#[{'group2': {'match': ['fedora17-2', 'fedora17-3'],
#             'require': ['group1'],
#             'sls': ['nginx', 'edit']}
#             }
#             ]

# Import salt libs
import salt.utils


def output(data):
    '''
    Format the data for printing stage information from the overstate system
    '''
    colors = salt.utils.get_colors(__opts__.get('color'))
    ostr = ''
    for comp in data:
        for name, stage in comp.items():
            ostr += '{0}{1}: {2}\n'.format(
                    colors['LIGHT_BLUE'],
                    name,
                    colors['ENDC'])
            for key in sorted(stage):
                ostr += '    {0}{1}: {2}{3}\n'.format(
                        colors['LIGHT_BLUE'],
                        key,
                        stage[key],
                        colors['ENDC'])
    return ostr

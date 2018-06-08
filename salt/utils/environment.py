# -*- coding: utf-8 -*-
'''
Environment utilities.
'''
from __future__ import absolute_import, print_function, unicode_literals
import os


def get_module_environment(env=None):
    '''
    Get module optional environment.

    To setup an environment option for a particular module,
    add either pillar or config at the minion as follows:

    system-environment:
      salt.modules.pkg:
        LC_ALL: en_GB.UTF-8
        FOO: bar
      salt.states.pkg:
        LC_ALL: en_US.Latin-1
        NAME: Fred

    So this will export the environment to all the modules,
    states, returnes etc. And calling this function with the globals()
    in that context will fetch the environment for further reuse.

    First will be fetched configuration, where virtual name goes first,
    then the physical name of the module overrides the virtual settings.
    Then pillar settings will override the configuration in the same order.

    :param env:
    :return:
    '''

    result = {}
    if not env:
        env = {}

    for env_src in [env.get('__opts__', {}), env.get('__pillar__', {})]:
        fname = env.get('__file__', '')
        physical_name = os.path.basename(fname).split('.')[0]
        section = os.path.basename(os.path.dirname(fname))
        for m_name in set([env.get('__virtualname__'), physical_name]):
            result.update(env_src.get('system-environment', {}).get(
                'salt.{sn}.{mn}'.format(sn=section, mn=m_name), {}).copy())

    return result

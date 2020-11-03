# -*- coding: utf-8 -*-
"""
Environment utilities.
"""
from __future__ import absolute_import, print_function, unicode_literals

import os


def get_module_environment(env=None, function=None):
    """
    Get module optional environment.

    To setup an environment option for a particular module,
    add either pillar or config at the minion as follows:

    system-environment:
      modules:
        pkg:
          _:
            LC_ALL: en_GB.UTF-8
            FOO: bar
          install:
            HELLO: world
      states:
        pkg:
          _:
            LC_ALL: en_US.Latin-1
            NAME: Fred

    So this will export the environment to all the modules,
    states, returnes etc. And calling this function with the globals()
    in that context will fetch the environment for further reuse.

    Underscore '_' exports environment for all functions within the module.
    If you want to specifially export environment only for one function,
    specify it as in the example above "install".

    First will be fetched configuration, where virtual name goes first,
    then the physical name of the module overrides the virtual settings.
    Then pillar settings will override the configuration in the same order.

    :param env:
    :param function: name of a particular function
    :return: dict
    """
    result = {}
    if not env:
        env = {}
    for env_src in [env.get("__opts__", {}), env.get("__pillar__", {})]:
        fname = env.get("__file__", "")
        physical_name = os.path.basename(fname).split(".")[0]
        section = os.path.basename(os.path.dirname(fname))
        m_names = [env.get("__virtualname__")]
        if physical_name not in m_names:
            m_names.append(physical_name)
        for m_name in m_names:
            if not m_name:
                continue
            result.update(
                env_src.get("system-environment", {})
                .get(section, {})
                .get(m_name, {})
                .get("_", {})
                .copy()
            )
            if function is not None:
                result.update(
                    env_src.get("system-environment", {})
                    .get(section, {})
                    .get(m_name, {})
                    .get(function, {})
                    .copy()
                )

    return result

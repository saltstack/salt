#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''\
Welcome to the Salt repl which exposes the execution environment of a minion in
a pre-configured Python shell

__opts__, __salt__, __grains__, and __pillar__ are available.

Jinja can be tested with full access to the above structures in the usual way:

    JINJA("""\\
        I am {{ salt['cmd.run']('whoami') }}.

        {% if otherstuff %}
        Some other stuff here
        {% endif %}
    """, otherstuff=True)

A history file is maintained in ~/.saltsh_history.
completion behavior can be customized via the ~/.inputrc file.

'''
# pylint: disable=file-perms

# Import python libs
from __future__ import absolute_import

import atexit
import os
import pprint  # pylint: disable=unused-import
import readline
import sys
from code import InteractiveConsole

# Import 3rd party libs
import jinja2

# Import salt libs
import salt.client
import salt.config
import salt.loader
import salt.output
import salt.pillar
import salt.runner

# pylint: disable=unused-import
# These are imported to be available in the spawned shell
import salt.utils.yaml
from salt.ext.six.moves import builtins  # pylint: disable=import-error

# pylint: enable=unused-import

HISTFILE = "{HOME}/.saltsh_history".format(**os.environ)


def savehist():
    """
    Save the history file
    """
    readline.write_history_file(HISTFILE)


def get_salt_vars():
    """
    Return all the Salt-usual double-under data structures for a minion
    """
    # Create the Salt __opts__ variable
    __opts__ = salt.config.client_config(
        os.environ.get("SALT_MINION_CONFIG", "/etc/salt/minion")
    )

    # Populate grains if it hasn't been done already
    if "grains" not in __opts__ or not __opts__["grains"]:
        __opts__["grains"] = salt.loader.grains(__opts__)

    # file_roots and pillar_roots should be set in the minion config
    if "file_client" not in __opts__ or not __opts__["file_client"]:
        __opts__["file_client"] = "local"

    # ensure we have a minion id
    if "id" not in __opts__ or not __opts__["id"]:
        __opts__["id"] = "saltsh_mid"

    # Populate template variables
    __salt__ = salt.loader.minion_mods(__opts__)
    __grains__ = __opts__["grains"]

    if __opts__["file_client"] == "local":
        __pillar__ = salt.pillar.get_pillar(
            __opts__, __grains__, __opts__.get("id"), __opts__.get("saltenv"),
        ).compile_pillar()
    else:
        __pillar__ = {}

    # pylint: disable=invalid-name,unused-variable,possibly-unused-variable
    JINJA = lambda x, **y: jinja2.Template(x).render(
        grains=__grains__, salt=__salt__, opts=__opts__, pillar=__pillar__, **y
    )
    # pylint: enable=invalid-name,unused-variable,possibly-unused-variable

    return locals()


def main():
    """
    The main entry point
    """
    salt_vars = get_salt_vars()

    def salt_outputter(value):
        """
        Use Salt's outputters to print values to the shell
        """
        if value is not None:
            builtins._ = value
            salt.output.display_output(value, "", salt_vars["__opts__"])

    sys.displayhook = salt_outputter

    # Set maximum number of items that will be written to the history file
    readline.set_history_length(300)

    if os.path.exists(HISTFILE):
        readline.read_history_file(HISTFILE)

    atexit.register(savehist)
    atexit.register(lambda: sys.stdout.write("Salt you later!\n"))

    saltrepl = InteractiveConsole(locals=salt_vars)
    saltrepl.interact(banner=__doc__)


if __name__ == "__main__":
    main()

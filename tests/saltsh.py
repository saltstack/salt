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

# Import python libs
import atexit
import os
import readline
import sys
from code import InteractiveConsole

# Import salt libs
import salt.client
import salt.config
import salt.loader
import salt.output
import salt.pillar
import salt.runner

# Import 3rd party libs
import jinja2


# pylint: disable=W0611
# These are imported to be available in the spawmed shell


import yaml
import pprint


HISTFILE = '{HOME}/.saltsh_history'.format(**os.environ)


def savehist():
    '''
    Save the history file
    '''
    readline.write_history_file(HISTFILE)


def get_salt_vars():
    '''
    Return all the Salt-usual double-under data structures for a minion
    '''
    # Create the Salt __opts__ variable
    __opts__ = salt.config.client_config(
            os.environ.get('SALT_MINION_CONFIG', '/etc/salt/minion'))

    # Populate grains if it hasn't been done already
    if not 'grains' in __opts__ or not __opts__['grains']:
        __opts__['grains'] = salt.loader.grains(__opts__)

    # file_roots and pillar_roots should be set in the minion config
    if not 'file_client' in __opts__ or not __opts__['file_client']:
        __opts__['file_client'] = 'local'

    # Populate template variables
    __salt__ = salt.loader.minion_mods(__opts__)
    __grains__ = __opts__['grains']
    __pillar__ = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__.get('id'),
        __opts__.get('environment'),
    ).compile_pillar()

    JINJA = lambda x, **y: jinja2.Template(x).render(  # pylint: disable=C0103,W0612
            grains=__grains__,
            salt=__salt__,
            opts=__opts__,
            pillar=__pillar__,
            **y)

    return locals()


def main():
    '''
    The main entry point
    '''
    salt_vars = get_salt_vars()

    def salt_outputter(value):
        '''
        Use Salt's outputters to print values to the shell
        '''
        if value is not None:
            try:
                import __builtin__
                __builtin__._ = value
            except ImportError:
                __builtins__._ = value

            salt.output.display_output(value, '', salt_vars['__opts__'])

    sys.displayhook = salt_outputter

    # Set maximum number of items that will be written to the history file
    readline.set_history_length(300)

    if os.path.exists(HISTFILE):
        readline.read_history_file(HISTFILE)

    atexit.register(savehist)
    atexit.register(lambda: sys.stdout.write('Salt you later!\n'))

    saltrepl = InteractiveConsole(locals=salt_vars)
    saltrepl.interact(banner=__doc__)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
'''
Execute a command and read the output as YAML. The YAML data is then directly overlaid onto the minion's Pillar data
'''
from __future__ import absolute_import, print_function, unicode_literals

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import Python libs
import logging

# Import Salt party libs
import salt.utils.yaml

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               command):
    '''
    Execute a command and read the output as YAML
    '''
    try:
        command = command.replace('%s', minion_id)
        output = __salt__['cmd.run_stdout'](command, python_shell=True)
        return salt.utils.yaml.safe_load(output)
    except Exception:
        log.critical(
            'YAML data from \'%s\' failed to parse. Command output:\n%s',
            command, output
        )
        return {}

# -*- coding: utf-8 -*-
'''
    tests.support.cli_scripts
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Code to generate Salt CLI scripts for test runs
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals
import os
import sys
import logging

# Import Pytest Salt libs
from pytestsalt.utils import cli_scripts

log = logging.getLogger(__name__)


def get_script_path(bin_dir, script_name):
    '''
    Return the path to a testing runtime script, generating one if it does not yet exist
    '''
    # Late import
    from tests.support.runtests import RUNTIME_VARS

    if not os.path.isdir(bin_dir):
        os.makedirs(bin_dir)

    cli_script_name = 'cli_{}.py'.format(script_name.replace('-', '_'))
    script_path = os.path.join(bin_dir, cli_script_name)

    if not os.path.isfile(script_path):
        cli_scripts.generate_script(
            bin_dir=bin_dir,
            script_name=script_name,
            executable=sys.executable,
            code_dir=RUNTIME_VARS.CODE_DIR,
            inject_sitecustomize='COVERAGE_PROCESS_START' in os.environ
        )
    log.info('Returning script path %r', script_path)
    return script_path


class ScriptPathMixin(object):

    def get_script_path(self, script_name):
        '''
        Return the path to a testing runtime script
        '''
        # Late import
        from tests.support.runtests import RUNTIME_VARS
        return get_script_path(RUNTIME_VARS.TMP_SCRIPT_DIR, script_name)

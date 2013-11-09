# -*- coding: utf-8 -*-
'''
Use composer to install PHP dependencies
'''

# Import python libs
import json
import logging
import distutils.version  # pylint: disable=E0611

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Function alias to make sure not to shadow built-in's
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    return 'composer'

def _valid_composer(composer):
    if salt.utils.which(composer):
        return True
    return False

def install(dir,
            composer=None,
            runas=None,
            prefer_source=None,
            prefer_dist=None,
            no_scripts=None,
            no_plugins=None,
            optimize=None,
            no_dev=None,
            quiet=True):
    '''
    Install composer dependencies for a project

    If no composer is specified
    '''

    if composer is None:
            composer = 'composer'

    # Validate Composer is there
    if not _valid_composer(composer):
        return '{0!r} is not available.'.format('composer.install')

    if dir is None:
        return '{0!r} is required for {1!r}'.format('dir', 'composer.install')

    # Base Settings
    cmd = composer + ' install --no-interaction'

    # Add Working Dir
    cmd += ' --working-dir=' + dir

    # Other Settings
    if quiet is True:
        cmd += ' --quiet'

    if no_dev is True:
        cmd += ' --no-dev'
    
    if prefer_source is True:
        cmd += ' --prefer-source'

    if prefer_dist is True:
        cmd += ' --prefer-dist'

    if no_scripts is True:
        cmd += ' --no-scripts'

    if no_plugins is True:
        cmd += ' --no-plugins'

    if optimize is True:
        cmd += ' --optimize-autoloader'

    result = __salt__['cmd.run_all'](cmd, runas=runas)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    if quiet is True:
        return True

    return result['stdout']




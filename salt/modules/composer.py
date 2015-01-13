# -*- coding: utf-8 -*-
'''
Use composer to install PHP dependencies for a directory
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Function alias to make sure not to shadow built-in's
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Always load
    '''
    return True


def _valid_composer(composer):
    '''
    Validate the composer file is indeed there.
    '''
    if salt.utils.which(composer):
        return True
    return False


def install(dir,
            composer=None,
            php=None,
            runas=None,
            prefer_source=None,
            prefer_dist=None,
            no_scripts=None,
            no_plugins=None,
            optimize=None,
            no_dev=None,
            quiet=False,
            composer_home='/root'):
    '''
    Install composer dependencies for a directory.

    If composer has not been installed globally making it available in the
    system PATH & making it executable, the ``composer`` and ``php`` parameters
    will need to be set to the location of the executables.

    dir
        Directory location of the composer.json file.

    composer
        Location of the composer.phar file. If not set composer will
        just execute "composer" as if it is installed globally.
        (i.e. /path/to/composer.phar)

    php
        Location of the php executable to use with composer.
        (i.e. /usr/bin/php)

    runas
        Which system user to run composer as.

    prefer_source
        --prefer-source option of composer.

    prefer_dist
        --prefer-dist option of composer.

    no_scripts
        --no-scripts option of composer.

    no_plugins
        --no-plugins option of composer.

    optimize
        --optimize-autoloader option of composer. Recommended for production.

    no_dev
        --no-dev option for composer. Recommended for production.

    quiet
        --quiet option for composer. Whether or not to return output from composer.

    composer_home
        $COMPOSER_HOME environment variable

    CLI Example:

    .. code-block:: bash

        salt '*' composer.install /var/www/application

        salt '*' composer.install /var/www/application \
            no_dev=True optimize=True
    '''
    if composer is not None:
        if php is None:
            php = 'php'
    else:
        composer = 'composer'

    # Validate Composer is there
    if not _valid_composer(composer):
        return '{0!r} is not available. Couldn\'t find {1!r}.'.format('composer.install', composer)

    if dir is None:
        return '{0!r} is required for {1!r}'.format('dir', 'composer.install')

    # Base Settings
    cmd = composer + ' install --no-interaction'

    # If php is set, prepend it
    if php is not None:
        cmd = php + ' ' + cmd

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

    result = __salt__['cmd.run_all'](cmd,
                                     runas=runas,
                                     env={'COMPOSER_HOME': composer_home},
                                     python_shell=False)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    if quiet is True:
        return True

    return result['stdout']

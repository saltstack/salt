# -*- coding: utf-8 -*-
'''
Use composer to install PHP dependencies for a directory
'''
from __future__ import absolute_import

# Import python libs
import logging
import os.path

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError, SaltInvocationError

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


def did_composer_install(dir):
    '''
    Test to see if the vendor directory exists in this directory

    dir
        Directory location of the composer.json file

    CLI Example:

    .. code-block:: bash

        salt '*' composer.did_composer_install /var/www/application
    '''
    lockFile = "{0}/vendor".format(dir)
    if os.path.exists(lockFile):
        return True
    return False


def _run_composer(action,
            dir=None,
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
            composer_home='/root',
            extra_flags=None):
    '''
    Run PHP's composer with a specific action.

    If composer has not been installed globally making it available in the
    system PATH & making it executable, the ``composer`` and ``php`` parameters
    will need to be set to the location of the executables.

    action
        The action to pass to composer ('install', 'update', 'selfupdate', etc).

    dir
        Directory location of the composer.json file.  Required except when
        action='selfupdate'

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

    extra_flags
        None, or a string containing extra flags to pass to composer.
    '''
    if composer is not None:
        if php is None:
            php = 'php'
    else:
        composer = 'composer'

    # Validate Composer is there
    if not _valid_composer(composer):
        raise CommandNotFoundError('\'composer.{0}\' is not available. Couldn\'t find {1!r}.'
                                   .format(action, composer))

    # Don't need a dir for the 'selfupdate' action; all other actions do need a dir
    if dir is None and action != 'selfupdate':
        raise SaltInvocationError('{0!r} is required for \'composer.{1}\''
                                  .format('dir', action))

    if action is None:
        raise SaltInvocationError('{0!r} is required for {1!r}'
                                  .format('action', 'composer._run_composer'))

    # Base Settings
    cmd = '{0} {1} {2}'.format(composer, action, '--no-interaction --no-ansi')

    if extra_flags is not None:
        cmd = '{0} {1}'.format(cmd, extra_flags)

    # If php is set, prepend it
    if php is not None:
        cmd = php + ' ' + cmd

    # Add Working Dir
    if dir is not None:
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

    return result


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
    result = _run_composer('install',
                           dir=dir,
                           composer=composer,
                           php=php,
                           runas=runas,
                           prefer_source=prefer_source,
                           prefer_dist=prefer_dist,
                           no_scripts=no_scripts,
                           no_plugins=no_plugins,
                           optimize=optimize,
                           no_dev=no_dev,
                           quiet=quiet,
                           composer_home=composer_home)
    return result


def update(dir,
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
    Update composer dependencies for a directory.

    If `composer install` has not yet been run, this runs `composer install`
    instead.

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

        salt '*' composer.update /var/www/application

        salt '*' composer.update /var/www/application \
            no_dev=True optimize=True
    '''
    result = _run_composer('update',
                           extra_flags='--no-progress',
                           dir=dir,
                           composer=composer,
                           php=php,
                           runas=runas,
                           prefer_source=prefer_source,
                           prefer_dist=prefer_dist,
                           no_scripts=no_scripts,
                           no_plugins=no_plugins,
                           optimize=optimize,
                           no_dev=no_dev,
                           quiet=quiet,
                           composer_home=composer_home)
    return result


def selfupdate(composer=None,
            php=None,
            runas=None,
            quiet=False,
            composer_home='/root'):
    '''
    Update composer itself.

    If composer has not been installed globally making it available in the
    system PATH & making it executable, the ``composer`` and ``php`` parameters
    will need to be set to the location of the executables.

    composer
        Location of the composer.phar file. If not set composer will
        just execute "composer" as if it is installed globally.
        (i.e. /path/to/composer.phar)

    php
        Location of the php executable to use with composer.
        (i.e. /usr/bin/php)

    runas
        Which system user to run composer as.

    quiet
        --quiet option for composer. Whether or not to return output from composer.

    composer_home
        $COMPOSER_HOME environment variable

    CLI Example:

    .. code-block:: bash

        salt '*' composer.selfupdate
    '''
    result = _run_composer('selfupdate',
                           extra_flags='--no-progress',
                           composer=composer,
                           php=php,
                           runas=runas,
                           quiet=quiet,
                           composer_home=composer_home)
    return result

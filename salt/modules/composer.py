"""
Use composer to install PHP dependencies for a directory
"""

import logging
import os.path

import salt.utils.args
import salt.utils.path
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
)

log = logging.getLogger(__name__)

# Function alias to make sure not to shadow built-in's
__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Always load
    """
    return True


def _valid_composer(composer):
    """
    Validate the composer file is indeed there.
    """
    if salt.utils.path.which(composer):
        return True
    return False


def did_composer_install(dir):
    """
    Test to see if the vendor directory exists in this directory

    dir
        Directory location of the composer.json file

    CLI Example:

    .. code-block:: bash

        salt '*' composer.did_composer_install /var/www/application
    """
    lockFile = "{}/vendor".format(dir)
    if os.path.exists(lockFile):
        return True
    return False


def _run_composer(
    action,
    directory=None,
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
    composer_home="/root",
    extra_flags=None,
    env=None,
):
    """
    Run PHP's composer with a specific action.

    If composer has not been installed globally making it available in the
    system PATH & making it executable, the ``composer`` and ``php`` parameters
    will need to be set to the location of the executables.

    action
        The action to pass to composer ('install', 'update', 'selfupdate', etc).

    directory
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

    env
        A list of environment variables to be set prior to execution.
    """
    if composer is not None:
        if php is None:
            php = "php"
    else:
        composer = "composer"

    # Validate Composer is there
    if not _valid_composer(composer):
        raise CommandNotFoundError(
            "'composer.{}' is not available. Couldn't find '{}'.".format(
                action, composer
            )
        )

    if action is None:
        raise SaltInvocationError("The 'action' argument is required")

    # Don't need a dir for the 'selfupdate' action; all other actions do need a dir
    if directory is None and action != "selfupdate":
        raise SaltInvocationError(
            "The 'directory' argument is required for composer.{}".format(action)
        )

    # Base Settings
    cmd = [composer, action, "--no-interaction", "--no-ansi"]

    if extra_flags is not None:
        cmd.extend(salt.utils.args.shlex_split(extra_flags))

    # If php is set, prepend it
    if php is not None:
        cmd = [php] + cmd

    # Add Working Dir
    if directory is not None:
        cmd.extend(["--working-dir", directory])

    # Other Settings
    if quiet is True:
        cmd.append("--quiet")

    if no_dev is True:
        cmd.append("--no-dev")

    if prefer_source is True:
        cmd.append("--prefer-source")

    if prefer_dist is True:
        cmd.append("--prefer-dist")

    if no_scripts is True:
        cmd.append("--no-scripts")

    if no_plugins is True:
        cmd.append("--no-plugins")

    if optimize is True:
        cmd.append("--optimize-autoloader")

    if env is not None:
        env = salt.utils.data.repack_dictlist(env)
        env["COMPOSER_HOME"] = composer_home
    else:
        env = {"COMPOSER_HOME": composer_home}

    result = __salt__["cmd.run_all"](cmd, runas=runas, env=env, python_shell=False)

    if result["retcode"] != 0:
        raise CommandExecutionError(result["stderr"])

    if quiet is True:
        return True

    return result


def install(
    directory,
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
    composer_home="/root",
    env=None,
):
    """
    Install composer dependencies for a directory.

    If composer has not been installed globally making it available in the
    system PATH & making it executable, the ``composer`` and ``php`` parameters
    will need to be set to the location of the executables.

    directory
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

    env
        A list of environment variables to be set prior to execution.

    CLI Example:

    .. code-block:: bash

        salt '*' composer.install /var/www/application

        salt '*' composer.install /var/www/application \
            no_dev=True optimize=True
    """
    result = _run_composer(
        "install",
        directory=directory,
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
        composer_home=composer_home,
        env=env,
    )
    return result


def update(
    directory,
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
    composer_home="/root",
    env=None,
):
    """
    Update composer dependencies for a directory.

    If `composer install` has not yet been run, this runs `composer install`
    instead.

    If composer has not been installed globally making it available in the
    system PATH & making it executable, the ``composer`` and ``php`` parameters
    will need to be set to the location of the executables.

    directory
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

    env
        A list of environment variables to be set prior to execution.

    CLI Example:

    .. code-block:: bash

        salt '*' composer.update /var/www/application

        salt '*' composer.update /var/www/application \
            no_dev=True optimize=True
    """
    result = _run_composer(
        "update",
        directory=directory,
        extra_flags="--no-progress",
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
        composer_home=composer_home,
        env=env,
    )
    return result


def selfupdate(composer=None, php=None, runas=None, quiet=False, composer_home="/root"):
    """
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
    """
    result = _run_composer(
        "selfupdate",
        extra_flags="--no-progress",
        composer=composer,
        php=php,
        runas=runas,
        quiet=quiet,
        composer_home=composer_home,
    )
    return result

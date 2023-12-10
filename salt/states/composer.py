"""
Installation of Composer Packages
=================================

These states manage the installed packages for composer for PHP. Note that
either composer is installed and accessible via a bin directory or you can pass
the location of composer in the state.

.. code-block:: yaml

    get-composer:
      cmd.run:
        - name: 'CURL=`which curl`; $CURL -sS https://getcomposer.org/installer | php'
        - unless: test -f /usr/local/bin/composer
        - cwd: /root/

    install-composer:
      cmd.wait:
        - name: mv /root/composer.phar /usr/local/bin/composer
        - cwd: /root/
        - watch:
          - cmd: get-composer

    /path/to/project:
      composer.installed:
        - no_dev: true
        - require:
          - cmd: install-composer


    # Without composer installed in your PATH
    # Note: composer.phar must be executable for state to work properly
    /path/to/project:
      composer.installed:
        - composer: /path/to/composer.phar
        - php: /usr/local/bin/php
        - no_dev: true
"""

from salt.exceptions import SaltException


def __virtual__():
    """
    Only load if the composer module is available in __salt__
    """
    if "composer.install" in __salt__:
        return True
    return (False, "composer module could not be loaded")


def installed(
    name,
    composer=None,
    php=None,
    user=None,
    prefer_source=None,
    prefer_dist=None,
    no_scripts=None,
    no_plugins=None,
    optimize=None,
    no_dev=None,
    quiet=False,
    composer_home="/root",
    always_check=True,
    env=None,
):
    """
    Verify that the correct versions of composer dependencies are present.

    name
        Directory location of the ``composer.json`` file.

    composer
        Location of the ``composer.phar`` file. If not set composer will
        just execute ``composer`` as if it is installed globally.
        (i.e. ``/path/to/composer.phar``)

    php
        Location of the php executable to use with composer.
        (i.e. ``/usr/bin/php``)

    user
        Which system user to run composer as.

        .. versionadded:: 2014.1.4

    prefer_source
        ``--prefer-source`` option of composer.

    prefer_dist
        ``--prefer-dist`` option of composer.

    no_scripts
        ``--no-scripts`` option of composer.

    no_plugins
        ``--no-plugins`` option of composer.

    optimize
        ``--optimize-autoloader`` option of composer. Recommended for production.

    no_dev
        ``--no-dev`` option for composer. Recommended for production.

    quiet
        ``--quiet`` option for composer. Whether or not to return output from composer.

    composer_home
        ``$COMPOSER_HOME`` environment variable

    always_check
        If ``True``, *always* run ``composer install`` in the directory.  This is the
        default behavior.  If ``False``, only run ``composer install`` if there is no
        vendor directory present.

    env
        A list of environment variables to be set prior to execution.
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    did_install = __salt__["composer.did_composer_install"](name)

    # Check if composer.lock exists, if so we already ran `composer install`
    # and we don't need to do it again
    if always_check is False and did_install:
        ret["result"] = True
        ret["comment"] = "Composer already installed this directory"
        return ret

    # The state of the system does need to be changed. Check if we're running
    # in ``test=true`` mode.
    if __opts__["test"] is True:

        if did_install is True:
            install_status = ""
        else:
            install_status = "not "

        ret["comment"] = 'The state of "{}" will be changed.'.format(name)
        ret["changes"] = {
            "old": "composer install has {}been run in {}".format(install_status, name),
            "new": "composer install will be run in {}".format(name),
        }
        ret["result"] = None
        return ret

    try:
        call = __salt__["composer.install"](
            name,
            composer=composer,
            php=php,
            runas=user,
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
    except (SaltException) as err:
        ret["result"] = False
        ret["comment"] = "Error executing composer in '{}': {}".format(name, err)
        return ret

    # If composer retcode != 0 then an exception was thrown and we dealt with it.
    # Any other case is success, regardless of what composer decides to output.

    ret["result"] = True

    if quiet is True:
        ret[
            "comment"
        ] = "Composer install completed successfully, output silenced by quiet flag"
    else:
        ret["comment"] = "Composer install completed successfully"
        ret["changes"] = {"stderr": call["stderr"], "stdout": call["stdout"]}

    return ret


def update(
    name,
    composer=None,
    php=None,
    user=None,
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
    Composer update the directory to ensure we have the latest versions
    of all project dependencies.

    name
        Directory location of the ``composer.json`` file.

    composer
        Location of the ``composer.phar`` file. If not set composer will
        just execute ``composer`` as if it is installed globally.
        (i.e. /path/to/composer.phar)

    php
        Location of the php executable to use with composer.
        (i.e. ``/usr/bin/php``)

    user
        Which system user to run composer as.

        .. versionadded:: 2014.1.4

    prefer_source
        ``--prefer-source`` option of composer.

    prefer_dist
        ``--prefer-dist`` option of composer.

    no_scripts
        ``--no-scripts`` option of composer.

    no_plugins
        ``--no-plugins`` option of composer.

    optimize
        ``--optimize-autoloader`` option of composer. Recommended for production.

    no_dev
        ``--no-dev`` option for composer. Recommended for production.

    quiet
        ``--quiet`` option for composer. Whether or not to return output from composer.

    composer_home
        ``$COMPOSER_HOME`` environment variable

    env
        A list of environment variables to be set prior to execution.
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    # Check if composer.lock exists, if so we already ran `composer install`
    is_installed = __salt__["composer.did_composer_install"](name)
    if is_installed:
        old_status = "composer install has not yet been run in {}".format(name)
    else:
        old_status = "composer install has been run in {}".format(name)

    # The state of the system does need to be changed. Check if we're running
    # in ``test=true`` mode.
    if __opts__["test"] is True:
        ret["comment"] = 'The state of "{}" will be changed.'.format(name)
        ret["changes"] = {
            "old": old_status,
            "new": "composer install/update will be run in {}".format(name),
        }
        ret["result"] = None
        return ret

    try:
        call = __salt__["composer.update"](
            name,
            composer=composer,
            php=php,
            runas=user,
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
    except (SaltException) as err:
        ret["result"] = False
        ret["comment"] = "Error executing composer in '{}': {}".format(name, err)
        return ret

    # If composer retcode != 0 then an exception was thrown and we dealt with it.
    # Any other case is success, regardless of what composer decides to output.

    ret["result"] = True

    if quiet is True:
        ret[
            "comment"
        ] = "Composer update completed successfully, output silenced by quiet flag"
    else:
        ret["comment"] = "Composer update completed successfully"
        ret["changes"] = {"stderr": call["stderr"], "stdout": call["stdout"]}

    return ret

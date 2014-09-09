# -*- coding: utf-8 -*-
'''
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
'''

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError


def __virtual__():
    '''
    Only load if the composer module is available in __salt__
    '''
    return 'composer.install' in __salt__


def installed(name,
              composer=None,
              php=None,
              runas=None,
              user=None,
              prefer_source=None,
              prefer_dist=None,
              no_scripts=None,
              no_plugins=None,
              optimize=None,
              no_dev=None,
              composer_home='/root'):
    '''
    Verify that composer has installed the latest packages give a
    ``composer.json`` and ``composer.lock`` file in a directory.

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

        .. deprecated:: 2014.1.4

    user
        Which system user to run composer as.

        .. versionadded:: 2014.1.4

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
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        'Lithium',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 2014.1.4.',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    try:
        call = __salt__['composer.install'](
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
            quiet=False,
            composer_home=composer_home
        )
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error executing composer in \'{0!r}\': {1!r}'.format(name, err)
        return ret

    if call or isinstance(call, list) or isinstance(call, dict):
        ret['result'] = True
        if call.find('Nothing to install or update') < 0:
            ret['changes']['stdout'] = call

        ret['comment'] = 'Composer ran, nothing changed in {0!r}'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Could not run composer'

    return ret

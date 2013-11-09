'''
Installaction of Composer Packages
==================================

These states manage the installed packages for composer for PHP.
Note that either composer is installed and accessible via a bin
directory or you can pass the location of composer in the state.

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
        - no_dev
        - require:
          - cmd: install-composer


    # Without composer installed in your PATH

    /path/to/composer:
      composer.installed:
        - composer: /path/to/composer.phar
        - php: /usr/local/bin/php
        - no_dev
'''

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError

def __virtual__():
    '''
    Only load if the npm module is available in __salt__
    '''
    return 'composer' if 'composer.install' in __salt__ else False

def installed(name,
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
    Docs go here
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    try:
        call = __salt__['composer.install'](
            name,
            composer=composer,
            runas=runas,
            prefer_source=prefer_source,
            prefer_dist=prefer_dist,
            no_scripts=no_scripts,
            no_plugins=no_plugins,
            optimize=optimize,
            no_dev=no_dev,
            quiet=quiet
        )
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error executing composer in \'{0}\': {1}'.format(name, err)
        return ret

    if call or isinstance(call, list) or isinstance(call, dict):
        ret['result'] = True
        ret['changes']['Composer Ran'] = 'Installed'
        ret['comment'] = 'Composer install executed in '.format(dir)
    else:
        ret['result'] = False
        ret['comment'] = 'Could not run composer'

    return ret




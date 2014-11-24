# -*- coding: utf-8 -*-
'''
Installation of Ruby modules packaged as gems
=============================================

A state module to manage rubygems. Gems can be set up to be installed
or removed. This module will use RVM or rbenv if they are installed. In that case,
you can specify what ruby version and gemset to target.

.. code-block:: yaml

    addressable:
      gem.installed:
        - user: rvm
        - ruby: jruby@jgemset
'''

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if gem module is available in __salt__
    '''
    return 'gem.list' in __salt__


def installed(name,          # pylint: disable=C0103
              ruby=None,
              runas=None,
              user=None,
              version=None,
              rdoc=False,
              ri=False,
              proxy=None):     # pylint: disable=C0103
    '''
    Make sure that a gem is installed.

    name
        The name of the gem to install

    ruby: None
        For RVM or rbenv installations: the ruby version and gemset to target.

    runas: None
        The user under which to run the ``gem`` command

        .. deprecated:: 0.17.0

    user: None
        The user under which to run the ``gem`` command

        .. versionadded:: 0.17.0

    version : None
        Specify the version to install for the gem.
        Doesn't play nice with multiple gems at once

    rdoc : False
        Generate RDoc documentation for the gem(s).

    ri : False
        Generate RI documentation for the gem(s).

    proxy : None
        Use the specified HTTP proxy server for all outgoing traffic.
        Format: http://hostname[:port]
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        'Lithium',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
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

    gems = __salt__['gem.list'](name, ruby, runas=user)
    if name in gems and version is not None and version in gems[name]:
        ret['result'] = True
        ret['comment'] = 'Gem is already installed.'
        return ret
    elif name in gems and version is None:
        ret['result'] = True
        ret['comment'] = 'Gem is already installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The gem {0} would have been installed'.format(name)
        return ret
    if __salt__['gem.install'](name,
                               ruby=ruby,
                               runas=user,
                               version=version,
                               rdoc=rdoc,
                               ri=ri,
                               proxy=proxy):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = 'Gem was successfully installed'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install gem.'

    return ret


def removed(name, ruby=None, runas=None, user=None):
    '''
    Make sure that a gem is not installed.

    name
        The name of the gem to uninstall

    ruby: None
        For RVM or rbenv installations: the ruby version and gemset to target.

    runas: None
        The user under which to run the ``gem`` command

        .. deprecated:: 0.17.0

    user: None
        The user under which to run the ``gem`` command

        .. versionadded:: 0.17.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        'Lithium',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
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

    if name not in __salt__['gem.list'](name, ruby, runas=user):
        ret['result'] = True
        ret['comment'] = 'Gem is not installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The gem {0} would have been removed'.format(name)
        return ret
    if __salt__['gem.uninstall'](name, ruby, runas=user):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Gem was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove gem.'
    return ret

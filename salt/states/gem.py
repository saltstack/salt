'''
Installation of Ruby modules packaged as gems.
==============================================

A state module to manage rubygems. Gems can be set up to be installed
or removed. This module will use RVM if it is installed. In that case,
you can specify what ruby version and gemset to target.

.. code-block:: yaml

    addressable:
      gem.installed:
        - runas: rvm
        - ruby: jruby@jgemset
'''


def __virtual__():
    '''
    Only load if gem module is available in __salt__
    '''
    return 'gem' if 'gem.list' in __salt__ else False


def installed(name,          # pylint: disable=C0103
              ruby=None,
              runas=None,
              version=None,
              rdoc=False,
              ri=False):     # pylint: disable=C0103
    '''
    Make sure that a gem is installed.

    name
        The name of the gem to install
    ruby : None
        For RVM installations: the ruby version and gemset to target.
    runas : None
        The user to run gem as.
    version : None
        Specify the version to install for the gem.
        Doesn't play nice with multiple gems at once
    rdoc : False
        Generate RDoc documentation for the gem(s).
    ri : False
        Generate RI documentation for the gem(s).
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    gems = __salt__['gem.list'](name, ruby, runas=runas)
    if name in gems and version and version in gems[name]:
        ret['result'] = True
        ret['comment'] = 'Gem is already installed.'
        return ret
    elif name in gems:
        ret['result'] = True
        ret['comment'] = 'Gem is already installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The gem {0} would have been installed'.format(name)
        return ret
    if __salt__['gem.install'](name,
                               ruby=ruby,
                               runas=runas,
                               version=version,
                               rdoc=rdoc,
                               ri=ri):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = 'Gem was successfully installed'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install gem.'

    return ret


def removed(name, ruby=None, runas=None):
    '''
    Make sure that a gem is not installed.

    name
        The name of the gem to uninstall
    ruby : None
        For RVM installations: the ruby version and gemset to target.
    runas : None
        The user to run gem as.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    if name not in __salt__['gem.list'](name, ruby, runas=runas):
        ret['result'] = True
        ret['comment'] = 'Gem is not installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The gem {0} would have been removed'.format(name)
        return ret
    if __salt__['gem.uninstall'](name, ruby, runas=runas):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Gem was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove gem.'
    return ret

# -*- coding: utf-8 -*-
'''
Installation of Cygwin packages
===============================

A state module to manage cygwin packages. Packages can be installed
or removed.

.. code-block:: yaml

    dos2unix:
      cyg.installed
'''

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if cyg module is available in __salt__
    '''
    return 'cyg.list' in __salt__


def installed(name,          # pylint: disable=C0103
              version=None,
              cyg_arch='x86_64'):     # pylint: disable=C0103
    '''
    Make sure that a package is installed.

    name
        The name of the package to install

    version : None
        Requested version of the package.
        Currently not used will instal the latest

    cyg_arch : x86_64
        The cygwin architecture to install the package into.
        Current options are x86 and x86_64
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if cyg_arch not in ['x86', 'x86_64']:
        return _fail(ret,
            'The \'cyg_arch\' argument must be one of \'x86\' or \'x86_64\''
        )

    pkgs = __salt__['cyg.list'](name, version, cyg_arch)
    if name in pkgs:
        ret['result'] = True
        ret['comment'] = 'Package is already installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The package {0} would have been installed'.format(name)
        return ret

    if __salt__['cyg.install'](name,
                               version=version,
                               cyg_arch=cyg_arch):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = 'Package was successfully installed'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install package.'

    return ret


def removed(name, cyg_arch='x86_64'):
    '''
    Make sure that a package is not installed.

    name
        The name of the package to uninstall

    cyg_arch : x86_64
        The cygwin architecture to remove the package from.
        Current options are x86 and x86_64
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if cyg_arch not in ['x86', 'x86_64']:
        return _fail(ret,
            'The \'cyg_arch\' argument must be one of \'x86\' or \'x86_64\''
        )

    if name not in __salt__['cyg.list'](name, cyg_arch):
        ret['result'] = True
        ret['comment'] = 'Package is not installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The package {0} would have been removed'.format(name)
        return ret
    if __salt__['cyg.uninstall'](name, cyg_arch):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Package was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove package.'
    return ret

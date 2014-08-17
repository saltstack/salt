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
              cyg_arch='x86_64'):     # pylint: disable=C0103
    '''
    Make sure that a package is installed.

    name
        The name of the package to install

    cyg_arch : x86_64
        The cygwin architecture to install the package into.
        Current options are x86 and x86_64
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if cyg_arch not in ['x86', 'x86_64']:
        return _fail(ret,
                     'The \'cyg_arch\' argument must be one of \'x86\' or \'x86_64\''
                    )

    if not __salt__['cyg.check_valid_package'](name, cyg_arch=cyg_arch):
        ret['result'] = False
        ret['comment'] = 'Invalid package name.'
        return ret

    pkgs = __salt__['cyg.list'](name, cyg_arch)
    if name in pkgs:
        ret['result'] = True
        ret['comment'] = 'Package is already installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The package {0} would have been installed'.format(name)
        return ret

    if __salt__['cyg.install'](name,
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

    if not __salt__['cyg.check_valid_package'](name, cyg_arch=cyg_arch):
        ret['result'] = False
        ret['comment'] = 'Invalid package name.'
        return ret

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

def updated(cyg_arch='x86_64'):
    '''
    Make sure all packages are up to date.

    cyg_arch : x86_64
        The cygwin architecture to update.
        Current options are x86 and x86_64
    '''
    ret = {'name': 'cyg.updated', 'result': None, 'comment': '', 'changes': {}}

    if cyg_arch not in ['x86', 'x86_64']:
        return _fail(ret,
                     'The \'cyg_arch\' argument must be one of \'x86\' or \'x86_64\''
                    )

    if __opts__['test']:
        ret['comment'] = 'All packages would have been updated'
        return ret
    before = __salt__['cyg.list'](cyg_arch=cyg_arch)
    if __salt__['cyg.update'](cyg_arch):
        after = __salt__['cyg.list'](cyg_arch=cyg_arch)
        differ = DictDiffer(before, after)
        ret['result'] = True
        if differ.same():
            ret['comment'] = 'Nothing to update.'
        else:
            ret['changes']['added'] = list(differ.added())
            ret['changes']['removed'] = list(differ.removed())
            ret['changes']['changed'] = list(differ.changed())
            ret['comment'] = 'All packages successfully updated.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not update packages.'
    return ret


"""
https://github.com/hughdbrown/dictdiffer
DictDiffer is licensed as MIT code
A dictionary difference calculator
Originally posted as:
http://stackoverflow.com/questions/1165352/fast-comparison-between-two-python-dictionary/1165552#1165552
"""
class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """
    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.current_keys, self.past_keys = [
            set(d.keys()) for d in (current_dict, past_dict)
        ]
        self.intersect = self.current_keys.intersection(self.past_keys)

    def same(self):
        return self.current_dict == self.past_dict

    def added(self):
        return self.current_keys - self.intersect

    def removed(self):
        return self.past_keys - self.intersect

    def changed(self):
        return set(o for o in self.intersect
                   if self.past_dict[o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect
                   if self.past_dict[o] == self.current_dict[o])

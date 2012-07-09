'''
Loading and unloading of kernel modules.
========================================

The Kernel modules on a system can be managed cleanly with the kmod state
module:

.. code-block:: yaml

  kvm_amd:
    kmod.present
  pcspkr:
    kmod.absent
'''


def __virtual__():
    '''
    only load if kmod is available
    '''
    return 'kmod' if 'kmod.available' in __salt__ else False


def present(name):
    '''
    Ensure that the specified kernel module is loaded

    name
        The name of the kernel module to verify is loaded
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    mods = __salt__['kmod.lsmod']()
    for mod in mods:
        if mod['module'] == name:
            ret['comment'] = ('Kernel module {0} is already present'
                              .format(name))
            return ret
    # Module is not loaded, verify availability
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Module {0} is set to be loaded'.format(name)
        return ret
    if name not in __salt__['kmod.available']():
        ret['comment'] = 'Kernel module {0} is unavailable'.format(name)
        ret['result'] = False
        return ret
    for mod in __salt__['kmod.load'](name):
        ret['changes'][mod] = 'loaded'
    if not ret['changes']:
        ret['result'] = False
        ret['comment'] = 'Failed to load kernel module {0}'.format(name)
        return ret
    ret['comment'] = 'Loaded kernel module {0}'.format(name)
    return ret


def absent(name):
    '''
    Verify that the named kernel module is not loaded

    name
        The name of the kernel module to verify is not loaded
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    mods = __salt__['kmod.lsmod']()
    for mod in mods:
        if mod['module'] == name:
            # Found the module, unload it!
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Module {0} is set to be unloaded'
                ret['comment'] = ret['comment'].format(name)
                return ret
            for mod in __salt__['kmod.load'](name):
                ret['changes'][mod] = 'removed'
            for change in ret['changes']:
                if name in change:
                    ret['comment'] = 'Removed kernel module {0}'.format(name)
                    return ret
            ret['result'] = False
            ret['comment'] = ('Module {0} is present but failed to remove'
                              .format(name))
            return ret
    ret['comment'] = 'Kernel module {0} is already absent'.format(name)
    return ret

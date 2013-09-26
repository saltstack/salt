# -*- coding: utf-8 -*-
'''
Accept a key from a hypervisor if the virt runner has
already submitted an authorization request
'''

# Import python libs
import logging

# Import salt libs
import salt.utils.virt


# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(hyper_id, pillar, name, key):
    '''
    Accept the key for the VM on the hyper, if authorized.
    '''
    vk = salt.utils.virt.VirtKey(hyper_id, name, __opts__)
    ok = vk.accept(key)
    pillar['virtkey'] = {name: ok}
    return {}

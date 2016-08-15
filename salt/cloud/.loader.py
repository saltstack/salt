# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "cloud" sub-system'''


from __future__ import absolute_import

import logging

from salt import loader_core
from salt import loader_pre

LOG = logging.getLogger(__name__)


# Because on the cloud drivers we do `from salt.cloud.libcloudfuncs import *`
# which simplifies code readability, it adds some unsupported functions into
# the driver's module scope.
# We list un-supported functions here. These will be removed from the loaded.
LIBCLOUD_FUNCS_NOT_SUPPORTED = (
    'parallels.avail_sizes',
    'parallels.avail_locations',
    'proxmox.avail_sizes',
    'saltify.destroy',
    'saltify.avail_sizes',
    'saltify.avail_images',
    'saltify.avail_locations',
    'rackspace.reboot',
    'openstack.list_locations',
    'rackspace.list_locations'
)


@loader_pre.LoaderFunc
def clouds(opts):
    '''
    Return the cloud functions
    '''
    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    functions = loader_core.LazyLoader(
        loader_core.module_dirs(opts,
                                'clouds',
                                'cloud',
                                base_path=__this_dir__,
                                int_type='clouds'),
        opts,
        tag='clouds',
        pack={'__active_provider_name__': None},
    )
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        LOG.trace(
            '\'{0}\' has been marked as not supported. Removing from the list '
            'of supported cloud functions'.format(
                funcname
            )
        )
        functions.pop(funcname, None)
    return functions

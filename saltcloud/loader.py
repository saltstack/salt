'''
The salt cloud module loader interface
'''
# Import python libs
import os
import logging

# Import Salt libs
import salt.loader
import saltcloud

log = logging.getLogger(__name__)


# Because on the cloud drivers we do `from saltcloud.libcloudfuncs import *`
# which simplifies code readability, it adds some unsupported functions into
# the driver's module scope.
# We list un-supported functions here. These will be removed from the loaded.
LIBCLOUD_FUNCS_NOT_SUPPORTED = (
    'joyent.avail_locations',
    'parallels.avail_sizes',
    'parallels.avail_locations',
    'saltify.destroy',
    'saltify.avail_sizes',
    'saltify.avail_images',
    'saltify.avail_locations',

)


def clouds(opts):
    '''
    Return the cloud functions
    '''
    load = salt.loader._create_loader(
        opts,
        'clouds',
        'cloud',
        base_path=os.path.dirname(
            saltcloud.__file__
        )
    )
    functions = load.gen_functions()
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        log.debug(
            '{0!r} has been marked as not supported. Removing from the list '
            'of supported cloud functions'.format(
                funcname
            )
        )
        functions.pop(funcname, None)
    return functions

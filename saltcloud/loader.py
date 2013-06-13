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
    salt_base_path = os.path.dirname(saltcloud.__file__)

    def saltcloud_mod_type_check(modpath):
        if modpath.startswith(salt_base_path):
            return 'int'
        return 'ext'

    try:
        load = salt.loader._create_loader(
            opts,
            'clouds',
            'cloud',
            base_path=salt_base_path,
            loaded_base_name='saltcloud.loaded',
            mod_type_check=saltcloud_mod_type_check
        )
    except TypeError:
        # Salt is not recent enough
        load = salt.loader._create_loader(
            opts,
            'clouds',
            'cloud',
            base_path=salt_base_path,
        )

    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    pack = {
        'name': '__active_provider_name__',
        'value': None
    }

    functions = load.gen_functions(pack)
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        log.debug(
            '{0!r} has been marked as not supported. Removing from the list '
            'of supported cloud functions'.format(
                funcname
            )
        )
        functions.pop(funcname, None)
    return functions

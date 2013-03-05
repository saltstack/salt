'''
The salt cloud module loader interface
'''
# Import python libs
import os

# Import Salt libs
import salt.loader
import saltcloud


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
    return load.gen_functions()

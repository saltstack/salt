'''
The salt cloud module loader interface
'''
# Import python libs
import os

# Import Salt libs
import salt.loader
import saltcloud

salt.loader.salt_base_path = os.path.dirname(saltcloud.__file__)

def clouds(opts):
    '''
    Return the cloud functions
    '''
    load = salt.loader._create_loader(opts, 'clouds', 'cloud')
    return load.gen_functions()

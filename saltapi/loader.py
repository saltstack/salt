'''
The salt cloud module loader interface
'''
# Import python libs
import os

# Import Salt libs
import salt.loader
import saltcloud

salt.loader.salt_base_path = os.path.dirname(saltapi.__file__)

def netapi(opts):
    '''
    Return the network api functions
    '''
    load = salt.loader._create_loader(opts, 'netapi', 'netapi')
    return load.gen_functions()

def netauth(opts):
    '''
    Return the network auth functions
    '''
    load = salt.loader._create_loader(opts, 'netauth', 'netauth')
    return load.gen_functions()

'''
The salt api module loader interface
'''
# Import python libs
import os

# Import Salt libs
import salt.loader
import salt.netapi
import salt


def netapi(opts):
    '''
    Return the network api functions
    '''
    load = salt.loader._create_loader(
            opts,
            'netapi',
            'netapi',
            base_path=os.path.dirname(salt.netapi.__file__)
            )
    return load.gen_functions()

def runner(opts):
    '''
    Load the runners, this function bypasses the issue with the altered
    basepath
    '''
    load = salt.loader._create_loader(
            opts,
            'runners',
            'runner',
            ext_type_dirs='runner_dirs',
            base_path=os.path.dirname(salt.__file__)
            )
    return load.gen_functions()

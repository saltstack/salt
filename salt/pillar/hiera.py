'''
Take in a hiera configuration file location and execute it.
Adds the hiera data to pillar
'''

# Import third party libs
import yaml

def ext_pillar(conf):
    '''
    Execute hiera and return the data
    '''
    cmd = 'hiera {0}'.format(conf)
    for key, val in __grains__.items():
        if isinstance(val, string_types):
            cmd += ' {0}={1}'.format(key, val)
    return yaml.safe_load(__salt__['cmd.run'](cmd))

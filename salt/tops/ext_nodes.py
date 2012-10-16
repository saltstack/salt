'''
The cmd_yaml replaces the original ext_nodes function
'''

# Import python libs
import subprocess

# Import third party libs
import yaml

# Import Salt libs
import salt.utils


def __virtual__():
    '''
    Only run if properly configured
    '''
    if __opts__['master_tops'].get('ext_nodes'):
        return 'ext_nodes'
    return False


def top(**kwargs):
    '''
    Run the command configured
    '''
    if not 'id' in kwargs['opts']:
        return {}
    cmd = '{0} {1}'.format(__opts__['master_tops']['ext_nodes'], kwargs['opts']['id'])
    ndata = yaml.safe_load(
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0])
    print ndata
    ret = {}
    if 'environment' in ndata:
        env = ndata['environment']
    else:
        env = 'base'

    if 'classes' in ndata:
        if isinstance(ndata['classes'], dict):
            ret[env] = list(ndata['classes'])
        elif isinstance(ndata['classes'], list):
            ret[env] = ndata['classes']
        else:
            return ret
    return ret 

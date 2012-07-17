'''
Support for pkgng
'''

import os 

def __virtual__():
    '''
    Pkgng module load on FreeBSD only.
    '''
    if __grains__['os'] == 'FreeBSD':
        return 'pkgng'
    else:
        return False


def parse_config(file_name='/usr/local/etc/pkg.conf'):
    '''
    Return dict of uncommented global variables.

    CLI Example::

        salt '*' pkgng.parse_config
        *NOTE* not working right
    '''
    ret = {}
    l = []
    if not os.path.isfile(file_name):
        return 'Unable to find {0} on file system'.format(file_name)

    with open(file_name) as f:
        for line in f.readlines():
            if line.startswith("#") or line.startswith("\n"):
                pass
            else:
                k, v = line.split('\t')
                ret[k] = v
                l.append(line)
    ret['config_file'] = file_name
    return ret


def version():
    '''return the version of pkgng'''
    cmd = 'pkg -v'
    return __salt__['cmd.run'](cmd)


def update_package_site(new_url):
    '''
    Updates remote package repo url, PACKAGESITE var to be exact.

    Must be using http://, ftp://, or https// protos

    CLI Example::
        salt '*' pkgng.update_package_site http://127.0.0.1/
    '''
    config_file = parse_config()['config_file']
    __salt__['file.sed'](config_file,'PACKAGESITE.*', \
        'PACKAGESITE\t : {0}'.format(new_url))

    # add change return later
    return True

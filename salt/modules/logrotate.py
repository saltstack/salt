'''
Module for managing logrotate.
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
default_conf = '/etc/logrotate.conf'


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms
    disable = ('Windows',)
    if __grains__['os'] in disable:
        return False
    return 'logrotate'


def _parse_conf(conf_file=default_conf):
    '''
    Parse a logrotate configuration file.

    Includes will also be parsed, and their configuration will be stored in the
    return dict, as if they were part of the main config file. A dict of which
    configs came from which includes will be stored in the 'include files' dict
    inside the return dict, for later reference by the user or module.
    '''
    conf_path = os.path.dirname(conf_file)
    ret = {}
    mode = 'single'
    multi_name = ''
    multi = {}
    with salt.utils.fopen(conf_file, 'r') as ifile:
        for line in ifile.readlines():
            if not line.strip():
                continue
            if line.strip().startswith('#'):
                continue

            comps = line.strip().split()
            if '{' in line and not '}' in line:
                mode = 'multi'
                multi_name = comps[0]
                continue
            if '}' in line:
                mode = 'single'
                ret[multi_name] = multi
                multi_name = ''
                multi = {}
                continue

            if mode == 'single':
                key = ret
            else:
                key = multi

            if comps[0] == 'include':
                if not 'include files' in ret:
                    ret['include files'] = {}
                for include in os.listdir(comps[1]):
                    if not include in ret['include files']:
                        ret['include files'][include] = []
                    include_path = '{0}/{1}'.format(comps[1], include)
                    include_conf = _parse_conf(include_path)
                    for file_key in include_conf:
                        ret[file_key] = include_conf[file_key]
                        ret['include files'][include].append(file_key)

            if len(comps) > 1:
                key[comps[0]] = ' '.join(comps[1:])
            else:
                key[comps[0]] = True
    return ret


def show_conf(conf_file=default_conf):
    '''
    Show parsed configuration

    CLI Example::

        salt '*' logrotate.show_conf
    '''
    return _parse_conf(conf_file)

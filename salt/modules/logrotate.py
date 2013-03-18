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


def set(key, value, setting=None, conf_file=default_conf):
    '''
    Set a new value for a specific configuration line

    CLI Example::

        salt '*' logrotate.set rotate 2

    Can also be used to set a single value inside a multiline configuration
    block. For instance, to change rotate in the following block::

        /var/log/wtmp {
            monthly
            create 0664 root root
            rotate 1
        }

    Use the following command::

        salt '*' logrotate.set /var/log/wtmp rotate 2

    This module also has the ability to scan files inside an include directory,
    and make changes in the appropriate file.
    '''
    conf = _parse_conf(conf_file)
    for include in conf['include files']:
        if key in conf['include files'][include]:
            conf_file = os.path.join(conf['include'], include)

    if type(conf[key]) is dict and not setting:
        return ('Error: {0} includes a dict, and a specific setting inside the '
                'dict was not declared'.format(key))

    if setting:
        if type(conf[key]) is str:
            return ('Error: A setting for a dict was declared, but the '
                    'configuration line given is not a dict')
        # We're going to be rewriting an entire stanza
        stanza = conf[key]
        if value == 'False':
            del stanza[value]
        else:
            stanza[value] = setting
        new_line = _dict_to_stanza(key, stanza)
        log.debug(stanza)
        log.debug(new_line)
        log.debug(key)
        __salt__['file.psed'](conf_file,
                              '{0}.*{{.*}}'.format(key),
                              new_line)
    else:
        # This is the new config line that will be set
        if value == 'True':
            new_line = key
        elif value == 'False':
            new_line = ''
        else:
            new_line = '{0} {1}'.format(key, value)

        log.debug(conf_file)
        log.debug(key)
        log.debug(new_line)
        __salt__['file.psed'](conf_file,
                              '^{0}.*'.format(key),
                              new_line,
                              flags='gM')


def _dict_to_stanza(key, stanza):
    '''
    Convert a dict to a multi-line stanza
    '''
    ret = ''
    for skey in stanza:
        if stanza[skey] is True:
            stanza[skey] = ''
        ret += '    {0} {1}\n'.format(skey, stanza[skey])
    return '{0} {{\n{1}}}'.format(key, ret)


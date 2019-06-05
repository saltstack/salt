# -*- coding: utf-8 -*-
'''
Support for Linux File Access Control Lists

The Linux ACL module requires the `getfacl` and `setfacl` binaries.

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.path
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'acl'


def __virtual__():
    '''
    Only load the module if getfacl is installed
    '''
    if salt.utils.path.which('getfacl'):
        return __virtualname__
    return (False, 'The linux_acl execution module cannot be loaded: the getfacl binary is not in the path.')


def version():
    '''
    Return facl version from getfacl --version

    CLI Example:

    .. code-block:: bash

        salt '*' acl.version
    '''
    cmd = 'getfacl --version'
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split()
    return ret[1].strip()


def _raise_on_no_files(*args):
    if len(args) == 0:
        raise CommandExecutionError('You need to specify at least one file or directory to work with!')


def getfacl(*args, **kwargs):
    '''
    Return (extremely verbose) map of FACLs on specified file(s)

    CLI Examples:

    .. code-block:: bash

        salt '*' acl.getfacl /tmp/house/kitchen
        salt '*' acl.getfacl /tmp/house/kitchen /tmp/house/livingroom
        salt '*' acl.getfacl /tmp/house/kitchen /tmp/house/livingroom recursive=True
    '''
    recursive = kwargs.pop('recursive', False)

    _raise_on_no_files(*args)

    ret = {}
    cmd = 'getfacl --absolute-names'
    if recursive:
        cmd += ' -R'
    for dentry in args:
        cmd += ' "{0}"'.format(dentry)
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    dentry = ''
    for line in out:
        if not line:
            continue
        elif line.startswith('getfacl'):
            continue
        elif line.startswith('#'):
            comps = line.replace('# ', '').split(': ')
            if comps[0] == 'file':
                dentry = comps[1]
                ret[dentry] = {'comment': {},
                               'user': [],
                               'group': []}
            ret[dentry]['comment'][comps[0]] = comps[1]
            if comps[0] == 'flags':
                flags = list(comps[1])
                if flags[0] == 's':
                    ret[dentry]['suid'] = True
                if flags[1] == 's':
                    ret[dentry]['sgid'] = True
                if flags[2] == 't':
                    ret[dentry]['sticky'] = True
        else:
            vals = _parse_acl(acl=line,
                              user=ret[dentry]['comment']['owner'],
                              group=ret[dentry]['comment']['group'])
            acl_type = vals['type']
            del vals['type']
            for entity in ('user', 'group'):
                if entity in vals:
                    usergroup = vals[entity]
                    del vals[entity]
                    if acl_type == 'acl':
                        ret[dentry][entity].append({usergroup: vals})
                    elif acl_type == 'default':
                        if 'defaults' not in ret[dentry]:
                            ret[dentry]['defaults'] = {}
                        if entity not in ret[dentry]['defaults']:
                            ret[dentry]['defaults'][entity] = []
                        ret[dentry]['defaults'][entity].append({usergroup: vals})
            for entity in ('other', 'mask'):
                if entity in vals:
                    del vals[entity]
                    if acl_type == 'acl':
                        ret[dentry][entity] = [{"": vals}]
                    elif acl_type == 'default':
                        if 'defaults' not in ret[dentry]:
                            ret[dentry]['defaults'] = {}
                        ret[dentry]['defaults'][entity] = [{"": vals}]

    return ret


def _parse_acl(acl, user, group):
    '''
    Parse a single ACL rule
    '''
    comps = acl.split(':')
    vals = {}

    # What type of rule is this?
    vals['type'] = 'acl'
    if comps[0] == 'default':
        vals['type'] = 'default'
        comps.pop(0)

    # If a user is not specified, use the owner of the file
    if comps[0] == 'user' and not comps[1]:
        comps[1] = user
    elif comps[0] == 'group' and not comps[1]:
        comps[1] = group
    vals[comps[0]] = comps[1]

    # Set the permissions fields
    octal = 0
    vals['permissions'] = {}
    if 'r' in comps[-1]:
        octal += 4
        vals['permissions']['read'] = True
    else:
        vals['permissions']['read'] = False
    if 'w' in comps[-1]:
        octal += 2
        vals['permissions']['write'] = True
    else:
        vals['permissions']['write'] = False
    if 'x' in comps[-1]:
        octal += 1
        vals['permissions']['execute'] = True
    else:
        vals['permissions']['execute'] = False
    vals['octal'] = octal

    return vals


def wipefacls(*args, **kwargs):
    '''
    Remove all FACLs from the specified file(s)

    CLI Examples:

    .. code-block:: bash

        salt '*' acl.wipefacls /tmp/house/kitchen
        salt '*' acl.wipefacls /tmp/house/kitchen /tmp/house/livingroom
        salt '*' acl.wipefacls /tmp/house/kitchen /tmp/house/livingroom recursive=True
    '''
    recursive = kwargs.pop('recursive', False)

    _raise_on_no_files(*args)
    cmd = 'setfacl -b'
    if recursive:
        cmd += ' -R'
    for dentry in args:
        cmd += ' "{0}"'.format(dentry)
    __salt__['cmd.run'](cmd, python_shell=False)
    return True


def _acl_prefix(acl_type):
    prefix = ''
    if acl_type.startswith('d'):
        prefix = 'd:'
        acl_type = acl_type.replace('default:', '')
        acl_type = acl_type.replace('d:', '')
    if acl_type == 'user' or acl_type == 'u':
        prefix += 'u'
    elif acl_type == 'group' or acl_type == 'g':
        prefix += 'g'
    elif acl_type == 'mask' or acl_type == 'm':
        prefix += 'm'
    return prefix


def modfacl(acl_type, acl_name='', perms='', *args, **kwargs):
    '''
    Add or modify a FACL for the specified file(s)

    CLI Examples:

    .. code-block:: bash

        salt '*' acl.modfacl user myuser rwx /tmp/house/kitchen
        salt '*' acl.modfacl default:group mygroup rx /tmp/house/kitchen
        salt '*' acl.modfacl d:u myuser 7 /tmp/house/kitchen
        salt '*' acl.modfacl g mygroup 0 /tmp/house/kitchen /tmp/house/livingroom
        salt '*' acl.modfacl user myuser rwx /tmp/house/kitchen recursive=True
        salt '*' acl.modfacl user myuser rwx /tmp/house/kitchen raise_err=True
    '''
    recursive = kwargs.pop('recursive', False)
    raise_err = kwargs.pop('raise_err', False)

    _raise_on_no_files(*args)

    cmd = 'setfacl'
    if recursive:
        cmd += ' -R'  # -R must come first as -m needs the acl_* arguments that come later

    cmd += ' -m'

    cmd = '{0} {1}:{2}:{3}'.format(cmd, _acl_prefix(acl_type), acl_name, perms)

    for dentry in args:
        cmd += ' "{0}"'.format(dentry)
    __salt__['cmd.run'](cmd, python_shell=False, raise_err=raise_err)
    return True


def delfacl(acl_type, acl_name='', *args, **kwargs):
    '''
    Remove specific FACL from the specified file(s)

    CLI Examples:

    .. code-block:: bash

        salt '*' acl.delfacl user myuser /tmp/house/kitchen
        salt '*' acl.delfacl default:group mygroup /tmp/house/kitchen
        salt '*' acl.delfacl d:u myuser /tmp/house/kitchen
        salt '*' acl.delfacl g myuser /tmp/house/kitchen /tmp/house/livingroom
        salt '*' acl.delfacl user myuser /tmp/house/kitchen recursive=True
    '''
    recursive = kwargs.pop('recursive', False)

    _raise_on_no_files(*args)

    cmd = 'setfacl'
    if recursive:
        cmd += ' -R'

    cmd += ' -x'

    cmd = '{0} {1}:{2}'.format(cmd, _acl_prefix(acl_type), acl_name)

    for dentry in args:
        cmd += ' "{0}"'.format(dentry)
    __salt__['cmd.run'](cmd, python_shell=False)
    return True

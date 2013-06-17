'''
Support for Linux File Access Control Lists
'''

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load the module if getfacl is installed
    '''
    if salt.utils.which('getfacl'):
        return 'acl'
    return False


def version():
    '''
    Return facl version from getfacl --version

    CLI Example::

        salt '*' acl.version
    '''
    cmd = 'getfacl --version'
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split()
    return ret[1].strip()


def getfacl(*args):
    '''
    Return (extremely verbose) map of FACLs on specified file(s)
    CLI Examples::

        salt '*' acl.getfacl /tmp/house/kitchen
        salt '*' acl.getfacl /tmp/house/kitchen /tmp/house/livingroom
    '''
    ret = {}
    cmd = 'getfacl -p'
    for dentry in args:
        cmd += ' {0}'.format(dentry)
    out = __salt__['cmd.run'](cmd).splitlines()
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
                ret[dentry] = {'comments': {},
                               'users': [],
                               'groups': []}
            ret[dentry]['comments'][comps[0]] = comps[1]
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
                              user=ret[dentry]['comments']['owner'],
                              group=ret[dentry]['comments']['group'])
            acl_type = vals['type']
            del vals['type']
            for entity in ('user', 'group'):
                plural = entity + 's'
                if entity in vals.keys():
                    usergroup = vals[entity]
                    del vals[entity]
                    if acl_type == 'acl':
                        ret[dentry][plural].append({usergroup: vals})
                    elif acl_type == 'default':
                        if 'defaults' not in ret[dentry].keys():
                            ret[dentry]['defaults'] = {}
                        if plural not in ret[dentry]['defaults'].keys():
                            ret[dentry]['defaults'][plural] = []
                        ret[dentry]['defaults'][plural].append({usergroup: vals})
            for entity in ('other', 'mask'):
                if entity in vals.keys():
                    del vals[entity]
                    ret[dentry][entity] = vals
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
    if 'r' in comps[2]:
        octal += 4
        vals['permissions']['read'] = True
    else:
        vals['permissions']['read'] = False
    if 'w' in comps[2]:
        octal += 2
        vals['permissions']['write'] = True
    else:
        vals['permissions']['write'] = False
    if 'x' in comps[2]:
        octal += 1
        vals['permissions']['execute'] = True
    else:
        vals['permissions']['execute'] = False
    vals['octal'] = octal

    return vals


def wipefacls(*args):
    '''
    Remove all FACLs from the specified file(s)
    CLI Examples::

        salt '*' acl.wipefacls /tmp/house/kitchen
        salt '*' acl.wipefacls /tmp/house/kitchen /tmp/house/livingroom
    '''
    cmd = 'setfacl -b'
    for dentry in args:
        cmd += ' {0}'.format(dentry)
    __salt__['cmd.run'](cmd)
    return True


def modfacl(acl_type, acl_name, perms, *args):
    '''
    Add or modify a FACL for the specified file(s)
    CLI Examples::

        salt '*' acl.addfacl user myuser rwx /tmp/house/kitchen
        salt '*' acl.addfacl default:group mygroup rx /tmp/house/kitchen
        salt '*' acl.addfacl d:u myuser 7 /tmp/house/kitchen
        salt '*' acl.addfacl g mygroup 0 /tmp/house/kitchen /tmp/house/livingroom
    '''
    cmd = 'setfacl -m'

    prefix = ''
    if acl_type.startswith('d'):
        prefix = 'd:'
        acl_type = acl_type.replace('default:', '')
        acl_type = acl_type.replace('d:', '')
    if acl_type == 'user' or acl_type == 'u':
        prefix += 'u'
    elif acl_type == 'group' or acl_type == 'g':
        prefix += 'g'
    cmd = '{0} {1}:{2}:{3}'.format(cmd, prefix, acl_name, perms)

    for dentry in args:
        cmd += ' {0}'.format(dentry)
    __salt__['cmd.run'](cmd)
    return True


def delfacl(acl_type, acl_name, *args):
    '''
    Remove specific FACL from the specified file(s)
    CLI Examples::

        salt '*' acl.delfacl user myuser /tmp/house/kitchen
        salt '*' acl.delfacl default:group mygroup /tmp/house/kitchen
        salt '*' acl.delfacl d:u myuser /tmp/house/kitchen
        salt '*' acl.delfacl g myuser /tmp/house/kitchen /tmp/house/livingroom
    '''
    cmd = 'setfacl -x'

    prefix = ''
    if acl_type.startswith('d'):
        prefix = 'd:'
        acl_type = acl_type.replace('default:', '')
        acl_type = acl_type.replace('d:', '')
    if acl_type == 'user' or acl_type == 'u':
        prefix += 'u'
    elif acl_type == 'group' or acl_type == 'g':
        prefix += 'g'
    cmd = '{0} {1}:{2}'.format(cmd, prefix, acl_name)

    for dentry in args:
        cmd += ' {0}'.format(dentry)
    __salt__['cmd.run'](cmd)
    return True

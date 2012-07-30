'''
Manage the information in the aliases file
'''

# Import python libs
import os
import re
import stat
import tempfile

__ALIAS_RE = re.compile(r'([^:#]*)\s*:?\s*([^#]*?)(\s+#.*|$)')


def __get_aliases_filename():
    '''
    Return the path to the appropriate aliases file
    '''
    if 'aliases.file' in __opts__:
        return __opts__['aliases.file']
    elif 'aliases.file' in __pillar__:
        return __pillar__['aliases.file']
    else:
        return '/etc/aliases'


def __parse_aliases():
    '''
    Parse the aliases file, and return a list of line components:

    [
      (alias1, target1, comment1),
      (alias2, target2, comment2),
    ]
    '''
    afn = __get_aliases_filename()
    ret = []
    if not os.path.isfile(afn):
        return ret
    for line in open(afn).readlines():
        m = __ALIAS_RE.match(line)
        if m:
            ret.append(m.groups())
        else:
            ret.append((None, None, line.strip()))
    return ret


def __write_aliases_file(lines):
    '''
    Write a new copy of the aliases file.  Lines is a list of lines
    as returned by __parse_aliases.
    '''
    afn = __get_aliases_filename()
    adir = os.path.dirname(afn)

    out = tempfile.NamedTemporaryFile(dir=adir, delete=False)

    if not __opts__.get('integration.test', False):
        if os.path.isfile(afn):
            st = os.stat(afn)
            os.chmod(out.name, stat.S_IMODE(st.st_mode))
            os.chown(out.name, st.st_uid, st.st_gid)
        else:
            os.chmod(out.name, 0o644)
            os.chown(out.name, 0, 0)

    for (line_alias, line_target, line_comment) in lines:
        if not line_comment:
            line_comment = ''
        if line_alias and line_target:
            out.write('%s: %s%s\n' % (line_alias, line_target, line_comment))
        else:
            out.write('%s\n' % line_comment)

    out.close()
    os.rename(out.name, afn)

    newaliases_path = '/usr/bin/newaliases'
    if os.path.exists(newaliases_path):
        __salt__['cmd.run'](newaliases_path)

    return True


def list_aliases():
    '''
    Return the aliases found in the aliases file in this format::

        {'<alias>': '<target>'}

    CLI Example::

        salt '*' aliases.list_aliases
    '''
    ret = {}
    for alias, target, comment in __parse_aliases():
        if not alias:
            continue
        ret[alias] = target
    return ret


def get_target(alias):
    '''
    Return the target associated with an alias

    CLI Example::

        salt '*' aliases.get_target <alias>
    '''
    aliases = list_aliases()
    if alias in aliases:
        return aliases[alias]
    return ''


def has_target(alias, target):
    '''
    Return true if the alias/target is set

    CLI Example::

        salt '*' aliases.has_target <alias> <target>
    '''
    aliases = list_aliases()
    return alias in aliases and target == aliases[alias]


def set_target(alias, target):
    '''
    Set the entry in the aliases file for the given alias, this will overwrite
    any previous entry for the given alias or create a new one if it does not
    exist.

    CLI Example::

        salt '*' aliases.set_target <alias> <target>
    '''

    if get_target(alias) == target:
        return True

    lines = __parse_aliases()
    out = []
    ovr = False
    for (line_alias, line_target, line_comment) in lines:
        if line_alias == alias:
            if not ovr:
                out.append((alias, target, line_comment))
                ovr = True
        else:
            out.append((line_alias, line_target, line_comment))
    if not ovr:
        out.append((alias, target, ''))

    __write_aliases_file(out)
    return True


def rm_alias(alias):
    '''
    Remove an entry from the aliases file

    CLI Example::

        salt '*' aliases.rm_alias <alias>
    '''
    if not get_target(alias):
        return True

    lines = __parse_aliases()
    out = []
    for (line_alias, line_target, line_comment) in lines:
        if line_alias != alias:
            out.append((line_alias, line_target, line_comment))

    __write_aliases_file(out)
    return True

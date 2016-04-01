# -*- coding: utf-8 -*-
'''
Work with incron
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
import salt.utils
from salt.ext.six.moves import range

# Set up logging
log = logging.getLogger(__name__)

TAG = '# Line managed by Salt, do not edit'
_INCRON_SYSTEM_TAB = '/etc/incron.d/'

_MASK_TYPES = [
    'IN_ACCESS', 'IN_ATTRIB', 'IN_CLOSE_WRITE',
    'IN_CLOSE_NOWRITE', 'IN_CREATE', 'IN_DELETE',
    'IN_DELETE_SELF', 'IN_MODIFY', 'IN_MOVE_SELF',
    'IN_MOVED_FROM', 'IN_MOVED_TO', 'IN_OPEN',
    'IN_ALL_EVENTS', 'IN_MOVE', 'IN_CLOSE',
    'IN_DONT_FOLLOW', 'IN_ONESHOT', 'IN_ONLYDIR',
    'IN_NO_LOOP'
]


def _needs_change(old, new):
    if old != new:
        if new == 'random':
            # Allow switch from '*' or not present to 'random'
            if old == '*':
                return True
        elif new is not None:
            return True
    return False


def _render_tab(lst):
    '''
    Takes a tab list structure and renders it to a list for applying it to
    a file
    '''
    ret = []
    for pre in lst['pre']:
        ret.append('{0}\n'.format(pre))
    for cron in lst['crons']:
        ret.append('{0} {1} {2} {3}\n'.format(cron['path'],
                                                      cron['mask'],
                                                      cron['cmd'],
                                                      TAG
                                                      )
                   )
    return ret


def _get_incron_cmdstr(path):
    '''
    Returns a format string, to be used to build an incrontab command.
    '''
    return 'incrontab {0}'.format(path)


def write_incron_file(user, path):
    '''
    Writes the contents of a file to a user's incrontab

    CLI Example:

    .. code-block:: bash

        salt '*' incron.write_incron_file root /tmp/new_incron
    '''
    return __salt__['cmd.retcode'](_get_incron_cmdstr(path), runas=user, python_shell=False) == 0


def write_incron_file_verbose(user, path):
    '''
    Writes the contents of a file to a user's incrontab and return error message on error

    CLI Example:

    .. code-block:: bash

        salt '*' incron.write_incron_file_verbose root /tmp/new_incron
    '''
    return __salt__['cmd.run_all'](_get_incron_cmdstr(path), runas=user, python_shell=False)


def _write_incron_lines(user, lines):
    '''
    Takes a list of lines to be committed to a user's incrontab and writes it
    '''
    if user == 'system':
        ret = {}
        ret['retcode'] = _write_file(_INCRON_SYSTEM_TAB, 'salt', ''.join(lines))
        return ret
    else:
        path = salt.utils.mkstemp()
        with salt.utils.fopen(path, 'w+') as fp_:
            fp_.writelines(lines)
        if __grains__['os_family'] == 'Solaris' and user != "root":
            __salt__['cmd.run']('chown {0} {1}'.format(user, path), python_shell=False)
        ret = __salt__['cmd.run_all'](_get_incron_cmdstr(path), runas=user, python_shell=False)
        os.remove(path)
        return ret


def _write_file(folder, filename, data):
    '''
    Writes a file to disk
    '''
    path = os.path.join(folder, filename)
    if not os.path.exists(folder):
        msg = '{0} cannot be written. {1} does not exist'
        msg = msg.format(filename, folder)
        log.error(msg)
        raise AttributeError(msg)
    fout = salt.utils.fopen(path, 'w')
    fout.write(data)
    fout.close()

    return 0


def _read_file(folder, filename):
    '''
    Reads and returns the contents of a file
    '''
    path = os.path.join(folder, filename)
    try:
        with salt.utils.fopen(path, 'rb') as contents:
            return contents.readlines()
    except (OSError, IOError):
        return ''


def raw_system_incron():
    '''
    Return the contents of the system wide incrontab

    CLI Example:

    .. code-block:: bash

        salt '*' incron.raw_system_incron
    '''
    log.debug("read_file {0}" . format(_read_file(_INCRON_SYSTEM_TAB, 'salt')))
    return ''.join(_read_file(_INCRON_SYSTEM_TAB, 'salt'))


def raw_incron(user):
    '''
    Return the contents of the user's incrontab

    CLI Example:

    .. code-block:: bash

        salt '*' incron.raw_incron root
    '''
    if __grains__['os_family'] == 'Solaris':
        cmd = 'incrontab -l {0}'.format(user)
    else:
        cmd = 'incrontab -l -u {0}'.format(user)
    return __salt__['cmd.run_stdout'](cmd, rstrip=False, runas=user, python_shell=False)


def list_tab(user):
    '''
    Return the contents of the specified user's incrontab

    CLI Example:

    .. code-block:: bash

        salt '*' incron.list_tab root
    '''
    if user == 'system':
        data = raw_system_incron()
    else:
        data = raw_incron(user)
        log.debug("user data {0}" . format(data))
    ret = {'crons': [],
           'pre': []
           }
    flag = False
    comment = None
    tag = '# Line managed by Salt, do not edit'
    for line in data.splitlines():
        if line.endswith(tag):
            if len(line.split()) > 3:
                # Appears to be a standard incron line
                comps = line.split()
                path = comps[0]
                mask = comps[1]
                (cmd, comment) = ' '.join(comps[2:]).split(' # ')

                dat = {'path': path,
                       'mask': mask,
                       'cmd': cmd,
                       'comment': comment}
                ret['crons'].append(dat)
                comment = None
        else:
            ret['pre'].append(line)
    return ret

# For consistency's sake
ls = salt.utils.alias_function(list_tab, 'ls')


def set_job(user, path, mask, cmd):
    '''
    Sets an incron job up for a specified user.

    CLI Example:

    .. code-block:: bash

        salt '*' incron.set_job root '/root' 'IN_MODIFY' 'echo "$$ $@ $# $% $&"'
    '''
    # Scrub the types
    mask = str(mask).upper()

    # Check for valid mask types
    for item in mask.split(','):
        if item not in _MASK_TYPES:
            return 'Invalid mask type: {0}' . format(item)

    updated = False
    arg_mask = mask.split(',')
    arg_mask.sort()
    lst = list_tab(user)

    updated_crons = []
    # Look for existing incrons that have cmd, path and at least one of the MASKS
    # remove and replace with the one we're passed
    for item, cron in enumerate(lst['crons']):
        if path == cron['path']:
            if cron['cmd'] == cmd:
                cron_mask = cron['mask'].split(',')
                cron_mask.sort()
                if cron_mask == arg_mask:
                    return 'present'

                if any([x in cron_mask for x in arg_mask]):
                    updated = True
                else:
                    updated_crons.append(cron)
            else:
                updated_crons.append(cron)
        else:
            updated_crons.append(cron)

    cron = {'cmd': cmd, 'path': path, 'mask': mask}
    updated_crons.append(cron)

    lst['crons'] = updated_crons
    comdat = _write_incron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']

    if updated:
        return 'updated'
    else:
        return 'new'


def rm_job(user,
           path,
           mask,
           cmd):
    '''
    Remove a incron job for a specified user. If any of the day/time params are
    specified, the job will only be removed if the specified params match.

    CLI Example:

    .. code-block:: bash

        salt '*' incron.rm_job root /path
    '''

    # Scrub the types
    mask = str(mask).upper()

    # Check for valid mask types
    for item in mask.split(','):
        if item not in _MASK_TYPES:
            return 'Invalid mask type: {0}' . format(item)

    lst = list_tab(user)
    ret = 'absent'
    rm_ = None
    for ind in range(len(lst['crons'])):
        if rm_ is not None:
            break
        if path == lst['crons'][ind]['path']:
            if cmd == lst['crons'][ind]['cmd']:
                if mask == lst['crons'][ind]['mask']:
                    rm_ = ind
    if rm_ is not None:
        lst['crons'].pop(rm_)
        ret = 'removed'
    comdat = _write_incron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']

    return ret

rm = salt.utils.alias_function(rm_job, 'rm')

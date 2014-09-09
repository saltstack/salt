# -*- coding: utf-8 -*-
'''
Salt interface to ZFS commands
'''

# Import Python libs
import logging

# Some std libraries that are made
# use of.
import re
import sys

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
import salt.modules.cmdmod as salt_cmd

log = logging.getLogger(__name__)

# Function alias to set mapping. Filled
# in later on.
__func_alias__ = {}


@decorators.memoize
def _check_zfs():
    '''
    Looks to see if zfs is present on the system.
    '''
    # Get the path to the zfs binary.
    return salt.utils.which('zfs')


def _available_commands():
    '''
    List available commands based on 'zfs -?'. Returns a dict.
    '''
    zfs_path = _check_zfs()
    if not zfs_path:
        return False

    ret = {}
    # Note that we append '|| :' as a unix hack to force return code to be 0.
    res = salt_cmd.run_stdout(
        '{0} -? || :'.format(zfs_path), output_loglevel='trace'
    )

    # This bit is dependent on specific output from `zfs -?` - any major changes
    # in how this works upstream will require a change.
    for line in res.splitlines():
        if re.match('	[a-zA-Z]', line):
            cmds = line.split(' ')[0].split('|')
            doc = ' '.join(line.split(' ')[1:])
            for cmd in [cmd.strip() for cmd in cmds]:
                if cmd not in ret:
                    ret[cmd] = doc
    return ret


def _exit_status(retcode):
    '''
    Translate exit status of zfs
    '''
    ret = {0: 'Successful completion.',
           1: 'An error occurred.',
           2: 'Usage error.'
          }[retcode]
    return ret


def __virtual__():
    '''
    Makes sure that ZFS is available.
    '''
    if _check_zfs():
        return 'zfs'
    return False


def _add_doc(func, doc, prefix='\n\n    '):
    if not func.__doc__:
        func.__doc__ = ''
    func.__doc__ += '{0}{1}'.format(prefix, doc)


def _make_function(cmd_name, doc):
    '''
    Returns a function based on the command name.
    '''
    def _cmd(*args):
        # Define a return value.
        ret = {}

        # Run the command.
        res = salt_cmd.run_all(
                '{0} {1} {2}'.format(
                    _check_zfs(),
                    cmd_name,
                    ' '.join(args)
                    )
                )

        # Make a note of the error in the return object if retcode
        # not 0.
        if res['retcode'] != 0:
            ret['Error'] = _exit_status(res['retcode'])

        # Set the output to be splitlines for now.
        ret = res['stdout'].splitlines()

        return ret

    _add_doc(_cmd, 'This function is dynamically generated.', '\n    ')
    _add_doc(_cmd, doc)
    _add_doc(_cmd, '\n    CLI Example:\n\n')
    _add_doc(_cmd, '\n        salt \'*\' zfs.{0} <args>'.format(cmd_name))

    # At this point return the function we've just defined.
    return _cmd

# Run through all the available commands
if _check_zfs():
    available_cmds = _available_commands()
    for available_cmd in available_cmds:

        # Set the output from _make_function to be 'available_cmd_'.
        # ie 'list' becomes 'list_' in local module.
        setattr(
                sys.modules[__name__],
                '{0}_'.format(available_cmd),
                _make_function(available_cmd, available_cmds[available_cmd])
                )

        # Update the function alias so that salt finds the functions properly.
        __func_alias__['{0}_'.format(available_cmd)] = available_cmd

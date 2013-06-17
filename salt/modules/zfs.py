''' Module for running ZFS command
'''

# Import Python libs
import logging

# Some std libraries that are made
# use of.
import re
import sys

# Import Salt libs
import salt.utils
import salt.modules.cmdmod as salt_cmd

log = logging.getLogger(__name__)

# Function alias to set mapping. Filled
# in later on.
__func_alias__ = {}

@salt.utils.memoize
def _check_zfs():
    '''
    Looks to see if zfs is present on the system.
    '''
    # Get the path to the zfs binary.
    return salt.utils.which('zfs')


def _available_commands():
    '''
    List available commands based on 'zfs help'. Either
    returns a list, or False.
    '''
    zfs_path = _check_zfs()
    if not zfs_path:
        return False

    _return = []
    # Note that we append '|| :' as a unix hack to force return code to be 0.
    res = salt_cmd.run_all('{0} help || :'.format(zfs_path))

    # This bit is dependant on specific output from `zfs help` - any major changes
    # in how this works upstream will require a change.
    for line in res['stderr'].splitlines():
        if re.match('	[a-zA-Z]', line):
            for cmd in [cmd.strip() for cmd in line.split(' ')[0].split('|')]:
                if cmd not in _return:
                    _return.append(cmd)
    return _return


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


def _make_function(cmd_name):
    '''
    Returns a function based on the command name.
    '''
    def _cmd(*args):
        '''
        Generated function. Maybe at some point in the
        future, fill this in dynamically.
        '''
        # Define a return value.
        ret = {}

        # Run the command.
        res = salt_cmd.run_all(
                '%s %s %s'.format(
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

    # At this point return the function we've just defined.
    return _cmd

# Run through all the available commands
if _check_zfs():
    for available_cmd in _available_commands():

        # Set the output from _make_function to be 'available_cmd_'.
        # ie 'list' becomes 'list_' in local module.
        setattr(
                sys.modules[__name__],
                '{0}_'.format(available_cmd),
                _make_function(available_cmd)
                )

        # Update the function alias so that salt finds the functions properly.
        __func_alias__['{0}_'.format(available_cmd)] = available_cmd

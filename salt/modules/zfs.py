'''
Module for running ZFS command
'''

# Import Python libs
import logging

# Regular expressions for matching output
# from 'zfs help'
import re

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

# Function alias to set mapping.
__func_alias__ = {
    'list_': 'list'
}

@salt.utils.memoize
def _check_zfs( ):
    '''
    Looks to see if zfs is present on the system.

    Optional command check.
    '''

    # Get the path to the zfs binary.
    return salt.utils.which('zfs')

def _available_commands( ):
    '''
    List available commands based on 'zfs help'. Either
    returns a list, or False.
    '''
    zfs_path = _check_zfs( )
    if not zfs_path:
        return False

    _return = [ ]
    # Note that we append '|| :' as a unix hack to force return code to be 0.
    res = __salt__['cmd.run_all']("%s help || :" % zfs_path)
    for line in res['stderr'].splitlines( ):
        if re.match( "	[a-zA-Z]", line ):
            for cmd in [ cmd.strip() for cmd in line.split( " " )[0].split( "|" ) ]:
                if cmd not in _return:
                    _return.append( cmd )
    return _return

def _check_command( command ):
    '''
    Simple check to see if the command is valid.
    '''
    return command in _available_commands( )

def _exit_status(retcode):
    '''
    Translate exit status of zfs
    '''
    ret = { 0 : 'Successful completion.',
            1 : 'An error occurred.',
            2 : 'Usage error.'
          }[retcode]
    return ret

def __virtual__():
    '''
    Makes sure that ZFS is available.
    '''
    if _check_zfs( ):
        return 'zfs'
    return False

# At this point use the helper commands to dynamically generate
# functions that are available.
#for available_cmd in _available_commands( ):
    # Define a new function here based on avaiable_cmd.
    # Also update __func_alias__
    #log.debug( "Would create function for %s" % available_cmd )
    # Use setattr( globals( ), new_func, "%_" % available_cmd )

def list_(*args):
    '''
    List all filesystems and volumes properties. If 'snapshot' given : list
    snapshots
    
    CLI Example::

        salt '*' zfs.list [snapshot] 
    '''
    ret = {}
    zfs = _check_zfs()
    if len(args) == 1 and 'snapshot' in args:
        cmd = '{0} list -t snapshot'.format(zfs)
    else:
        cmd = '{0} list'.format(zfs)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret = res['stdout'].splitlines()
    return ret

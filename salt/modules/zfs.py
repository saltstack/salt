''' Module for running ZFS command
'''

# Import Python libs
import logging

# Regular expressions for matching output
# from 'zfs help'
import re

import sys

# Import Salt libs
import salt.utils
import salt.modules.cmdmod as salt_cmd

log = logging.getLogger(__name__)

# Function alias to set mapping. Filled
# in later on.
__func_alias__ = { }

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
    res = salt_cmd.run_all("%s help || :" % zfs_path)
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

def _make_function( cmd_name ):
    '''
    Returns a function based on the command name.
    '''
    def _cmd( *args ):
        '''
        Generated function. Maybe at some point in the
        future, fill this in dynamically.
        '''
        # Define a return value.
        ret = { }

        # Run the command.
	#TODO - add arguments into this.
        res = salt_cmd.run_all( "%s %s %s" % ( _check_zfs( ), cmd_name, " ".join( args ) ) )

        # Make a note of the error in the return object if retcode
        # not 0.
        if res['retcode'] != 0:
            ret['Error'] = _exit_status( res['retcode'] )

        # Set the output to be splitlines for now.
        ret = res['stdout'].splitlines( )

        return ret

    # At this point return the function we've just defined.
    return _cmd

generated = { } 

# Run through all the available commands
for available_cmd in _available_commands( ):

    generated[available_cmd] = _make_function( available_cmd )
    setattr( sys.modules[__name__], "%s_" % available_cmd, generated[available_cmd] )

    # Update the function alias so that salt finds the functions properly.
    __func_alias__["%s_" % available_cmd] = available_cmd

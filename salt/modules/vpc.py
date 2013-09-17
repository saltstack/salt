'''
Amazon VPC Module
'''
import logging
import inspect
import re
import sys
import boto
import boto.vpc

log = logging.getLogger(__name__)

__func_alias__  = { }

def __virtual__( ):
    return 'vpc'

def _add_doc( func, doc, prefix='\n        ' ):
    '''
    Quick helper that allows for documentation
    to be added to a function.
    '''
    if not func.__doc__:
        func.__doc__ = '';
    func.__doc__ += '{0}{1}'.format(prefix, doc)

def _get_connection( ):
    '''
    Helper method to handle creation of the actual
    boto.vpc.VPCConnection object.

    Note that this is more complicated because when the module
    starts up we don't have access to __salt__.. so
    a dummy connection is made, with a dirty flag set.
    '''

    # Exit out if we've already got a connection obj.
    _conn   = getattr( sys.modules[__name__], "_conn", False )
    if _conn:
        return _conn

    # Try and grab the configuration. If this fails, use dummy
    # values. Also set the dirty flag.
    try:
        _key        = __salt__['config.option']('aws.key')
        _key_id     = __salt__['config.option']('aws.key_id')
        _dirty      = False
    except Exception:
        return boto.vpc.VPCConnection( "", "" )

    # We've got a valid configuration, so create the new object.
    conn   = boto.vpc.VPCConnection( _key, _key_id )
    setattr( sys.modules[__name__], "_conn", conn )
    return conn

def _create_func( function_name, function_obj ):
    '''
    Create a python function that is directly based on
    function_obj. Note that introspection is used to do this.
    '''

    arguments,vararguments,keywords,defaults = inspect.getargspec( function_obj )

    # Define the actual function we will return.
    def _f( *args ):
        '''
        This is a dynamically generated function from boto.
        '''

        # Currently the only input types for boto are list, string, or tuple.
        # Check the particular type, and change the execution args accordingly.
        # TODO

        # We wrap this in a try/catch as the boto function could 
        # raise an exception.
        try:
            _result = function_obj( *args )
        except Exception as e:
            return "ERROR: {0}".format(e)

    # Get the documentation from the object.
    doc = inspect.getdoc( function_obj )
    if doc:
        for line in doc.splitlines( ):
            _add_doc( _f, line )

    return _f

# Iterate over the boto object. Note that we're using an instance not a class
# because inspect.isfunction checks if the function is bound or not.
for member_name, member_method in inspect.getmembers( _get_connection( ) ):

    # We only want methods.
    if not inspect.ismethod( member_method ):
        continue

    # Limit the search to methods that are only in boto.vpc.VPCConnection, not
    # parents..
    if member_name in dir(boto.vpc.EC2Connection):
        continue

    # Blacklist __ functions..
    if re.compile( "^__" ).match( member_name ):
        continue

    # Call _create_func with the particular member name and function.
    # Then set it to be class wide. Note that we append of suffix
    # of '_' to methods that are generated out of _create_func.

    setattr(
            sys.modules[__name__],
            '{0}_'.format( member_name ),
            _create_func( member_name, member_method )
    )

    # Update func alias so that salt finds the new function.
    __func_alias__['{0}_'.format( member_name )] = member_name

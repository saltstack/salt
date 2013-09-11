'''
Amazon VPC Module
'''
import logging
import inspect
import re
import boto
import boto.vpc

log = logging.getLogger(__name__)

def __virtual__( ):
    return 'vpc'

def debug( ):
    return "Go away"

def _get_connection( ):
    '''
    Helper method to handle creation of the actual
    boto.vpc.VPCConnection object. This uses
    configuration values from salt.

    Also checks if one already exists.
    '''
    pass

def _create_func( function_name, function_obj ):
    '''
    Create a python function that is directly based on
    function_obj. Note that introspection is used to do this.
    '''

    # Get the documentation from the object.
    doc = inspect.getdoc( function_obj )
    
    # Get the signature of the function.
    spec = inspect.getargspec( function_obj )

    # Define the actual function we will return.
    def _f( *args ):
        # Use spec to reconcile what we get from *args
        # and call the boto function.

        # getattr( _get_connection( ), function_name ) is the actual boto obj.

        pass
    return _f

# Iterate over the boto class.
for member_name, member_method in inspect.getmembers( boto.vpc.VPCConnection ):
    
    log.debug( "I have member name of %s" % member_name )

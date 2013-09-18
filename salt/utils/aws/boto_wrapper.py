'''
Wrapper util for boto.
'''
import logging
import inspect
import re
import sys
import boto

log = logging.getLogger(__name__)

def _add_doc( func, doc, prefix='\n        ' ):
    '''
    Quick helper that allows for documentation
    to be added to a function.
    '''
    if not func.__doc__:
        func.__doc__ = '';
    func.__doc__ += '{0}{1}'.format(prefix, doc)

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

def create_functions( boto_submodule ):
    '''
    Return a dictionary of functions that have
    been created via _create_func.
    '''
    _r = { }

    # Parse boto_submodule and import the required module.

    # Get the actual boto object.
    # PLACEHOLDER
    boto_obj = boto.vpc.VPCConnection

    # Iterate over the boto object. Note that we're using an instance not a class
    # because inspect.isfunction checks if the function is bound or not.
    for member_name, member_method in inspect.getmembers( boto_obj ):

        # We only want methods.
        if not inspect.ismethod( member_method ):
            continue

        # Limit the search, inspect.getmembers will
        # iterate through the parent as well.
        if not member_name in dir( boto_obj ):
            continue

        # Blacklist __ functions..
        if re.compile( "^__" ).match( member_name ):
            continue

        _r[member_name] = _create_func( member_name, member_method )

    return _r

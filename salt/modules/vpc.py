'''
Amazon VPC Module
'''
import logging
import inspect
import re
import boto

log = logging.getLogger(__name__)

def __virtual__( ):
    return 'vpc'

# Define a whitelist of functions that we will match while inspecting boto.
whitelist = { "VPCConnection": [    re.compile("^create"),
                                    re.compile("^delete"),
                                    re.compile("^get") ] }

for key in whitelist:
    # Get the actual class object.
    _class = boto[key]

    # Iterate over all the members of that class.
    for member_name, member_method in inspect.getmembers( _class )

        # Iterate over all the valid patterns for this class, if we find a match then break out.
        found = False
        for _regex in whitelist[key]
            if _regex.match( member_name ):
                found = True
                break

        # Skip members that don't match the regex.
        if not found:
            continue

        log.debug( "I have member name of %s" % member_name )

# VPCConnection iteration..

# Iterate over boto.vpc to figure out what options are available.


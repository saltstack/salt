'''
Amazon VPC Module
'''
import logging
import boto

log = logging.getLogger(__name__)

def __virtual__( ):
    return 'vpc'

# Iterate over boto.vpc to figure out what options are available.


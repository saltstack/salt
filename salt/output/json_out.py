'''
The JSON output module converts the return data into JSON.
'''
# Import python libs
import json
import traceback
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Rename to json
    '''
    return 'json'


def output(data):
    '''
    Print the output data in JSAON
    '''
    try:
        # A good kwarg might be: indent=4
        ret = json.dumps(data, indent=4)
    except TypeError:
        log.debug(traceback.format_exc())
        # Return valid json for unserializable objects
        ret = json.dumps({})
    return ret

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
    Print the output data in JSON
    '''
    try:
        if 'output_indent' in __opts__:
            if __opts__['output_indent'] >= 0:
                return json.dumps(data, indent=__opts__['output_indent'])
            return json.dumps(data)
        return json.dumps(data, indent=4)
    except TypeError:
        log.debug(traceback.format_exc())
    # Return valid json for unserializable objects
    return json.dumps({})

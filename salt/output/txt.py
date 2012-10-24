'''
The txt outputter
'''

# Import python libs
import pprint

def output(data):
    '''
    Output the data in lines, very nice for running commands
    '''
    if hasattr(data, 'keys'):
        for key in data:
            value = data[key]
            # Don't blow up on non-strings
            try:
                for line in value.split('\n'):
                    print('{0}: {1}'.format(key, line))
            except AttributeError:
                print('{0}: {1}'.format(key, value))
    else:
        # For non-dictionary data, just use print
        pprint.pprint(data)


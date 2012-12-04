'''
The python pretty print system is the default outputter. This outputter
simply passed the data passed into it through the pprint module.
'''

# Import python libs
import pprint

def __virtual__():
    '''
    Change the name to pprint
    '''
    return 'pprint'

def output(data):
    '''
    Print out via pretty print
    '''
    if isinstance(data, Exception):
        data = str(data)
    return pprint.pformat(data)

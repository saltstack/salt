'''
The default outputter, just fall back to python pretty print
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
    pprint.pprint(data)

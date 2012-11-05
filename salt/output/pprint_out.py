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
    return pprint.pformat(data)

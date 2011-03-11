'''
Module for shelling out commands, inclusion of this module should be
configurable for security reasons
'''

def echo(text):
    '''
    Return a string - used for testing the connection
    '''
    print 'Echo got called!'
    return text

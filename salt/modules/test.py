'''
Module for running arbitrairy tests
'''

def echo(text):
    '''
    Return a string - used for testing the connection
    '''
    print 'Echo got called!'
    return text

def ping():
    '''
    Just used to make sure the minion is up and responding
    Return True
    '''
    return True

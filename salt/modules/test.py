'''
Module for running arbitrairy tests
'''

def echo(text):
    '''
    Return a string - used for testing the connection

    CLI Example:
    salt '*' test.echo 'foo bar baz quo qux'
    '''
    print 'Echo got called!'
    return text

def ping():
    '''
    Just used to make sure the minion is up and responding
    Return True

    CLI Example:
    salt '*' test.ping
    '''
    return True

def facter():
    '''
    Return the facter data

    CLI Example:
    salt '*' test.facter_data
    '''
    return __facter__

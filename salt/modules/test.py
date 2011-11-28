'''
Module for running arbitrary tests
'''

import time


# Load in default options for the module
__opts__ = {
            'test.foo': 'foo'
            }
# Load the outputters for the module
__outputter__ = {
                 'outputter': 'txt'
                 }


def echo(text):
    '''
    Return a string - used for testing the connection

    CLI Example::

        salt '*' test.echo 'foo bar baz quo qux'
    '''
    print 'Echo got called!'
    return text


def ping():
    '''
    Just used to make sure the minion is up and responding
    Return True

    CLI Example::

        salt '*' test.ping
    '''
    return True

def version():
    '''
    Return the version of salt on the minion

    CLI Example::

        salt '*' test.version
    '''
    import salt
    return salt.__version__


def conf_test():
    '''
    Return the value for test.foo in the minion configuration file, or return
    the default value

    CLI Example::

        salt '*' test.conf_test
    '''
    return __opts__['test.foo']


def get_opts():
    '''
    Return the configuration options passed to this minion

    CLI Example::

        salt '*' test.get_opts
    '''
    return __opts__


# FIXME: mutable types as default parameter values
def cross_test(func, args=[]):
    '''
    Execute a minion function via the __salt__ object in the test module, used
    to verify that the minion functions can be called via the __salt__module

    CLI Example::

        salt '*' test.cross_test file.gid_to_group 0
    '''
    return __salt__[func](*args)


def fib(num):
    '''
    Return a Fibonacci sequence up to the passed number, and the time it took
    to compute in seconds. Used for performance tests

    CLI Example::

        salt '*' test.fib 3
    '''
    start = time.time()
    a, b = 0, 1
    ret = [0]
    while b < num:
        ret.append(b)
        a, b = b, a + b
    return ret, time.time() - start


def collatz(start):
    '''
    Execute the collatz conjecture from the passed starting number, returns
    the sequence and the time it took to compute. Used for performance tests.

    CLI Example::

        salt '*' test.collatz 3
    '''
    begin = time.time()
    steps = []
    while start != 1:
        steps.append(start)
        if start > 1:
            if start % 2 == 0:
                start = start / 2
            else:
                start = start * 3 + 1
    return steps, time.time() - begin


def outputter(data):
    '''
    Test the outputter, pass in data to return

    CLI Example::

        salt '*' test.outputter foobar
    '''
    return data

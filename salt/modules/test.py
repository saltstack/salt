'''
Module for running arbitrary tests
'''

# Import salt libs
import time


# Load the outputters for the module
__outputter__ = {
    'echo': 'txt',
    'ping': 'txt',
    'fib': 'yaml',
    'version': 'txt',
    'collatz': 'yaml',
    'conf_test': 'txt',
    'get_opts': 'yaml',
    'outputter': 'txt',
}


def echo(text):
    '''
    Return a string - used for testing the connection

    CLI Example::

        salt '*' test.echo 'foo bar baz quo qux'
    '''
    return text


def ping():
    '''
    Just used to make sure the minion is up and responding
    Return True

    CLI Example::

        salt '*' test.ping
    '''
    return True


def sleep(length):
    '''
    Instruct the minion to initiate a process that will sleep for a given
    period of time.

    CLI Example::

        salt '*' test.sleep 20
    '''
    time.sleep(int(length))
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
    return __salt__['config.option']('test.foo')


def get_opts():
    '''
    Return the configuration options passed to this minion

    CLI Example::

        salt '*' test.get_opts
    '''
    return __opts__


def cross_test(func, args=None):
    '''
    Execute a minion function via the __salt__ object in the test
    module, used to verify that the minion functions can be called
    via the __salt__ module.

    CLI Example::

        salt '*' test.cross_test file.gid_to_group 0
    '''
    if args is None:
        args = []
    return __salt__[func](*args)


def kwarg(**kwargs):
    '''
    Print out the data passed into the function ``**kwargs``, this is used to
    both test the publication data and cli kwarg passing, but also to display
    the information available within the publication data.

    CLI Example::

        salt '*' test.kwarg
    '''
    return kwargs


def fib(num):
    '''
    Return a Fibonacci sequence up to the passed number, and the
    timeit took to compute in seconds. Used for performance tests

    CLI Example::

        salt '*' test.fib 3
    '''
    num = int(num)
    start = time.time()
    a, b = 0, 1
    ret = [0]
    while b < num:
        ret.append(b)
        a, b = b, a + b
    return ret, time.time() - start


def collatz(start):
    '''
    Execute the collatz conjecture from the passed starting number,
    returns the sequence and the time it took to compute. Used for
    performance tests.

    CLI Example::

        salt '*' test.collatz 3
    '''
    start = int(start)
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

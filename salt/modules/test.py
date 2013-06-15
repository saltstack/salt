'''
Module for running arbitrary tests
'''

# Import Python libs
import os
import sys
import time
import random

# Import Salt libs
import salt
import salt.version
import salt.loader


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


def rand_sleep(max=60):
    '''
    Sleep for a random number of seconds, used to test long-running commands
    and minions returning at differing intervals

    CLI Example::

        salt '*' test.rand_sleep 60
    '''
    time.sleep(random.randint(0, max))
    return True


def version():
    '''
    Return the version of salt on the minion

    CLI Example::

        salt '*' test.version
    '''
    return salt.__version__


def versions_information():
    '''
    Returns versions of components used by salt as a dict

    CLI Example::

        salt '*' test.versions_information
    '''
    return dict(salt.version.versions_information())


def versions_report():
    '''
    Returns versions of components used by salt

    CLI Example::

        salt '*' test.versions_report
    '''
    return '\n'.join(salt.version.versions_report())


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

        salt '*' test.kwarg num=1 txt="two" env='{a: 1, b: "hello"}'
    '''
    return kwargs

def arg(*args, **kwargs):
    '''
    Print out the data passed into the function ``*args`` and ```kwargs``, this
    is used to both test the publication data and cli argument passing, but
    also to display the information available within the publication data.
    Returns {"args": args, "kwargs": kwargs}.

    CLI Example::

        salt '*' test.arg 1 "two" 3.1 txt="hello" wow='{a: 1, b: "hello"}'
    '''
    return {"args": args, "kwargs": kwargs}

def arg_repr(*args, **kwargs):
    '''
    Print out the data passed into the function ``*args`` and ```kwargs``, this
    is used to both test the publication data and cli argument passing, but
    also to display the information available within the publication data.
    Returns {"args": repr(args), "kwargs": repr(kwargs)}.

    CLI Example::

        salt '*' test.arg_repr 1 "two" 3.1 txt="hello" wow='{a: 1, b: "hello"}'
    '''
    return {"args": repr(args), "kwargs": repr(kwargs)}

def fib(num):
    '''
    Return a Fibonacci sequence up to the passed number, and the
    timeit took to compute in seconds. Used for performance tests

    CLI Example::

        salt '*' test.fib 3
    '''
    num = int(num)
    start = time.time()
    fib_a, fib_b = 0, 1
    ret = [0]
    while fib_b < num:
        ret.append(fib_b)
        fib_a, fib_b = fib_b, fib_a + fib_b
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


def retcode(code=42):
    '''
    Test that the returncode system is functioning correctly

    CLI Example::

        salt '*' test.retcode 42
    '''
    __context__['retcode'] = code
    return True


def provider(module):
    '''
    Pass in a function name to discover what provider is being used

    CLI Example::

        salt '*' test.provider service
    '''
    func = ''
    for key in __salt__:
        if not key.startswith('{0}.'.format(module)):
            continue
        func = key
        break
    if not func:
        return ''
    pfn = sys.modules[__salt__[func].__module__].__file__
    pfn = os.path.basename(pfn)
    return pfn[:pfn.rindex('.')]


def providers():
    '''
    Return a dict of the provider names and the files that provided them

    CLI Example::

        salt '*' test.providers
    '''
    ret = {}
    for funcname in __salt__:
        modname = funcname.split('.')[0]
        if modname not in ret:
            ret[provider(modname)] = modname
    return ret


def not_loaded():
    '''
    List the modules that were not loaded by the salt loader system

    CLI Example::

        salt '*' test.not_loaded
    '''
    prov = providers()
    ret = set()
    loader = salt.loader._create_loader(__opts__, 'modules', 'module')
    for mod_dir in loader.module_dirs:
        if not os.path.isabs(mod_dir):
            continue
        if not os.path.isdir(mod_dir):
            continue
        for fn_ in os.listdir(mod_dir):
            if fn_.startswith('_'):
                continue
            name = fn_.split('.')[0]
            if name not in prov:
                ret.add(name)
    return sorted(ret)

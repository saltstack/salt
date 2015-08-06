# -*- coding: utf-8 -*-
'''
Module for running arbitrary tests
'''
from __future__ import absolute_import

# Import Python libs
import os
import sys
import time
import traceback
import hashlib
import random

# Import Salt libs
import salt
import salt.version
import salt.loader
import salt.ext.six as six
from salt.utils.decorators import depends

__proxyenabled__ = ['*']


@depends('non_existantmodulename')
def missing_func():
    return 'foo'


def attr_call():
    '''
    Call grains.items via the attribute

    CLI Example::

    .. code-block:: bash

        salt '*' test.attr_call
    '''
    return __salt__.grains.items()


def module_report():
    '''
    Return a dict containing all of the exeution modules with a report on
    the overall availability via different references

    CLI Example::

    .. code-block:: bash

        salt '*' test.module_report
    '''
    ret = {'functions': [],
           'function_attrs': [],
           'function_subs': [],
           'modules': [],
           'module_attrs': [],
           'missing_attrs': [],
           'missing_subs': []}
    for ref in __salt__:
        if '.' in ref:
            ret['functions'].append(ref)
        else:
            ret['modules'].append(ref)
            if hasattr(__salt__, ref):
                ret['module_attrs'].append(ref)
            for func in __salt__[ref]:
                full = '{0}.{1}'.format(ref, func)
                if hasattr(getattr(__salt__, ref), func):
                    ret['function_attrs'].append(full)
                if func in __salt__[ref]:
                    ret['function_subs'].append(full)
    for func in ret['functions']:
        if func not in ret['function_attrs']:
            ret['missing_attrs'].append(func)
        if func not in ret['function_subs']:
            ret['missing_subs'].append(func)
    return ret


def echo(text):
    '''
    Return a string - used for testing the connection

    CLI Example:

    .. code-block:: bash

        salt '*' test.echo 'foo bar baz quo qux'
    '''
    return text


def ping():
    '''
    Used to make sure the minion is up and responding. Not an ICMP ping.

    Returns ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' test.ping
    '''

    if 'proxymodule' in __opts__:
        ping_cmd = __opts__['proxymodule'].loaded_base_name + '.ping'
        return __opts__['proxymodule'][ping_cmd]()
    else:
        return True


def sleep(length):
    '''
    Instruct the minion to initiate a process that will sleep for a given
    period of time.

    CLI Example:

    .. code-block:: bash

        salt '*' test.sleep 20
    '''
    time.sleep(int(length))
    return True


def rand_sleep(max=60):
    '''
    Sleep for a random number of seconds, used to test long-running commands
    and minions returning at differing intervals

    CLI Example:

    .. code-block:: bash

        salt '*' test.rand_sleep 60
    '''
    time.sleep(random.randint(0, max))
    return True


def version():
    '''
    Return the version of salt on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' test.version
    '''
    return salt.version.__version__


def versions_information():
    '''
    Returns versions of components used by salt as a dict

    CLI Example:

    .. code-block:: bash

        salt '*' test.versions_information
    '''
    return dict(salt.version.versions_information())


def versions_report():
    '''
    Returns versions of components used by salt

    CLI Example:

    .. code-block:: bash

        salt '*' test.versions_report
    '''
    return '\n'.join(salt.version.versions_report())


def conf_test():
    '''
    Return the value for test.foo in the minion configuration file, or return
    the default value

    CLI Example:

    .. code-block:: bash

        salt '*' test.conf_test
    '''
    return __salt__['config.option']('test.foo')


def get_opts():
    '''
    Return the configuration options passed to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' test.get_opts
    '''
    return __opts__


def cross_test(func, args=None):
    '''
    Execute a minion function via the __salt__ object in the test
    module, used to verify that the minion functions can be called
    via the __salt__ module.

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' test.kwarg num=1 txt="two" env='{a: 1, b: "hello"}'
    '''
    return kwargs


def arg(*args, **kwargs):
    '''
    Print out the data passed into the function ``*args`` and ```kwargs``, this
    is used to both test the publication data and cli argument passing, but
    also to display the information available within the publication data.
    Returns {"args": args, "kwargs": kwargs}.

    CLI Example:

    .. code-block:: bash

        salt '*' test.arg 1 "two" 3.1 txt="hello" wow='{a: 1, b: "hello"}'
    '''
    return {"args": args, "kwargs": kwargs}


def arg_type(*args, **kwargs):
    '''
    Print out the types of the args and kwargs. This is used to test the types
    of the args and kwargs passed down to the minion

    CLI Example:

    .. code-block:: bash

           salt '*' test.arg_type 1 'int'
    '''
    ret = {'args': [], 'kwargs': {}}
    # all the args
    for argument in args:
        ret['args'].append(str(type(argument)))

    # all the kwargs
    for key, val in six.iteritems(kwargs):
        ret['kwargs'][key] = str(type(val))

    return ret


def arg_repr(*args, **kwargs):
    '''
    Print out the data passed into the function ``*args`` and ```kwargs``, this
    is used to both test the publication data and cli argument passing, but
    also to display the information available within the publication data.
    Returns {"args": repr(args), "kwargs": repr(kwargs)}.

    CLI Example:

    .. code-block:: bash

        salt '*' test.arg_repr 1 "two" 3.1 txt="hello" wow='{a: 1, b: "hello"}'
    '''
    return {"args": repr(args), "kwargs": repr(kwargs)}


def fib(num):
    '''
    Return a Fibonacci sequence up to the passed number, and the
    timeit took to compute in seconds. Used for performance tests

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' test.outputter foobar
    '''
    return data


def retcode(code=42):
    '''
    Test that the returncode system is functioning correctly

    CLI Example:

    .. code-block:: bash

        salt '*' test.retcode 42
    '''
    __context__['retcode'] = code
    return True


def provider(module):
    '''
    Pass in a function name to discover what provider is being used

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' test.not_loaded
    '''
    prov = providers()
    ret = set()
    for mod_dir in salt.loader._module_dirs(__opts__, 'modules', 'module'):
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


def opts_pkg():
    '''
    Return an opts package with the grains and opts for this minion.
    This is primarily used to create the options used for master side
    state compiling routines

    CLI Example:

    .. code-block:: bash

        salt '*' test.opts_pkg
    '''
    ret = {}
    ret.update(__opts__)
    ret['grains'] = __grains__
    return ret


def rand_str(size=9999999999):
    '''
    Return a random string

    CLI Example:

    .. code-block:: bash

        salt '*' test.rand_str
    '''
    hasher = getattr(hashlib, __opts__.get('hash_type', 'md5'))
    return hasher(str(random.SystemRandom().randint(0, size))).hexdigest()


def exception(message='Test Exception'):
    '''
    Raise an exception

    Optionally provide an error message or output the full stack.

    CLI Example:

    .. code-block:: bash

        salt '*' test.exception 'Oh noes!'
    '''
    raise Exception(message)


def stack():
    '''
    Return the current stack trace

    CLI Example:

    .. code-block:: bash

        salt '*' test.stack
    '''
    return ''.join(traceback.format_stack())


def tty(*args, **kwargs):  # pylint: disable=W0613
    '''
    Deprecated! Moved to cmdmod.

    CLI Example:

    .. code-block:: bash

        salt '*' test.tty tty0 'This is a test'
        salt '*' test.tty pts3 'This is a test'
    '''
    return 'ERROR: This function has been moved to cmd.tty'


def try_(module, return_try_exception=False, **kwargs):
    '''
    Try to run a module command. On an exception return None.
    If `return_try_exception` is set True return the exception.
    This can be helpfull in templates where running a module might fail as expected.

    CLI Example:

    .. code-block:: bash

        <pre>
        {% for i in range(0,230) %}
            {{ salt['test.try'](module='ipmi.get_users', bmc_host='172.2.2.'+i)|yaml(False) }}
        {% endfor %}
        </pre>
    '''
    try:
        return __salt__[module](**kwargs)
    except Exception as e:
        if return_try_exception:
            return e
    return None


def assertion(assertion):
    '''
    Assert the given argument

    CLI Example:

    .. code-block:: bash

        salt '*' test.assert False
    '''
    assert assertion

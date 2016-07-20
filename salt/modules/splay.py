# -*- coding: UTF-8 -*-
'''
Splay function calls across targeted minions
'''

# Import Python Libs
from __future__ import absolute_import
import time

# Import 3rd-party libs
import salt.ext.six as six

# Import Salt Libs
from salt.exceptions import CommandExecutionError

_DEFAULT_SPLAYTIME = 600
_DEFAULT_SIZE = 8192


def _get_hash(hashable, size):
    '''
    Jenkins One-At-A-Time Hash Function
    More Info: http://en.wikipedia.org/wiki/Jenkins_hash_function#one-at-a-time
    '''
    # Using bitmask to emulate rollover behavior of C unsigned 32 bit int
    bitmask = 0xffffffff
    h = 0

    for i in bytearray(hashable):
        h = (h + i) & bitmask
        h = (h + (h << 10)) & bitmask
        h = (h ^ (h >> 6)) & bitmask

    h = (h + (h << 3)) & bitmask
    h = (h ^ (h >> 11)) & bitmask
    h = (h + (h << 15)) & bitmask

    return (h & (size - 1)) & bitmask


def _calc_splay(hashable, splaytime=_DEFAULT_SPLAYTIME, size=_DEFAULT_SIZE):
    hash_val = _get_hash(hashable, size)
    return int(splaytime * hash_val / float(size))


def splay(*args, **kwargs):
    '''
    Splay a salt function call execution time across minions over
    a number of seconds (default: 600)

    .. note::
        You *probably* want to use --async here and look up the job results later.
        If you're dead set on getting the output from the CLI command, then make
        sure to set the timeout (with the -t flag) to something greater than the
        splaytime (max splaytime + time to execute job).
        Otherwise, it's very likely that the cli will time out before the job returns.


    CLI Examples:

    .. code-block:: bash

        salt --async '*' splay.splay pkg.install cowsay version=3.03-8.el6

    .. code-block:: bash

      # With specified splaytime (5 minutes) and timeout with 10 second buffer
      salt -t 310 '*' splay.splay 300 pkg.version cowsay
    '''
    # Convert args tuple to a list so we can pop the splaytime and func out
    args = list(args)

    # If the first argument passed is an integer, set it as the splaytime
    try:
        splaytime = int(args[0])
        args.pop(0)
    except ValueError:
        splaytime = _DEFAULT_SPLAYTIME

    if splaytime <= 0:
        raise ValueError('splaytime must be a positive integer')

    func = args.pop(0)
    # Check if the func is valid before the sleep
    if func not in __salt__:
        raise CommandExecutionError('Unable to find module function {0}'.format(func))

    my_delay = _calc_splay(__grains__['id'], splaytime=splaytime)
    time.sleep(my_delay)
    # Get rid of the hidden kwargs that salt injects
    func_kwargs = dict((k, v) for k, v in six.iteritems(kwargs) if not k.startswith('__'))
    result = __salt__[func](*args, **func_kwargs)
    if not isinstance(result, dict):
        result = {'result': result}
    result['splaytime'] = str(my_delay)
    return result


def show(splaytime=_DEFAULT_SPLAYTIME):
    '''
    Show calculated splaytime for this minion
    Will use default value of 600 (seconds) if splaytime value not provided


    CLI Example:
        salt example-host splay.show
        salt example-host splay.show 60
    '''
    # Coerce splaytime to int (passed arg from CLI will be a str)
    if not isinstance(splaytime, int):
        splaytime = int(splaytime)

    return str(_calc_splay(__grains__['id'], splaytime=splaytime))

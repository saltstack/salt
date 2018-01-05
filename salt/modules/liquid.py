# -*- coding: utf-8 -*-
'''
Liquid
======

This module provides functions for the Liquid Salt system.
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils.args
import salt.utils.liquid


def fetch(opts=None, **kwargs):
    '''
    Return the liquid configuration fetched from the sources configured on the Minion.

    Configuration example:

    .. code-block:: yaml

        liquid:
          - yaml:
              path: https://example.com/yaml-api
          - mongo:
              host: example.com
              port: 49017
              db: common_opts
          - mongo:
              host: example.com
              port: 49017
              db: only_master_opts

    CLI Example:

    .. code-block:: bash

        salt '*' liquid.fetch
    '''
    if not opts:
        opts = __opts__
    clean_kwargs = salt.utils.args.clean_kwargs(**kwargs)
    return salt.utils.liquid.fetch(opts,
                                   # functions=__salt__,
                                   utils=__utils__,
                                   **clean_kwargs)
    # TODO: revist later the commented line above (`functions=__salt__`)
    # Having the execution functions dict injected into the liquid modules
    # might turn useful, but it can also be a pain: if the module is run on
    # the Master, __salt__ will provide the runner instead.
    # This wouldn't be a problem in here, but if the developer makes use of
    # the salt dunder in the liquid module, it will very likely fail when
    # collecting the Master opts from the remote system.
    # We can however detect when running on the Master side, and invoke
    # the execution function instead, though that might fail.
    # There's also the discussion: do we really want to inject the execution
    # functions into a system that collects the configuration opts? Maybe,
    # for the sake of reusing existing code, but that can open a can of worms.


def get_cache():
    '''
    Return the cached liquid opts.

    CLI Example:

    .. code-block:: bash

        salt '*' liquid.get_cache
    '''
    return salt.utils.liquid.get_cache(__opts__)


def get_cache_filename():
    '''
    Return the name of the liquid opts cache file.


    CLI Example:

    .. code-block:: bash

        salt '*' liquid.get_cache_filename
    '''
    return salt.utils.liquid.get_cache_filename(__opts__)


def cache(opts=None, **kwargs):
    '''
    Fetch the liquid opts and cache them.
    This function does not check if the cached file already exist,
    it will simply fetch the liquid opts and save them to the cache file,
    without any further checks.

    CLI Example:

    .. code-block:: bash

        salt '*' liquid.cache
    '''
    if not opts:
        opts = __opts__
    clean_kwargs = salt.utils.args.clean_kwargs(**kwargs)
    return salt.utils.liquid.cache(opts,
                                   # functions=__salt__,
                                   utils=__utils__,
                                   **clean_kwargs)

# -*- coding: utf-8 -*-
'''
Utilities for the Liquid subsystem
'''
from __future__ import absolute_import
import logging

# Import salt libs
import salt.loader

log = logging.getLogger(__name__)


def fetch(opts, utils=None, **kwargs):
    '''
    Fetch the configuration options using the liquid module.

    Opts syntax:

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
    '''
    if 'liquid' not in opts:
        return {}
    if not isinstance(opts['liquid'], list):
        log.error('Liquid opts must be a list')
        return {}
    if utils is None:
        utils = {}
    opts = {}
    for liquid_driver in opts['liquid']:
        if not isinstance(liquid_driver, dict):
            log.warning('Liquid opts must be a list of dicts')
            return {}
        driver_name = list(liquid_driver.keys())[0]
        driver_kwargs = liquid_driver[driver_name]
        fun = '{0}.fetch'.format(driver_name)
        loaded_lq = salt.loader.liquid(opts, fun, utils=utils)
        driver_opts = loaded_lq[fun](**driver_kwargs)
        opts.update(driver_opts)
    return opts

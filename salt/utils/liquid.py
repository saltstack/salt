# -*- coding: utf-8 -*-
'''
Utilities for the Liquid subsystem
'''
from __future__ import absolute_import

import os
import yaml
import logging

# Import salt libs
import salt.loader
import salt.utils.files
import salt.utils.yamldumper
import salt.utils.yamlloader as yamlloader


log = logging.getLogger(__name__)


def fetch(opts, functions=None, utils=None, **kwargs):
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
    liquid_opts = {}
    for liquid_driver in opts['liquid']:
        if not isinstance(liquid_driver, dict):
            log.warning('Liquid opts must be a list of dicts')
            return {}
        driver_name = list(liquid_driver.keys())[0]
        driver_kwargs = liquid_driver[driver_name]
        fun = '{0}.fetch'.format(driver_name)
        loaded_lq = salt.loader.liquid(opts, functions=functions, utils=utils)
        try:
            driver_opts = loaded_lq[fun](**driver_kwargs)
        except KeyError:
            log.error('Unable to fetch opts from %s (the module does not exist)', driver_name)
            return {}
        liquid_opts.update(driver_opts)
    return liquid_opts


def get_cache(opts):
    '''
    Return the cached liquid opts.
    '''
    liquid_filename = get_cache_filename(opts)
    log.debug('Reading the cached liquid opts from %s', liquid_filename)
    if os.path.isfile(liquid_filename):
        # If the liquid file already exists,
        # try loadign the config from there
        liquid_opts = None
        with salt.utils.files.fopen(liquid_filename, 'r') as liquid_fh:
            try:
                liquid_opts = yamlloader.load(
                    liquid_fh.read(),
                    Loader=yamlloader.SaltYamlSafeLoader,
                ) or {}
            except yaml.YAMLError as err:
                message = 'Error reading the liquid config file: {0} - {1}'.format(liquid_filename, err)
                log.error(message)
        if liquid_opts is not None:
            return liquid_opts
    log.debug('The liquid cache file %s does not exist', liquid_filename)
    return {}


def get_cache_filename(opts):
    '''
    Return the filename (absolute path) of the liquid cache file.
    '''
    role = opts['__role']
    if os.path.isdir(opts['conf_file']):
        liquid_filename = os.path.join(
            opts['conf_file'],
            '{}.d'.format(role),
            '_liquid.conf')
    else:
        liquid_filename = os.path.join(
            os.path.dirname(opts['conf_file']),
            '{}.d'.format(role),
            '_liquid.conf'
        )
    opts['liquid_cache_file'] = liquid_filename
    return liquid_filename


def save_opts(opts, liquid_opts):
    '''
    Save the liquid opts to the cache file.
    '''
    liquid_filename = get_cache_filename(opts)
    if liquid_opts:
        with salt.utils.files.fopen(liquid_filename, 'w+') as liquid_fh:
            salt.utils.yamldumper.safe_dump(liquid_opts,
                                            stream=liquid_fh)
        return True
    return False


def cache(opts, functions=None, utils=None, **kwargs):
    '''
    Fetch the liquid opts and cache them.
    This function does not check if the cached file already exist,
    it will simply fetch the liquid opts and save them to the cache file,
    without any further checks.
    '''
    liquid_opts = fetch(opts, functions=functions, utils=utils, **kwargs)
    saved = save_opts(opts, liquid_opts)
    return liquid_opts


def refresh_opts(opts, liquid_opts):
    '''
    '''
    return False

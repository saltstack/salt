# -*- coding: utf-8 -*-
'''
Take data from salt and "return" it into a raw file containing the json, with
one line per event.

Add the following to the minion or master configuration file.

.. code-block:: yaml

    rawfile_json.filename: <path_to_output_file>

Default is ``/var/log/salt/events``.

Common use is to log all events on the master. This can generate a lot of
noise, so you may wish to configure batch processing and/or configure the
:conf_master:`event_return_whitelist` or :conf_master:`event_return_blacklist`
to restrict the events that are written.
'''

# Import python libs
from __future__ import absolute_import, print_function, with_statement
import logging
import json

import salt.returners
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'rawfile_json'


def __virtual__():
    return __virtualname__


def _get_options(ret):
    '''
    Returns options used for the rawfile_json returner.
    '''
    defaults = {'filename': '/var/log/salt/events'}
    attrs = {'filename': 'filename'}
    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)

    return _options


def returner(ret):
    '''
    Write the return data to a file on the minion.
    '''
    opts = _get_options({})  # Pass in empty ret, since this is a list of events
    try:
        with salt.utils.flopen(opts['filename'], 'a') as logfile:
            logfile.write(json.dumps(ret)+'\n')
    except:
        log.error('Could not write to rawdata_json file {0}'.format(opts['filename']))
        raise


def event_return(event):
    '''
    Write event return data to a file on the master.
    '''
    opts = _get_options({})  # Pass in empty ret, since this is a list of events
    try:
        with salt.utils.flopen(opts['filename'], 'a') as logfile:
            for e in event:
                logfile.write(str(json.dumps(e))+'\n')
    except:
        log.error('Could not write to rawdata_json file {0}'.format(opts['filename']))
        raise

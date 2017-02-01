# -*- coding: utf-8 -*-
'''
On-demand logging
=================

.. versionadded:: Nitrogen

The sole purpose of this module is logging messages in the (proxy) minion.
It comes very handy when debugging complex Jinja templates, for example:

.. code-block:: jinja

    {%- for var in range(10) %}
      {%- do salt.log.info(var) -%}
    {%- endfor %}

CLI Example:

.. code-block:: bash

    salt '*' log.error 'Please dont do that, this module is not for CLI use!'

However, please note that it will not log the message when executed from the CLI.
'''
from __future__ import absolute_import

# Import python libs
import logging
log = logging.getLogger(__name__)

__virtualname__ = 'log'
__proxyenabled__ = ['*']


def __virtual__():
    return __virtualname__


def debug(message, **kwargs):
    '''Log message at level DEBUG.'''
    if not kwargs:
        # log only when not executed from the CLI
        log.debug(message)
        return True
    return False


def info(message, **kwargs):
    '''Log message at level INFO.'''
    if not kwargs:
        # log only when not executed from the CLI
        log.info(message)
        return True
    return False


def warning(message, **kwargs):
    '''Log message at level WARNING.'''
    if not kwargs:
        # log only when not executed from the CLI
        log.warning(message)
        return True
    return False


def error(message, **kwargs):
    '''Log message at level ERROR.'''
    if not kwargs:
        # log only when not executed from the CLI
        log.error(message)
        return True
    return False


def critical(message, **kwargs):
    '''Log message at level CRITICAL.'''
    if not kwargs:
        # log only when not executed from the CLI
        log.critical(message)
        return True
    return False


def exception(message, **kwargs):
    '''Log message at level EXCEPTION.'''
    if not kwargs:
        # log only when not executed from the CLI
        log.exception(message)
        return True
    return False

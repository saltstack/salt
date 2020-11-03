# -*- coding: utf-8 -*-
"""
On-demand logging
=================

.. versionadded:: 2017.7.0

The sole purpose of this module is logging messages in the (proxy) minion.
It comes very handy when debugging complex Jinja templates, for example:

.. code-block:: jinja

    {%- for var in range(10) %}
      {%- do salt.log.info(var) -%}
    {%- endfor %}

CLI Example:

.. code-block:: bash

    salt '*' log.error "Please don't do that, this module is not for CLI use!"
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

log = logging.getLogger(__name__)

__virtualname__ = "log"
__proxyenabled__ = ["*"]


def __virtual__():
    return __virtualname__


def debug(message):
    """
    Log message at level DEBUG.
    """
    log.debug(message)
    return True


def info(message):
    """
    Log message at level INFO.
    """
    log.info(message)
    return True


def warning(message):
    """
    Log message at level WARNING.
    """
    log.warning(message)
    return True


def error(message):
    """
    Log message at level ERROR.
    """
    log.error(message)
    return True


def critical(message):
    """
    Log message at level CRITICAL.
    """
    log.critical(message)
    return True


def exception(message):
    """
    Log message at level EXCEPTION.
    """
    log.exception(message)
    return True

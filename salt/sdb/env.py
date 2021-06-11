# -*- coding: utf-8 -*-
"""
Environment sdb Module

:maintainer:    SaltStack
:maturity:      New
:depends:       None
:platform:      all

This module allows access to environment variables using an ``sdb://`` URI.

Example configuration for this module:

.. code-block:: yaml

    osenv:
      driver: env

WARNING:
--------
OS environment variables will be available
to read via SDB.
Please make sure you don't have any sensitive data
in your environment variables!!

Example usage of sdb env module:

.. code-block:: jinja

    set some env var:
      cmd.run:
        - name: echo {{ salt['sdb.set']('sdb://osenv/foo', 'bar') }}
        - order: 1

    {% if salt['sdb.get']('sdb://osenv/foo') == 'bar' %}
    always-changes-and-succeeds:
      test.succeed_with_changes:
        - name: foo
    {% else %}
    always-changes-and-fails:
      test.fail_with_changes:
        - name: foo
    {% endif  %}

The above example will return success.

The ``env`` sdb module can also be used with salt cloud.
Assuming you have exported the environment variable named
``compute`` (and have ``osenv`` defined).
The example below will look for the salt cloud config key ``compute_name``
in the environment:

.. code-block:: yaml

  my-openstack-config:
    compute_name: sdb://osenv/compute
    ..snip

"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import os

__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Always load
    """
    return True


def set_(key, value, profile=None):
    """
    Set a key/value pair
    """
    # pylint: disable=unused-argument
    return os.environ.setdefault(key, value)


def get(key, profile=None):
    """
    Get a value
    """
    # pylint: disable=unused-argument
    return os.environ.get(key)

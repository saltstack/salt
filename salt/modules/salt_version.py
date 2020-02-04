# -*- coding: utf-8 -*-
'''
Access Salt's elemental release code-names.

.. versionadded:: Neon

Salt's feature release schedule is based on the Periodic Table, as described
in the :ref:`Version Numbers <version-numbers>` documentation.

When a feature was added (or removed) in a specific release, it can be
difficult to build out future-proof functionality that is dependent on
a naming scheme that moves.

For example, a state syntax needs to change to support an option that will be
removed in the future, but there are many Minion versions in use across an
infrastructure. It would be handy to use some Jinja syntax to check for these
instances to perform one state syntax over another.

A simple example might be something like the following:

.. code-block:: jinja

    {# a boolean check #}
    {% set option_deprecated = salt['salt_version.less_than']("Sodium") %}

    {% if option_deprecated %}
      <use old syntax>
    {% else %}
      <use new syntax>
    {% endif %}

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
from salt.ext import six
import salt.version
import salt.utils.versions


log = logging.getLogger(__name__)

__virtualname__ = 'salt_version'


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return __virtualname__


def get_release_number(name):
    '''
    Returns the release number of a given release code name in a
    ``MAJOR.PATCH`` format.

    If the release name has not been given an assigned release number, the
    function returns a string. If the release cannot be found, it returns
    ``None``.

    name
        The release code name for which to find a release number.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.get_release_number 'Oxygen'
    '''
    name = name.lower()
    version_map = salt.version.SaltStackVersion.LNAMES
    version = version_map.get(name)
    if version is None:
        log.info('Version {} not found.'.format(name))
        return None

    if version[1] == 0:
        log.info('Version {} found, but no release number has been assigned '
                 'yet.'.format(name))
        return 'No version assigned.'

    return '.'.join(str(item) for item in version)


def equal(name):
    '''
    Returns a boolean (True) if the minion's current version
    code name matches the named version.

    name
        The release code name to check the version against.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.equal 'Oxygen'
    '''
    if _check_release_cmp(name) == 0:
        log.info(
            'The minion\'s version code name matches \'{}\'.'.format(name)
        )
        return True

    return False


def greater_than(name):
    '''
    Returns a boolean (True) if the minion's current
    version code name is greater than the named version.

    name
        The release code name to check the version against.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.greater_than 'Sodium'
    '''
    if _check_release_cmp(name) == 1:
        log.info(
            'The minion\'s version code name is greater than \'{}\'.'.format(name)
        )
        return True

    return False


def less_than(name):
    '''
    Returns a boolean (True) if the minion's current
    version code name is less than the named version.

    name
        The release code name to check the version against.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.less_than 'Sodium'
    '''
    if _check_release_cmp(name) == -1:
        log.info(
            'The minion\'s version code name is less than \'{}\'.'.format(name)
        )
        return True

    return False


def _check_release_cmp(name):
    '''
    Helper function to compare the minion's current
    Salt version to release code name versions.

    If release code name isn't found, the function returns None. Otherwise, it
    returns the results of the version comparison as documented by the
    ``versions_cmp`` function in ``salt.utils.versions.py``.
    '''
    map_version = get_release_number(name)
    if map_version is None:
        log.info('Release code name {} was not found.'.format(name))
        return None

    current_version = six.text_type(salt.version.SaltStackVersion(
        *salt.version.__version_info__))
    current_version = current_version.rsplit('.', 1)[0]
    version_cmp = salt.utils.versions.version_cmp(current_version, map_version)
    return version_cmp

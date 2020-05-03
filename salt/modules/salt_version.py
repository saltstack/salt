# -*- coding: utf-8 -*-
'''
Access Salt's elemental release code-names.

.. versionadded:: Neon

Salt's feature release schedule is based on the Periodic Table, as described
in the :ref:`Version Numbers <version-numbers>` documentation.

Since deprecation notices often use the elemental release code-name when warning
users about deprecated changes, it can be difficult to build out future-proof
functionality that are dependent on a naming scheme that moves.

For example, a state syntax needs to change to support an option that will be
removed in the future, but there are many Minion versions in use across an
infrastructure. It would be handy to use some Jinja syntax to check for these
instances to perform one state syntax over another.

A simple example might be something like the following:

.. code-block:: jinja

    {# a boolean check #}
    {% set option_deprecated = salt['salt_version.is_older']("Sodium") %}

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
    ``<year>.<month>`` context.

    If the release name has not been given an assigned release number, the
    function returns a string. If the release cannot be found, it returns
    ``None``.

    name
        The release codename for which to find a release number.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.get_release_number 'Oxygen'
    '''
    name = name.lower()
    version_map = salt.version.SaltStackVersion.LNAMES
    version = version_map.get(name)
    if version is None:
        log.info('Version %s not found.', name)
        return None

    if version[1] == 0:
        log.info('Version %s found, but no release number has been assigned yet.', name)
        return 'No version assigned.'

    return '.'.join(str(item) for item in version)


def is_equal(name):
    '''
    Returns a boolean if the named version matches the minion's current Salt
    version.

    name
        The release codename to check the version against.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.is_equal 'Oxygen'
    '''
    if _check_release_cmp(name) == 0:
        log.info('Release codename \'%s\' equals the minion\'s version.', name)
        return True

    return False


def is_newer(name):
    '''
    Returns a boolean if the named version is newer that the minion's current
    Salt version.

    name
        The release codename to check the version against.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.is_newer 'Sodium'
    '''
    if _check_release_cmp(name) == 1:
        log.info('Release codename \'%s\' is newer than the minion\'s version.', name)
        return True

    return False


def is_older(name):
    '''
    Returns a boolean if the named version is older that the minion's current
    Salt version.

    name
        The release codename to check the version against.

    CLI Example:

    .. code-block:: bash

        salt '*' salt_version.is_newer 'Sodium'
    '''
    if _check_release_cmp(name) == -1:
        log.info('Release codename \'%s\' is older than the minion\'s version.', name)
        return True

    return False


def _check_release_cmp(name):
    '''
    Helper function to compare release codename versions to the minion's current
    Salt version.

    If release codename isn't found, the function returns None. Otherwise, it
    returns the results of the version comparison as documented by the
    ``versions_cmp`` function in ``salt.utils.versions.py``.
    '''
    map_version = get_release_number(name)
    if map_version is None:
        log.info('Release codename %s was not found.', name)
        return None

    current_version = six.text_type(salt.version.SaltStackVersion(
        *salt.version.__version_info__))
    current_version = current_version.rsplit('.', 1)[0]
    version_cmp = salt.utils.versions.version_cmp(map_version, current_version)

    return version_cmp

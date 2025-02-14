"""
Extract the pillar data for this minion
"""

import salt.pillar
import salt.utils.data
import salt.utils.dictupdate
from salt.defaults import DEFAULT_TARGET_DELIM

try:
    # Python 3
    from collections.abc import Mapping
except ImportError:
    # We still allow Py2 import because this could be executed in a machine with Py2.
    from collections import (  # pylint: disable=no-name-in-module,deprecated-class
        Mapping,
    )


def get(key, default="", merge=False, delimiter=DEFAULT_TARGET_DELIM):
    """
    .. versionadded:: 0.14.0

    Attempt to retrieve the named value from pillar, if the named value is not
    available return the passed default. The default return is an empty string.

    If the merge parameter is set to ``True``, the default will be recursively
    merged into the returned pillar data.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in pillar looks like this::

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed::

        pkg:apache

    merge
        Specify whether or not the retrieved values should be recursively
        merged into the passed default.

        .. versionadded:: 2015.5.0

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.get pkg:apache
    """
    if merge:
        ret = salt.utils.data.traverse_dict_and_list(
            __pillar__.value(), key, {}, delimiter
        )
        if isinstance(ret, Mapping) and isinstance(default, Mapping):
            return salt.utils.dictupdate.update(default, ret)

    return salt.utils.data.traverse_dict_and_list(
        __pillar__.value(), key, default, delimiter
    )


def item(*args):
    """
    .. versionadded:: 0.16.2

    Return one or more pillar entries

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.item foo
        salt '*' pillar.item foo bar baz
    """
    ret = {}
    for arg in args:
        try:
            ret[arg] = __pillar__[arg]
        except KeyError:
            pass
    return ret


def raw(key=None):
    """
    Return the raw pillar data that is available in the module. This will
    show the pillar as it is loaded as the __pillar__ dict.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.raw

    With the optional key argument, you can select a subtree of the
    pillar raw data.::

        salt '*' pillar.raw key='roles'
    """
    if key:
        ret = __pillar__.get(key, {})
    else:
        ret = __pillar__.value()

    return ret


def keys(key, delimiter=DEFAULT_TARGET_DELIM):
    """
    .. versionadded:: 2015.8.0

    Attempt to retrieve a list of keys from the named value from the pillar.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict, similar to how pillar.get works.

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.keys web:sites
    """
    ret = salt.utils.data.traverse_dict_and_list(
        __pillar__.value(), key, KeyError, delimiter
    )

    if ret is KeyError:
        raise KeyError("Pillar key not found: {}".format(key))

    if not isinstance(ret, dict):
        raise ValueError("Pillar value in key {} is not a dict".format(key))

    return ret.keys()


def filter_by(lookup_dict, pillar, merge=None, default="default", base=None):
    """
    .. versionadded:: 2017.7.0

    Look up the given pillar in a given dictionary and return the result

    :param lookup_dict: A dictionary, keyed by a pillar, containing a value or
        values relevant to systems matching that pillar. For example, a key
        could be a pillar for a role and the value could the name of a package
        on that particular OS.

        The dictionary key can be a globbing pattern. The function will return
        the corresponding ``lookup_dict`` value where the pillar value matches
        the  pattern. For example:

        .. code-block:: bash

            # this will render 'got some salt' if ``role`` begins with 'salt'
            salt '*' pillar.filter_by '{salt*: got some salt, default: salt is not here}' role

    :param pillar: The name of a pillar to match with the system's pillar. For
        example, the value of the "role" pillar could be used to pull values
        from the ``lookup_dict`` dictionary.

        The pillar value can be a list. The function will return the
        ``lookup_dict`` value for a first found item in the list matching
        one of the ``lookup_dict`` keys.

    :param merge: A dictionary to merge with the results of the pillar
        selection from ``lookup_dict``. This allows another dictionary to
        override the values in the ``lookup_dict``.

    :param default: default lookup_dict's key used if the pillar does not exist
        or if the pillar value has no match on lookup_dict.  If unspecified
        the value is "default".

    :param base: A lookup_dict key to use for a base dictionary.  The
        pillar-selected ``lookup_dict`` is merged over this and then finally
        the ``merge`` dictionary is merged.  This allows common values for
        each case to be collected in the base and overridden by the pillar
        selection dictionary and the merge dictionary.  Default is unset.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.filter_by '{web: Serve it up, db: I query, default: x_x}' role
    """
    return salt.utils.data.filter_by(
        lookup_dict=lookup_dict,
        lookup=pillar,
        traverse=__pillar__.value(),
        merge=merge,
        default=default,
        base=base,
    )


# Allow pillar.data to also be used to return pillar data
items = raw
data = items

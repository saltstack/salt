"""
Return/control aspects of the grains data
"""


import copy
import math
from collections.abc import Mapping

import salt.utils.data
import salt.utils.dictupdate
import salt.utils.json
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import SaltException

# Seed the grains dict so cython will build
__grains__ = {}


def _serial_sanitizer(instr):
    """
    Replaces the last 1/4 of a string with X's
    """
    length = len(instr)
    index = int(math.floor(length * 0.75))
    return "{}{}".format(instr[:index], "X" * (length - index))


_FQDN_SANITIZER = lambda x: "MINION.DOMAINNAME"
_HOSTNAME_SANITIZER = lambda x: "MINION"
_DOMAINNAME_SANITIZER = lambda x: "DOMAINNAME"


# A dictionary of grain -> function mappings for sanitizing grain output. This
# is used when the 'sanitize' flag is given.
_SANITIZERS = {
    "serialnumber": _serial_sanitizer,
    "domain": _DOMAINNAME_SANITIZER,
    "fqdn": _FQDN_SANITIZER,
    "id": _FQDN_SANITIZER,
    "host": _HOSTNAME_SANITIZER,
    "localhost": _HOSTNAME_SANITIZER,
    "nodename": _HOSTNAME_SANITIZER,
}


def get(key, default="", delimiter=DEFAULT_TARGET_DELIM, ordered=True):
    """
    Attempt to retrieve the named value from grains, if the named value is not
    available return the passed default. The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in grains looks like this::

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed::

        pkg:apache

    CLI Example:

    .. code-block:: bash

        salt '*' grains.get pkg:apache
    """
    if ordered is True:
        grains = __grains__.value()
    else:
        grains = salt.utils.json.loads(salt.utils.json.dumps(__grains__.value()))
    return salt.utils.data.traverse_dict_and_list(
        __grains__.value(), key, default, delimiter
    )


def has_value(key):
    """
    Determine whether a named value exists in the grains dictionary.

    Given a grains dictionary that contains the following structure::

        {'pkg': {'apache': 'httpd'}}

    One would determine if the apache key in the pkg dict exists by::

        pkg:apache

    CLI Example:

    .. code-block:: bash

        salt '*' grains.has_value pkg:apache
    """
    return (
        True
        if salt.utils.data.traverse_dict_and_list(__grains__, key, False)
        else False
    )


def items(sanitize=False):
    """
    Return all of the minion's grains

    CLI Example:

    .. code-block:: bash

        salt '*' grains.items

    Sanitized CLI Example:

    .. code-block:: bash

        salt '*' grains.items sanitize=True
    """
    if salt.utils.data.is_true(sanitize):
        out = dict(__grains__.value())
        for key, func in _SANITIZERS.items():
            if key in out:
                out[key] = func(out[key])
        return out
    else:
        return __grains__.value()


def item(*args, **kwargs):
    """
    Return one or more grains

    CLI Example:

    .. code-block:: bash

        salt '*' grains.item os
        salt '*' grains.item os osrelease oscodename

    Sanitized CLI Example:

    .. code-block:: bash

        salt '*' grains.item host sanitize=True
    """
    ret = {}
    for arg in args:
        try:
            ret[arg] = __grains__[arg]
        except KeyError:
            pass
    if salt.utils.data.is_true(kwargs.get("sanitize")):
        for arg, func in _SANITIZERS.items():
            if arg in ret:
                ret[arg] = func(ret[arg])
    return ret


def ls():  # pylint: disable=C0103
    """
    Return a list of all available grains

    CLI Example:

    .. code-block:: bash

        salt '*' grains.ls
    """
    return sorted(__grains__)


def filter_by(lookup_dict, grain="os_family", merge=None, default="default", base=None):
    """
    .. versionadded:: 0.17.0

    Look up the given grain in a given dictionary for the current OS and return
    the result

    Although this may occasionally be useful at the CLI, the primary intent of
    this function is for use in Jinja to make short work of creating lookup
    tables for OS-specific data. For example:

    .. code-block:: jinja

        {% set apache = salt['grains.filter_by']({
            'Debian': {'pkg': 'apache2', 'srv': 'apache2'},
            'RedHat': {'pkg': 'httpd', 'srv': 'httpd'},
        }), default='Debian' %}

        myapache:
          pkg.installed:
            - name: {{ apache.pkg }}
          service.running:
            - name: {{ apache.srv }}

    Values in the lookup table may be overridden by values in Pillar. An
    example Pillar to override values in the example above could be as follows:

    .. code-block:: yaml

        apache:
          lookup:
            pkg: apache_13
            srv: apache

    The call to ``filter_by()`` would be modified as follows to reference those
    Pillar values:

    .. code-block:: jinja

        {% set apache = salt['grains.filter_by']({
            ...
        }, merge=salt['pillar.get']('apache:lookup')) %}


    :param lookup_dict: A dictionary, keyed by a grain, containing a value or
        values relevant to systems matching that grain. For example, a key
        could be the grain for an OS and the value could the name of a package
        on that particular OS.
    :param grain: The name of a grain to match with the current system's
        grains. For example, the value of the "os_family" grain for the current
        system could be used to pull values from the ``lookup_dict``
        dictionary.
    :param merge: A dictionary to merge with the ``lookup_dict`` before doing
        the lookup. This allows Pillar to override the values in the
        ``lookup_dict``. This could be useful, for example, to override the
        values for non-standard package names such as when using a different
        Python version from the default Python version provided by the OS
        (e.g., ``python26-mysql`` instead of ``python-mysql``).
    :param default: default lookup_dict's key used if the grain does not exists
         or if the grain value has no match on lookup_dict.

         .. versionadded:: 2014.1.0

    :param base: A lookup_dict key to use for a base dictionary. The
        grain-selected ``lookup_dict`` is merged over this and then finally
        the ``merge`` dictionary is merged. This allows common values for
        each case to be collected in the base and overridden by the grain
        selection dictionary and the merge dictionary. Default is None.

        .. versionadded:: 2015.8.11,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' grains.filter_by '{Debian: Debheads rule, RedHat: I love my hat}'
        # this one will render {D: {E: I, G: H}, J: K}
        salt '*' grains.filter_by '{A: B, C: {D: {E: F,G: H}}}' 'xxx' '{D: {E: I},J: K}' 'C'
    """
    ret = lookup_dict.get(
        __grains__.get(grain, default), lookup_dict.get(default, None)
    )

    if base and base in lookup_dict:
        base_values = lookup_dict[base]
        if ret is None:
            ret = base_values

        elif isinstance(base_values, Mapping):
            if not isinstance(ret, Mapping):
                raise SaltException(
                    "filter_by default and look-up values must both be dictionaries."
                )
            ret = salt.utils.dictupdate.update(copy.deepcopy(base_values), ret)

    if merge:
        if not isinstance(merge, Mapping):
            raise SaltException("filter_by merge argument must be a dictionary.")
        else:
            if ret is None:
                ret = merge
            else:
                salt.utils.dictupdate.update(ret, merge)

    return ret

"""
Return/control aspects of the grains data

Grains set or altered with this module are stored in the 'grains'
file on the minions. By default, this file is located at: ``/etc/salt/grains``

.. Note::

   This does **NOT** override any grains set in the minion config file.
"""


import collections
import logging
import math
import operator
import os
import random
from collections.abc import Mapping
from functools import reduce  # pylint: disable=redefined-builtin

import salt.utils.compat
import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import SaltException

__proxyenabled__ = ["*"]

# Seed the grains dict so cython will build
__grains__ = {}

# Change the default outputter to make it more readable
__outputter__ = {
    "items": "nested",
    "item": "nested",
    "setval": "nested",
}

# http://stackoverflow.com/a/12414913/127816
_infinitedict = lambda: collections.defaultdict(_infinitedict)

_non_existent_key = "NonExistentValueMagicNumberSpK3hnufdHfeBUXCfqVK"

log = logging.getLogger(__name__)


def _serial_sanitizer(instr):
    """Replaces the last 1/4 of a string with X's"""
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


    :param delimiter:
        Specify an alternate delimiter to use when traversing a nested dict.
        This is useful for when the desired key contains a colon. See CLI
        example below for usage.

        .. versionadded:: 2014.7.0

    :param ordered:
        Outputs an ordered dict if applicable (default: True)

        .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' grains.get pkg:apache
        salt '*' grains.get abc::def|ghi delimiter='|'
    """
    if ordered is True:
        grains = __grains__
    else:
        grains = salt.utils.json.loads(salt.utils.json.dumps(__grains__))
    return salt.utils.data.traverse_dict_and_list(grains, key, default, delimiter)


def has_value(key):
    """
    Determine whether a key exists in the grains dictionary.

    Given a grains dictionary that contains the following structure::

        {'pkg': {'apache': 'httpd'}}

    One would determine if the apache key in the pkg dict exists by::

        pkg:apache

    CLI Example:

    .. code-block:: bash

        salt '*' grains.has_value pkg:apache
    """
    return (
        salt.utils.data.traverse_dict_and_list(__grains__, key, KeyError)
        is not KeyError
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
        out = dict(__grains__)
        for key, func in _SANITIZERS.items():
            if key in out:
                out[key] = func(out[key])
        return out
    else:
        return dict(__grains__)


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
    default = kwargs.get("default", "")
    delimiter = kwargs.get("delimiter", DEFAULT_TARGET_DELIM)

    try:
        for arg in args:
            ret[arg] = salt.utils.data.traverse_dict_and_list(
                __grains__, arg, default, delimiter
            )
    except KeyError:
        pass

    if salt.utils.data.is_true(kwargs.get("sanitize")):
        for arg, func in _SANITIZERS.items():
            if arg in ret:
                ret[arg] = func(ret[arg])
    return ret


def setvals(grains, destructive=False, refresh_pillar=True):
    """
    Set new grains values in the grains config file

    destructive
        If an operation results in a key being removed, delete the key, too.
        Defaults to False.

    refresh_pillar
        Whether pillar will be refreshed.
        Defaults to True.

    CLI Example:

    .. code-block:: bash

        salt '*' grains.setvals "{'key1': 'val1', 'key2': 'val2'}"
    """
    new_grains = grains
    if not isinstance(new_grains, Mapping):
        raise SaltException("setvals grains must be a dictionary.")
    grains = {}
    if os.path.isfile(__opts__["conf_file"]):
        if salt.utils.platform.is_proxy():
            gfn = os.path.join(
                os.path.dirname(__opts__["conf_file"]),
                "proxy.d",
                __opts__["id"],
                "grains",
            )
        else:
            gfn = os.path.join(os.path.dirname(__opts__["conf_file"]), "grains")
    elif os.path.isdir(__opts__["conf_file"]):
        if salt.utils.platform.is_proxy():
            gfn = os.path.join(
                __opts__["conf_file"], "proxy.d", __opts__["id"], "grains"
            )
        else:
            gfn = os.path.join(__opts__["conf_file"], "grains")
    else:
        if salt.utils.platform.is_proxy():
            gfn = os.path.join(
                os.path.dirname(__opts__["conf_file"]),
                "proxy.d",
                __opts__["id"],
                "grains",
            )
        else:
            gfn = os.path.join(os.path.dirname(__opts__["conf_file"]), "grains")

    if os.path.isfile(gfn):
        with salt.utils.files.fopen(gfn, "rb") as fp_:
            try:
                grains = salt.utils.yaml.safe_load(fp_)
            except salt.utils.yaml.YAMLError as exc:
                return "Unable to read existing grains file: {}".format(exc)
        if not isinstance(grains, dict):
            grains = {}
    for key, val in new_grains.items():
        if val is None and destructive is True:
            if key in grains:
                del grains[key]
            if key in __grains__:
                del __grains__[key]
        else:
            grains[key] = val
            __grains__[key] = val
    try:
        with salt.utils.files.fopen(gfn, "w+", encoding="utf-8") as fp_:
            salt.utils.yaml.safe_dump(grains, fp_, default_flow_style=False)
    except OSError:
        log.error("Unable to write to grains file at %s. Check permissions.", gfn)
    fn_ = os.path.join(__opts__["cachedir"], "module_refresh")
    try:
        with salt.utils.files.flopen(fn_, "w+"):
            pass
    except OSError:
        log.error("Unable to write to cache file %s. Check permissions.", fn_)
    if not __opts__.get("local", False):
        # Refresh the grains
        __salt__["saltutil.refresh_grains"](refresh_pillar=refresh_pillar)
    # Return the grains we just set to confirm everything was OK
    return new_grains


def setval(key, val, destructive=False, refresh_pillar=True):
    """
    Set a grains value in the grains config file

    key
        The grain key to be set.

    val
        The value to set the grain key to.

    destructive
        If an operation results in a key being removed, delete the key, too.
        Defaults to False.

    refresh_pillar
        Whether pillar will be refreshed.
        Defaults to True.

    CLI Example:

    .. code-block:: bash

        salt '*' grains.setval key val
        salt '*' grains.setval key "{'sub-key': 'val', 'sub-key2': 'val2'}"
    """
    return setvals({key: val}, destructive, refresh_pillar=refresh_pillar)


def append(key, val, convert=False, delimiter=DEFAULT_TARGET_DELIM):
    """
    .. versionadded:: 0.17.0

    Append a value to a list in the grains config file. If the grain doesn't
    exist, the grain key is added and the value is appended to the new grain
    as a list item.

    key
        The grain key to be appended to

    val
        The value to append to the grain key

    convert
        If convert is True, convert non-list contents into a list.
        If convert is False and the grain contains non-list contents, an error
        is given. Defaults to False.

    delimiter
        The key can be a nested dict key. Use this parameter to
        specify the delimiter you use, instead of the default ``:``.
        You can now append values to a list in nested dictionary grains. If the
        list doesn't exist at this level, it will be created.

        .. versionadded:: 2014.7.6

    CLI Example:

    .. code-block:: bash

        salt '*' grains.append key val
    """
    grains = get(key, [], delimiter)
    if convert:
        if not isinstance(grains, list):
            grains = [] if grains is None else [grains]
    if not isinstance(grains, list):
        return "The key {} is not a valid list".format(key)
    if val in grains:
        return "The val {} was already in the list {}".format(val, key)
    if isinstance(val, list):
        for item in val:
            grains.append(item)
    else:
        grains.append(val)

    while delimiter in key:
        key, rest = key.rsplit(delimiter, 1)
        _grain = get(key, _infinitedict(), delimiter)
        if isinstance(_grain, dict):
            _grain.update({rest: grains})
        grains = _grain

    return setval(key, grains)


def remove(key, val, delimiter=DEFAULT_TARGET_DELIM):
    """
    .. versionadded:: 0.17.0

    Remove a value from a list in the grains config file

    key
        The grain key to remove.

    val
        The value to remove.

    delimiter
        The key can be a nested dict key. Use this parameter to
        specify the delimiter you use, instead of the default ``:``.
        You can now append values to a list in nested dictionary grains. If the
        list doesn't exist at this level, it will be created.

        .. versionadded:: 2015.8.2

    CLI Example:

    .. code-block:: bash

        salt '*' grains.remove key val
    """
    grains = get(key, [], delimiter)
    if not isinstance(grains, list):
        return "The key {} is not a valid list".format(key)
    if val not in grains:
        return "The val {} was not in the list {}".format(val, key)
    grains.remove(val)

    while delimiter in key:
        key, rest = key.rsplit(delimiter, 1)
        _grain = get(key, None, delimiter)
        if isinstance(_grain, dict):
            _grain.update({rest: grains})
        grains = _grain

    return setval(key, grains)


def delkey(key, force=False):
    """
    .. versionadded:: 2017.7.0

    Remove a grain completely from the grain system, this will remove the
    grain key and value

    key
        The grain key from which to delete the value.

    force
        Force remove the grain even when it is a mapped value.
        Defaults to False

    CLI Example:

    .. code-block:: bash

        salt '*' grains.delkey key
    """
    return delval(key, destructive=True, force=force)


def delval(key, destructive=False, force=False):
    """
    .. versionadded:: 0.17.0

    Delete a grain value from the grains config file. This will just set the
    grain value to ``None``. To completely remove the grain, run ``grains.delkey``
    or pass ``destructive=True`` to ``grains.delval``.

    key
        The grain key from which to delete the value.

    destructive
        Delete the key, too. Defaults to False.

    force
        Force remove the grain even when it is a mapped value.
        Defaults to False

    CLI Example:

    .. code-block:: bash

        salt '*' grains.delval key
    """
    return set(key, None, destructive=destructive, force=force)


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
        }, default='Debian') %}

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

        .. versionchanged:: 2016.11.0

            The dictionary key could be a globbing pattern. The function will
            return the corresponding ``lookup_dict`` value where grain value
            matches the pattern. For example:

            .. code-block:: bash

                # this will render 'got some salt' if Minion ID begins from 'salt'
                salt '*' grains.filter_by '{salt*: got some salt, default: salt is not here}' id

    :param grain: The name of a grain to match with the current system's
        grains. For example, the value of the "os_family" grain for the current
        system could be used to pull values from the ``lookup_dict``
        dictionary.

        .. versionchanged:: 2016.11.0

            The grain value could be a list. The function will return the
            ``lookup_dict`` value for a first found item in the list matching
            one of the ``lookup_dict`` keys.

    :param merge: A dictionary to merge with the results of the grain selection
        from ``lookup_dict``. This allows Pillar to override the values in the
        ``lookup_dict``. This could be useful, for example, to override the
        values for non-standard package names such as when using a different
        Python version from the default Python version provided by the OS
        (e.g., ``python26-mysql`` instead of ``python-mysql``).

    :param default: default lookup_dict's key used if the grain does not exists
        or if the grain value has no match on lookup_dict.  If unspecified
        the value is "default".

        .. versionadded:: 2014.1.0

    :param base: A lookup_dict key to use for a base dictionary.  The
        grain-selected ``lookup_dict`` is merged over this and then finally
        the ``merge`` dictionary is merged.  This allows common values for
        each case to be collected in the base and overridden by the grain
        selection dictionary and the merge dictionary.  Default is unset.

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' grains.filter_by '{Debian: Debheads rule, RedHat: I love my hat}'
        # this one will render {D: {E: I, G: H}, J: K}
        salt '*' grains.filter_by '{A: B, C: {D: {E: F, G: H}}}' 'xxx' '{D: {E: I}, J: K}' 'C'
        # next one renders {A: {B: G}, D: J}
        salt '*' grains.filter_by '{default: {A: {B: C}, D: E}, F: {A: {B: G}}, H: {D: I}}' 'xxx' '{D: J}' 'F' 'default'
        # next same as above when default='H' instead of 'F' renders {A: {B: C}, D: J}
    """
    return salt.utils.data.filter_by(
        lookup_dict=lookup_dict,
        lookup=grain,
        traverse=__grains__,
        merge=merge,
        default=default,
        base=base,
    )


def _dict_from_path(path, val, delimiter=DEFAULT_TARGET_DELIM):
    """
    Given a lookup string in the form of 'foo:bar:baz" return a nested
    dictionary of the appropriate depth with the final segment as a value.

    >>> _dict_from_path('foo:bar:baz', 'somevalue')
    {"foo": {"bar": {"baz": "somevalue"}}
    """
    nested_dict = _infinitedict()
    keys = path.rsplit(delimiter)
    lastplace = reduce(operator.getitem, keys[:-1], nested_dict)
    lastplace[keys[-1]] = val

    return nested_dict


def get_or_set_hash(
    name, length=8, chars="abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
):
    """
    Perform a one-time generation of a hash and write it to the local grains.
    If that grain has already been set return the value instead.

    This is useful for generating passwords or keys that are specific to a
    single minion that don't need to be stored somewhere centrally.

    State Example:

    .. code-block:: yaml

        some_mysql_user:
          mysql_user:
            - present
            - host: localhost
            - password: {{ salt['grains.get_or_set_hash']('mysql:some_mysql_user') }}

    CLI Example:

    .. code-block:: bash

        salt '*' grains.get_or_set_hash 'django:SECRET_KEY' 50

    .. warning::

        This function could return strings which may contain characters which are reserved
        as directives by the YAML parser, such as strings beginning with ``%``. To avoid
        issues when using the output of this function in an SLS file containing YAML+Jinja,
        surround the call with single quotes.
    """
    salt.utils.versions.warn_until(
        "Phosphorus",
        "The 'grains.get_or_set_hash' function has been deprecated and it's "
        "functionality will be completely removed. Reference pillar and SDB "
        "documentation for secure ways to manage sensitive information. Grains "
        "are an insecure way to store secrets.",
    )
    ret = get(name, None)

    if ret is None:
        val = "".join([random.SystemRandom().choice(chars) for _ in range(length)])

        if DEFAULT_TARGET_DELIM in name:
            root, rest = name.split(DEFAULT_TARGET_DELIM, 1)
            curr = get(root, _infinitedict())
            val = _dict_from_path(rest, val)
            curr.update(val)
            setval(root, curr)
        else:
            setval(name, val)

    return get(name)


def set(key, val="", force=False, destructive=False, delimiter=DEFAULT_TARGET_DELIM):
    """
    Set a key to an arbitrary value. It is used like setval but works
    with nested keys.

    This function is conservative. It will only overwrite an entry if
    its value and the given one are not a list or a dict. The ``force``
    parameter is used to allow overwriting in all cases.

    .. versionadded:: 2015.8.0

    :param force: Force writing over existing entry if given or existing
                  values are list or dict. Defaults to False.
    :param destructive: If an operation results in a key being removed,
                  delete the key, too. Defaults to False.
    :param delimiter:
        Specify an alternate delimiter to use when traversing a nested dict,
        the default being ``:``

    CLI Example:

    .. code-block:: bash

        salt '*' grains.set 'apps:myApp:port' 2209
        salt '*' grains.set 'apps:myApp' '{port: 2209}'
    """

    ret = {"comment": "", "changes": {}, "result": True}

    # Get val type
    _new_value_type = "simple"
    if isinstance(val, dict):
        _new_value_type = "complex"
    elif isinstance(val, list):
        _new_value_type = "complex"

    _non_existent = object()
    _existing_value = get(key, _non_existent, delimiter)
    _value = _existing_value

    _existing_value_type = "simple"
    if _existing_value is _non_existent:
        _existing_value_type = None
    elif isinstance(_existing_value, dict):
        _existing_value_type = "complex"
    elif isinstance(_existing_value, list):
        _existing_value_type = "complex"

    if (
        _existing_value_type is not None
        and _existing_value == val
        and (val is not None or destructive is not True)
    ):
        ret["comment"] = "Grain is already set"
        return ret

    if _existing_value is not None and not force:
        if _existing_value_type == "complex":
            ret["comment"] = (
                "The key '{}' exists but is a dict or a list. "
                "Use 'force=True' to overwrite.".format(key)
            )
            ret["result"] = False
            return ret
        elif _new_value_type == "complex" and _existing_value_type is not None:
            ret["comment"] = (
                "The key '{}' exists and the given value is a dict or a "
                "list. Use 'force=True' to overwrite.".format(key)
            )
            ret["result"] = False
            return ret
        else:
            _value = val
    else:
        _value = val

    # Process nested grains
    while delimiter in key:
        key, rest = key.rsplit(delimiter, 1)
        _existing_value = get(key, {}, delimiter)
        if isinstance(_existing_value, dict):
            if _value is None and destructive:
                if rest in _existing_value.keys():
                    _existing_value.pop(rest)
            else:
                _existing_value.update({rest: _value})
        elif isinstance(_existing_value, list):
            _list_updated = False
            for _index, _item in enumerate(_existing_value):
                if _item == rest:
                    _existing_value[_index] = {rest: _value}
                    _list_updated = True
                elif isinstance(_item, dict) and rest in _item:
                    _item.update({rest: _value})
                    _list_updated = True
            if not _list_updated:
                _existing_value.append({rest: _value})
        elif _existing_value == rest or force:
            _existing_value = {rest: _value}
        else:
            ret["comment"] = (
                "The key '{}' value is '{}', which is different from "
                "the provided key '{}'. Use 'force=True' to overwrite.".format(
                    key, _existing_value, rest
                )
            )
            ret["result"] = False
            return ret
        _value = _existing_value

    _setval_ret = setval(key, _value, destructive=destructive)
    if isinstance(_setval_ret, dict):
        ret["changes"] = _setval_ret
    else:
        ret["comment"] = _setval_ret
        ret["result"] = False
    return ret


def equals(key, value):
    """
    Used to make sure the minion's grain key/value matches.

    Returns ``True`` if matches otherwise ``False``.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' grains.equals fqdn <expected_fqdn>
        salt '*' grains.equals systemd:version 219
    """
    return str(value) == str(get(key))


# Provide a jinja function call compatible get aliased as fetch
fetch = get

"""
Return config information
"""

import copy
import fnmatch
import logging
import os
import urllib.parse

import salt.config
import salt.syspaths as syspaths
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.platform
import salt.utils.sdb as sdb
from salt.loader.context import LoaderContext

try:
    # Gated for salt-ssh (salt.utils.cloud imports msgpack)
    import salt.utils.cloud

    HAS_CLOUD = True
except ImportError:
    HAS_CLOUD = False


if salt.utils.platform.is_windows():
    _HOSTS_FILE = os.path.join(
        os.environ["SystemRoot"], "System32", "drivers", "etc", "hosts"
    )
else:
    _HOSTS_FILE = os.path.join(os.sep, "etc", "hosts")

log = logging.getLogger(__name__)

__proxyenabled__ = ["*"]
__salt_loader__ = LoaderContext()
__opts__ = __salt_loader__.named_context("__opts__")

# Set up the default values for all systems
DEFAULTS = {
    "mongo.db": "salt",
    "mongo.password": "",
    "mongo.port": 27017,
    "mongo.user": "",
    "redis.db": "0",
    "redis.host": "salt",
    "redis.port": 6379,
    "test.foo": "unconfigured",
    "ca.cert_base_path": "/etc/pki",
    "solr.cores": [],
    "solr.host": "localhost",
    "solr.port": "8983",
    "solr.baseurl": "/solr",
    "solr.type": "master",
    "solr.request_timeout": None,
    "solr.init_script": "/etc/rc.d/solr",
    "solr.dih.import_options": {
        "clean": False,
        "optimize": True,
        "commit": True,
        "verbose": False,
    },
    "solr.backup_path": None,
    "solr.num_backups": 1,
    "poudriere.config": "/usr/local/etc/poudriere.conf",
    "poudriere.config_dir": "/usr/local/etc/poudriere.d",
    "ldap.uri": "",
    "ldap.server": "localhost",
    "ldap.port": "389",
    "ldap.tls": False,
    "ldap.no_verify": False,
    "ldap.anonymous": True,
    "ldap.scope": 2,
    "ldap.attrs": None,
    "ldap.binddn": "",
    "ldap.bindpw": "",
    "hosts.file": _HOSTS_FILE,
    "aliases.file": "/etc/aliases",
    "virt": {
        "tunnel": False,
        "images": os.path.join(syspaths.SRV_ROOT_DIR, "salt-images"),
    },
    "docker.exec_driver": "docker-exec",
    "docker.compare_container_networks": {
        "static": ["Aliases", "Links", "IPAMConfig"],
        "automatic": ["IPAddress", "Gateway", "GlobalIPv6Address", "IPv6Gateway"],
    },
}


def backup_mode(backup=""):
    """
    Return the backup mode

    CLI Example:

    .. code-block:: bash

        salt '*' config.backup_mode
    """
    if backup:
        return backup
    return option("backup_mode")


def manage_mode(mode):
    """
    Return a mode value, normalized to a string

    CLI Example:

    .. code-block:: bash

        salt '*' config.manage_mode
    """
    # config.manage_mode should no longer be invoked from the __salt__ dunder
    # in Salt code, this function is only being left here for backwards
    # compatibility.
    return salt.utils.files.normalize_mode(mode)


def valid_fileproto(uri):
    """
    Returns a boolean value based on whether or not the URI passed has a valid
    remote file protocol designation

    CLI Example:

    .. code-block:: bash

        salt '*' config.valid_fileproto salt://path/to/file
    """
    return urllib.parse.urlparse(uri).scheme in salt.utils.files.VALID_PROTOS


def option(
    value,
    default=None,
    omit_opts=False,
    omit_grains=False,
    omit_pillar=False,
    omit_master=False,
    omit_all=False,
    wildcard=False,
):
    """
    Returns the setting for the specified config value. The priority for
    matches is the same as in :py:func:`config.get <salt.modules.config.get>`,
    only this function does not recurse into nested data structures. Another
    difference between this function and :py:func:`config.get
    <salt.modules.config.get>` is that it comes with a set of "sane defaults".
    To view these, you can run the following command:

    .. code-block:: bash

        salt '*' config.option '*' omit_all=True wildcard=True

    default
        The default value if no match is found. If not specified, then the
        fallback default will be an empty string, unless ``wildcard=True``, in
        which case the return will be an empty dictionary.

    omit_opts : False
        Pass as ``True`` to exclude matches from the minion configuration file

    omit_grains : False
        Pass as ``True`` to exclude matches from the grains

    omit_pillar : False
        Pass as ``True`` to exclude matches from the pillar data

    omit_master : False
        Pass as ``True`` to exclude matches from the master configuration file

    omit_all : True
        Shorthand to omit all of the above and return matches only from the
        "sane defaults".

        .. versionadded:: 3000

    wildcard : False
        If used, this will perform pattern matching on keys. Note that this
        will also significantly change the return data. Instead of only a value
        being returned, a dictionary mapping the matched keys to their values
        is returned. For example, using ``wildcard=True`` with a ``key`` of
        ``'foo.ba*`` could return a dictionary like so:

        .. code-block:: python

            {'foo.bar': True, 'foo.baz': False}

        .. versionadded:: 3000

    CLI Example:

    .. code-block:: bash

        salt '*' config.option redis.host
    """
    if omit_all:
        omit_opts = omit_grains = omit_pillar = omit_master = True

    if default is None:
        default = "" if not wildcard else {}

    if not wildcard:
        if not omit_opts:
            if value in __opts__:
                return __opts__[value]
        if not omit_grains:
            if value in __grains__:
                return __grains__[value]
        if not omit_pillar:
            if value in __pillar__:
                return __pillar__[value]
        if not omit_master:
            if value in __pillar__.get("master", {}):
                return __pillar__["master"][value]
        if value in DEFAULTS:
            return DEFAULTS[value]

        # No match
        return default
    else:
        # We need to do the checks in the reverse order so that minion opts
        # takes precedence
        ret = {}
        for omit, data in (
            (omit_master, __pillar__.get("master", {})),
            (omit_pillar, __pillar__),
            (omit_grains, __grains__),
            (omit_opts, __opts__),
        ):
            if not omit:
                ret.update({x: data[x] for x in fnmatch.filter(data, value)})
        # Check the DEFAULTS as well to see if the pattern matches it
        for item in (x for x in fnmatch.filter(DEFAULTS, value) if x not in ret):
            ret[item] = DEFAULTS[item]

        # If no matches, return the default
        return ret or default


def merge(value, default="", omit_opts=False, omit_master=False, omit_pillar=False):
    """
    Retrieves an option based on key, merging all matches.

    Same as ``option()`` except that it merges all matches, rather than taking
    the first match.

    CLI Example:

    .. code-block:: bash

        salt '*' config.merge schedule
    """
    ret = None
    if not omit_opts:
        if value in __opts__:
            ret = __opts__[value]
            if isinstance(ret, str):
                return ret
    if not omit_master:
        if value in __pillar__.get("master", {}):
            tmp = __pillar__["master"][value]
            if ret is None:
                ret = tmp
                if isinstance(ret, str):
                    return ret
            elif isinstance(ret, dict) and isinstance(tmp, dict):
                tmp.update(ret)
                ret = tmp
            elif isinstance(ret, (list, tuple)) and isinstance(tmp, (list, tuple)):
                ret = list(ret) + list(tmp)
    if not omit_pillar:
        if value in __pillar__:
            tmp = __pillar__[value]
            if ret is None:
                ret = tmp
                if isinstance(ret, str):
                    return ret
            elif isinstance(ret, dict) and isinstance(tmp, dict):
                tmp.update(ret)
                ret = tmp
            elif isinstance(ret, (list, tuple)) and isinstance(tmp, (list, tuple)):
                ret = list(ret) + list(tmp)
    if ret is None and value in DEFAULTS:
        return DEFAULTS[value]
    if ret is None:
        return default
    return ret


def get(
    key,
    default="",
    delimiter=":",
    merge=None,
    omit_opts=False,
    omit_pillar=False,
    omit_master=False,
    omit_grains=False,
):
    """
    .. versionadded:: 0.14.0

    Attempt to retrieve the named value from the minion config file, pillar,
    grains or the master config. If the named value is not available, return
    the value specified by the ``default`` argument. If this argument is not
    specified, ``default`` falls back to an empty string.

    Values can also be retrieved from nested dictionaries. Assume the below
    data structure:

    .. code-block:: python

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the ``apache`` key, in the
    sub-dictionary corresponding to the ``pkg`` key, the following command can
    be used:

    .. code-block:: bash

        salt myminion config.get pkg:apache

    The ``:`` (colon) is used to represent a nested dictionary level.

    .. versionchanged:: 2015.5.0
        The ``delimiter`` argument was added, to allow delimiters other than
        ``:`` to be used.

    This function traverses these data stores in this order, returning the
    first match found:

    - Minion configuration
    - Minion's grains
    - Minion's pillar data
    - Master configuration (requires :conf_minion:`pillar_opts` to be set to
      ``True`` in Minion config file in order to work)

    This means that if there is a value that is going to be the same for the
    majority of minions, it can be configured in the Master config file, and
    then overridden using the grains, pillar, or Minion config file.

    Adding config options to the Master or Minion configuration file is easy:

    .. code-block:: yaml

        my-config-option: value
        cafe-menu:
          - egg and bacon
          - egg sausage and bacon
          - egg and spam
          - egg bacon and spam
          - egg bacon sausage and spam
          - spam bacon sausage and spam
          - spam egg spam spam bacon and spam
          - spam sausage spam spam bacon spam tomato and spam

    .. note::
        Minion configuration options built into Salt (like those defined
        :ref:`here <configuration-salt-minion>`) will *always* be defined in
        the Minion configuration and thus *cannot be overridden by grains or
        pillar data*. However, additional (user-defined) configuration options
        (as in the above example) will not be in the Minion configuration by
        default and thus can be overridden using grains/pillar data by leaving
        the option out of the minion config file.

    **Arguments**

    delimiter
        .. versionadded:: 2015.5.0

        Override the delimiter used to separate nested levels of a data
        structure.

    merge
        .. versionadded:: 2015.5.0

        If passed, this parameter will change the behavior of the function so
        that, instead of traversing each data store above in order and
        returning the first match, the data stores are first merged together
        and then searched. The pillar data is merged into the master config
        data, then the grains are merged, followed by the Minion config data.
        The resulting data structure is then searched for a match. This allows
        for configurations to be more flexible.

        .. note::

            The merging described above does not mean that grain data will end
            up in the Minion's pillar data, or pillar data will end up in the
            master config data, etc. The data is just combined for the purposes
            of searching an amalgam of the different data stores.

        The supported merge strategies are as follows:

        - **recurse** - If a key exists in both dictionaries, and the new value
          is not a dictionary, it is replaced. Otherwise, the sub-dictionaries
          are merged together into a single dictionary, recursively on down,
          following the same criteria. For example:

          .. code-block:: python

              >>> dict1 = {'foo': {'bar': 1, 'qux': True},
                           'hosts': ['a', 'b', 'c'],
                           'only_x': None}
              >>> dict2 = {'foo': {'baz': 2, 'qux': False},
                           'hosts': ['d', 'e', 'f'],
                           'only_y': None}
              >>> merged
              {'foo': {'bar': 1, 'baz': 2, 'qux': False},
               'hosts': ['d', 'e', 'f'],
               'only_dict1': None,
               'only_dict2': None}

        - **overwrite** - If a key exists in the top level of both
          dictionaries, the new value completely overwrites the old. For
          example:

          .. code-block:: python

              >>> dict1 = {'foo': {'bar': 1, 'qux': True},
                           'hosts': ['a', 'b', 'c'],
                           'only_x': None}
              >>> dict2 = {'foo': {'baz': 2, 'qux': False},
                           'hosts': ['d', 'e', 'f'],
                           'only_y': None}
              >>> merged
              {'foo': {'baz': 2, 'qux': False},
               'hosts': ['d', 'e', 'f'],
               'only_dict1': None,
               'only_dict2': None}

    CLI Example:

    .. code-block:: bash

        salt '*' config.get pkg:apache
        salt '*' config.get lxc.container_profile:centos merge=recurse
    """
    if merge is None:
        if not omit_opts:
            ret = salt.utils.data.traverse_dict_and_list(
                __opts__, key, "_|-", delimiter=delimiter
            )
            if ret != "_|-":
                return sdb.sdb_get(ret, __opts__)

        if not omit_grains:
            ret = salt.utils.data.traverse_dict_and_list(
                __grains__, key, "_|-", delimiter
            )
            if ret != "_|-":
                return sdb.sdb_get(ret, __opts__)

        if not omit_pillar:
            ret = salt.utils.data.traverse_dict_and_list(
                __pillar__, key, "_|-", delimiter=delimiter
            )
            if ret != "_|-":
                return sdb.sdb_get(ret, __opts__)

        if not omit_master:
            ret = salt.utils.data.traverse_dict_and_list(
                __pillar__.get("master", {}), key, "_|-", delimiter=delimiter
            )
            if ret != "_|-":
                return sdb.sdb_get(ret, __opts__)

        ret = salt.utils.data.traverse_dict_and_list(
            DEFAULTS, key, "_|-", delimiter=delimiter
        )
        if ret != "_|-":
            return sdb.sdb_get(ret, __opts__)
    else:
        if merge not in ("recurse", "overwrite"):
            log.warning(
                "Unsupported merge strategy '%s'. Falling back to 'recurse'.", merge
            )
            merge = "recurse"

        merge_lists = salt.config.master_config("/etc/salt/master").get(
            "pillar_merge_lists"
        )

        data = copy.copy(DEFAULTS)
        data = salt.utils.dictupdate.merge(
            data, __pillar__.get("master", {}), strategy=merge, merge_lists=merge_lists
        )
        data = salt.utils.dictupdate.merge(
            data, __pillar__, strategy=merge, merge_lists=merge_lists
        )
        data = salt.utils.dictupdate.merge(
            data, __grains__, strategy=merge, merge_lists=merge_lists
        )
        data = salt.utils.dictupdate.merge(
            data, __opts__, strategy=merge, merge_lists=merge_lists
        )
        ret = salt.utils.data.traverse_dict_and_list(
            data, key, "_|-", delimiter=delimiter
        )
        if ret != "_|-":
            return sdb.sdb_get(ret, __opts__)

    return default


def dot_vals(value):
    """
    Pass in a configuration value that should be preceded by the module name
    and a dot, this will return a list of all read key/value pairs

    CLI Example:

    .. code-block:: bash

        salt '*' config.dot_vals host
    """
    ret = {}
    for key, val in __pillar__.get("master", {}).items():
        if key.startswith(f"{value}."):
            ret[key] = val
    for key, val in __opts__.items():
        if key.startswith(f"{value}."):
            ret[key] = val
    return ret


def gather_bootstrap_script(bootstrap=None):
    """
    Download the salt-bootstrap script, and return its location

    bootstrap
        URL of alternate bootstrap script

    CLI Example:

    .. code-block:: bash

        salt '*' config.gather_bootstrap_script
    """
    if not HAS_CLOUD:
        return False, "config.gather_bootstrap_script is unavailable"
    ret = salt.utils.cloud.update_bootstrap(__opts__, url=bootstrap)
    if "Success" in ret and ret["Success"]["Files updated"]:
        return ret["Success"]["Files updated"][0]


def items():
    """
    Return the complete config from the currently running minion process.
    This includes defaults for values not set in the config file.

    CLI Example:

    .. code-block:: bash

        salt '*' config.items
    """
    return __opts__

"""
SSH wrapper module to work with salt formula defaults files

"""

import copy
import logging
import os

import salt.fileclient
import salt.utils.data
import salt.utils.dictupdate as dictupdate
import salt.utils.files
import salt.utils.json
import salt.utils.url
import salt.utils.yaml

__virtualname__ = "defaults"

log = logging.getLogger(__name__)


def _mk_client():
    """
    Create a file client and add it to the context
    """
    return salt.fileclient.get_file_client(__opts__)


def _load(formula):
    """
    Generates a list of salt://<formula>/defaults.(json|yaml) files
    and fetches them from the Salt master.

    Returns first defaults file as python dict.
    """

    # Compute possibilities
    paths = []
    for ext in ("yaml", "json"):
        source_url = salt.utils.url.create(formula + "/defaults." + ext)
        paths.append(source_url)
    # Fetch files from master
    with _mk_client() as client:
        defaults_files = client.cache_files(paths)

    for file_ in defaults_files:
        if not file_:
            # Skip empty string returned by cp.fileclient.cache_files.
            continue

        suffix = file_.rsplit(".", 1)[-1]
        if suffix == "yaml":
            loader = salt.utils.yaml.safe_load
        elif suffix == "json":
            loader = salt.utils.json.load
        else:
            log.debug("Failed to determine loader for %r", file_)
            continue

        if os.path.exists(file_):
            log.debug("Reading defaults from %r", file_)
            with salt.utils.files.fopen(file_) as fhr:
                defaults = loader(fhr)
                log.debug("Read defaults %r", defaults)

            return defaults or {}


def get(key, default=""):
    """
    defaults.get is used much like pillar.get except that it will read
    a default value for a pillar from defaults.json or defaults.yaml
    files that are stored in the root of a salt formula.

    CLI Example:

    .. code-block:: bash

        salt '*' defaults.get core:users:root

    The defaults is computed from pillar key. The first entry is considered as
    the formula namespace.

    For example, querying ``core:users:root`` will try to load
    ``salt://core/defaults.yaml`` and ``salt://core/defaults.json``.
    """

    # Determine formula namespace from query
    if ":" in key:
        namespace, key = key.split(":", 1)
    else:
        namespace, key = key, None

    # Fetch and load defaults formula files from states.
    defaults = _load(namespace)

    # Fetch value
    if key:
        return salt.utils.data.traverse_dict_and_list(defaults, key, default)
    else:
        return defaults


def merge(dest, src, merge_lists=False, in_place=True, convert_none=True):
    """
    defaults.merge
        Allows deep merging of dicts in formulas.

    merge_lists : False
        If True, it will also merge lists instead of replace their items.

    in_place : True
        If True, it will merge into dest dict,
        if not it will make a new copy from that dict and return it.

    convert_none : True
        If True, it will convert src and dest to empty dicts if they are None.
        If True and dest is None but in_place is True, raises TypeError.
        If False it will make a new copy from that dict and return it.

        .. versionadded:: 3005

    CLI Example:

    .. code-block:: bash

        salt '*' defaults.merge '{a: b}' '{d: e}'

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    """
    # Force empty dicts if applicable (useful for cleaner templating)
    src = {} if (src is None and convert_none) else src
    if dest is None and convert_none:
        if in_place:
            raise TypeError("Can't perform in-place merge into NoneType")
        else:
            dest = {}

    if in_place:
        merged = dest
    else:
        merged = copy.deepcopy(dest)
    return dictupdate.update(merged, src, merge_lists=merge_lists)


def deepcopy(source):
    """
    defaults.deepcopy
        Allows deep copy of objects in formulas.

        By default, Python does not copy objects,
        it creates bindings between a target and an object.

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    """
    return copy.deepcopy(source)


def update(dest, defaults, merge_lists=True, in_place=True, convert_none=True):
    """
    defaults.update
        Allows setting defaults for group of data set e.g. group for nodes.

        This function is a combination of defaults.merge
        and defaults.deepcopy to avoid redundant in jinja.

        Example:

        .. code-block:: yaml

            group01:
              defaults:
                enabled: True
                extra:
                  - test
                  - stage
              nodes:
                host01:
                  index: foo
                  upstream: bar
                host02:
                  index: foo2
                  upstream: bar2

        .. code-block:: jinja

            {% do salt['defaults.update'](group01.nodes, group01.defaults) %}

        Each node will look like the following:

        .. code-block:: yaml

            host01:
              enabled: True
              index: foo
              upstream: bar
              extra:
                - test
                - stage

    merge_lists : True
        If True, it will also merge lists instead of replace their items.

    in_place : True
        If True, it will merge into dest dict.
        if not it will make a new copy from that dict and return it.

    convert_none : True
        If True, it will convert src and dest to empty dicts if they are None.
        If True and dest is None but in_place is True, raises TypeError.
        If False it will make a new copy from that dict and return it.

        .. versionadded:: 3005

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    """
    #  Force empty dicts if applicable here
    if in_place:
        if dest is None:
            raise TypeError("Can't perform in-place update into NoneType")
        else:
            nodes = dest
    else:
        dest = {} if (dest is None and convert_none) else dest
        nodes = deepcopy(dest)

    defaults = {} if (defaults is None and convert_none) else defaults

    for node_name, node_vars in nodes.items():
        defaults_vars = deepcopy(defaults)
        node_vars = merge(
            defaults_vars, node_vars, merge_lists=merge_lists, convert_none=convert_none
        )
        nodes[node_name] = node_vars

    return nodes

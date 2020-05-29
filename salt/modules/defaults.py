"""
Module to work with salt formula defaults files

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
    if "cp.fileclient" not in __context__:
        __context__["cp.fileclient"] = salt.fileclient.get_file_client(__opts__)


def _load(formula, saltenv, defaults_files_names):
    """
    Generates a list of salt://<formula>/defaults.(json|yaml) files
    and fetches them from the Salt master.

    If ``defaults_files_names`` is not ``None`` fetches this list
    from the Salt master.

    Returns merge of defaults files as python dict.
    """
    # Compute possibilities
    _mk_client()

    template_ctx = {
        "salt": __salt__,
        "opts": __opts__,
        "grains": __grains__,
        "saltenv": saltenv,
    }
    defaults = {}
    if defaults_files_names is None:
        defaults_files_names = ["defaults.yaml", "defaults.json"]

    paths = [
        salt.utils.url.create(formula + "/" + default_file)
        for default_file in defaults_files_names
    ]

    # Fetch files from master
    defaults_files = __context__["cp.fileclient"].cache_files(paths, saltenv)

    for file_ in defaults_files:
        if not file_:
            # Skip empty string returned by cp.fileclient.cache_files.
            continue

        suffix = file_.rsplit(".", 1)[-1]
        if suffix == "yaml":
            loader = salt.utils.yaml.safe_load
        elif suffix == "json":
            loader = salt.utils.json.loads
        else:
            log.debug("Failed to determine loader for %r", file_)
            continue

        if os.path.exists(file_):
            log.debug("Reading defaults from %r", file_)
            basedir, filename = os.path.split(file_)
            with salt.utils.files.fopen(file_) as fhr:
                rdata = salt.utils.templates.render_jinja_tmpl(
                    salt.utils.stringutils.to_unicode(fhr.read()),
                    context=template_ctx,
                    tmplpath=basedir,
                )
                defaults = merge(defaults, loader(rdata))
                log.debug("Read defaults %r", defaults)

    return defaults


def get(key, default="", saltenv="base", defaults_files_names=None):
    """
    defaults.get is used much like pillar.get except that it will read
    a default value for a pillar from defaults.json or defaults.yaml
    files that are stored in the root of a salt formula.

    saltenv: base

    defaults_files_names: None
        list of default filenames that will be merged in a single python dict.

    CLI Example:

    .. code-block:: bash

        salt '*' defaults.get core:users:root
        salt '*' defaults.get core:users:root saltenv=prod
        salt '*' defaults.get core:users:root saltenv=prod defaults_files_names='['defaults-role1.yaml', 'defaults-role2.yaml']'

    The defaults is computed from pillar key. The first entry is considered as
    the formula namespace.

    For example, querying ``core:users:root`` will try to load
    ``salt://core/defaults.yaml`` and ``salt://core/defaults.json``.

    defaults.(json|yaml) can contain jinja variables and access to salt dicts ``grains['somekey']``,
    ``salt['somekey']`` and ``opts['somekey']``.

    Example:

        .. code-block:: jinja

            {% set os_family = grains['os_family'] %}
            defaults:
                enabled: True
                hostname: {{ grains['fqdn'] }}
                os_family: {{ os_family }}

        .. code-block:: jinja

            {% set os_family = grains['os_family'] %}
            {
                "key": {{ 2+1 }},
                "hostname": "{{ grains['fqdn'] }}",
                os_family: {{ os_family }}
            }
    """

    # Determine formula namespace from query
    if ":" in key:
        namespace, key = key.split(":", 1)
    else:
        namespace, key = key, None

    # Fetch and load defaults formula files from states.
    defaults = _load(namespace, saltenv, defaults_files_names)

    # Fetch value
    if key:
        return salt.utils.data.traverse_dict_and_list(defaults, key, default)
    else:
        return defaults


def merge(dest, src, merge_lists=False, in_place=True):
    """
    defaults.merge
        Allows deep merging of dicts in formulas.

    merge_lists : False
        If True, it will also merge lists instead of replace their items.

    in_place : True
        If True, it will merge into dest dict,
        if not it will make a new copy from that dict and return it.

    CLI Example:

    .. code-block:: bash

        salt '*' defaults.merge '{a: b}' '{d: e}'

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    """
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


def update(dest, defaults, merge_lists=True, in_place=True):
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

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    """

    if in_place:
        nodes = dest
    else:
        nodes = deepcopy(dest)

    for node_name, node_vars in nodes.items():
        defaults_vars = deepcopy(defaults)
        node_vars = merge(defaults_vars, node_vars, merge_lists=merge_lists)
        nodes[node_name] = node_vars

    return nodes

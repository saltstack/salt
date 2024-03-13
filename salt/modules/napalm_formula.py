"""
NAPALM Formula helpers
======================

.. versionadded:: 2019.2.0

This is an Execution Module providing helpers for various NAPALM formulas,
e.g., napalm-interfaces-formula, napalm-bgp-formula, napalm-ntp-formula etc.,
meant to provide various helper functions to make the templates more readable.
"""

import copy
import fnmatch
import logging

import salt.utils.dictupdate

# Import salt modules
import salt.utils.napalm
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.utils.data import traverse_dict_and_list as _traverse_dict_and_list

__proxyenabled__ = ["*"]
__virtualname__ = "napalm_formula"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Available only on NAPALM Minions.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


def _container_path(model, key=None, container=None, delim=DEFAULT_TARGET_DELIM):
    """
    Generate all the possible paths within an OpenConfig-like object.
    This function returns a generator.
    """
    if not key:
        key = ""
    if not container:
        container = "config"
    for model_key, model_value in model.items():
        if key:
            key_depth = "{prev_key}{delim}{cur_key}".format(
                prev_key=key, delim=delim, cur_key=model_key
            )
        else:
            key_depth = model_key
        if model_key == container:
            yield key_depth
        else:
            yield from _container_path(
                model_value, key=key_depth, container=container, delim=delim
            )


def container_path(model, key=None, container=None, delim=DEFAULT_TARGET_DELIM):
    """
    Return the list of all the possible paths in a container, down to the
    ``config`` container.
    This function can be used to verify that the ``model`` is a Python object
    correctly structured and respecting the OpenConfig hierarchy.

    model
        The OpenConfig-structured object to inspect.

    delim: ``:``
        The key delimiter. In particular cases, it is indicated to use ``//``
        as ``:`` might be already used in various cases, e.g., IPv6 addresses,
        interface name (e.g., Juniper QFX series), etc.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_formula.container_path "{'interfaces': {'interface': {'Ethernet1': {'config': {'name': 'Ethernet1'}}}}}"

    The example above would return a list with the following element:
    ``interfaces:interface:Ethernet1:config`` which is the only possible path
    in that hierarchy.

    Other output examples:

    .. code-block:: text

        - interfaces:interface:Ethernet1:config
        - interfaces:interface:Ethernet1:subinterfaces:subinterface:0:config
        - interfaces:interface:Ethernet2:config
    """
    return list(_container_path(model))


def setval(key, val, dict_=None, delim=DEFAULT_TARGET_DELIM):
    """
    Set a value under the dictionary hierarchy identified
    under the key. The target 'foo/bar/baz' returns the
    dictionary hierarchy {'foo': {'bar': {'baz': {}}}}.

    .. note::

        Currently this doesn't work with integers, i.e.
        cannot build lists dynamically.

    CLI Example:

    .. code-block:: bash

        salt '*' formula.setval foo:baz:bar True
    """
    if not dict_:
        dict_ = {}
    prev_hier = dict_
    dict_hier = key.split(delim)
    for each in dict_hier[:-1]:
        if each not in prev_hier:
            prev_hier[each] = {}
        prev_hier = prev_hier[each]
    prev_hier[dict_hier[-1]] = copy.deepcopy(val)
    return dict_


def traverse(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
    """
    Traverse a dict or list using a colon-delimited (or otherwise delimited,
    using the ``delimiter`` param) target string. The target ``foo:bar:0`` will
    return ``data['foo']['bar'][0]`` if this value exists, and will otherwise
    return the dict in the default argument.
    Function will automatically determine the target type.
    The target ``foo:bar:0`` will return data['foo']['bar'][0] if data like
    ``{'foo':{'bar':['baz']}}`` , if data like ``{'foo':{'bar':{'0':'baz'}}}``
    then ``return data['foo']['bar']['0']``

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_formula.traverse "{'foo': {'bar': {'baz': True}}}" foo:baz:bar
    """
    return _traverse_dict_and_list(data, key, default=default, delimiter=delimiter)


def dictupdate(dest, upd, recursive_update=True, merge_lists=False):
    """
    Recursive version of the default dict.update

    Merges upd recursively into dest

    If recursive_update=False, will use the classic dict.update, or fall back
    on a manual merge (helpful for non-dict types like ``FunctionWrapper``).

    If ``merge_lists=True``, will aggregate list object types instead of replace.
    The list in ``upd`` is added to the list in ``dest``, so the resulting list
    is ``dest[key] + upd[key]``. This behaviour is only activated when
    ``recursive_update=True``. By default ``merge_lists=False``.
    """
    return salt.utils.dictupdate.update(
        dest, upd, recursive_update=recursive_update, merge_lists=merge_lists
    )


def defaults(model, defaults_, delim="//", flipped_merge=False):
    """
    Apply the defaults to a Python dictionary having the structure as described
    in the OpenConfig standards.

    model
        The OpenConfig model to apply the defaults to.

    defaults
        The dictionary of defaults. This argument must equally be structured
        with respect to the OpenConfig standards.

        For ease of use, the keys of these support glob matching, therefore
        we don't have to provide the defaults for each entity but only for
        the entity type. See an example below.

    delim: ``//``
        The key delimiter to use. Generally, ``//`` should cover all the possible
        cases, and you don't need to override this value.

    flipped_merge: ``False``
        Whether should merge the model into the defaults, or the defaults
        into the model. Default: ``False`` (merge the model into the defaults,
        i.e., any defaults would be overridden by the values from the ``model``).

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_formula.defaults "{'interfaces': {'interface': {'Ethernet1': {'config': {'name': 'Ethernet1'}}}}}" "{'interfaces': {'interface': {'*': {'config': {'enabled': True}}}}}"

    As one can notice in the example above, the ``*`` corresponds to the
    interface name, therefore, the defaults will be applied on all the
    interfaces.
    """
    merged = {}
    log.debug("Applying the defaults:")
    log.debug(defaults_)
    log.debug("openconfig like dictionary:")
    log.debug(model)
    for model_path in _container_path(model, delim=delim):
        for default_path in _container_path(defaults_, delim=delim):
            log.debug("Comparing %s to %s", model_path, default_path)
            if not fnmatch.fnmatch(model_path, default_path) or not len(
                model_path.split(delim)
            ) == len(default_path.split(delim)):
                continue
            log.debug("%s matches %s", model_path, default_path)
            # If there's a match, it will build the dictionary from the top
            devault_val = _traverse_dict_and_list(
                defaults_, default_path, delimiter=delim
            )
            merged = setval(model_path, devault_val, dict_=merged, delim=delim)
    log.debug("Complete default dictionary")
    log.debug(merged)
    log.debug("Merging with the model")
    log.debug(model)
    if flipped_merge:
        return salt.utils.dictupdate.update(model, merged)
    return salt.utils.dictupdate.update(merged, model)


def render_field(dictionary, field, prepend=None, append=None, quotes=False, **opts):
    """
    Render a field found under the ``field`` level of the hierarchy in the
    ``dictionary`` object.
    This is useful to render a field in a Jinja template without worrying that
    the hierarchy might not exist. For example if we do the following in Jinja:
    ``{{ interfaces.interface.Ethernet5.config.description }}`` for the
    following object:
    ``{'interfaces': {'interface': {'Ethernet1': {'config': {'enabled': True}}}}}``
    it would error, as the ``Ethernet5`` key does not exist.
    With this helper, we can skip this and avoid existence checks. This must be
    however used with care.

    dictionary
        The dictionary to traverse.

    field
        The key name or part to traverse in the ``dictionary``.

    prepend: ``None``
        The text to prepend in front of the text. Usually, we need to have the
        name of the field too when generating the configuration.

    append: ``None``
        Text to append at the end.

    quotes: ``False``
        Whether should wrap the text around quotes.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_formula.render_field "{'enabled': True}" enabled
        # This would return the value of the ``enabled`` leaf key
        salt '*' napalm_formula.render_field "{'enabled': True}" description
        # This would not error

    Jinja usage example:

    .. code-block:: jinja

        {%- set config = {'enabled': True, 'description': 'Interface description'} %}
        {{ salt.napalm_formula.render_field(config, 'description', quotes=True) }}

    The example above would be rendered on Arista / Cisco as:

    .. code-block:: text

        description "Interface description"

    While on Junos (the semicolon is important to be added, otherwise the
    configuration won't be accepted by Junos):

    .. code-block:: text

        description "Interface description";
    """
    value = traverse(dictionary, field)
    if value is None:
        return ""
    if prepend is None:
        prepend = field.replace("_", "-")
    if append is None:
        if __grains__["os"] in ("junos",):
            append = ";"
        else:
            append = ""
    if quotes:
        value = f'"{value}"'
    return "{prepend} {value}{append}".format(
        prepend=prepend, value=value, append=append
    )


def render_fields(dictionary, *fields, **opts):
    """
    This function works similarly to
    :mod:`render_field <salt.modules.napalm_formula.render_field>` but for a
    list of fields from the same dictionary, rendering, indenting and
    distributing them on separate lines.

    dictionary
        The dictionary to traverse.

    fields
        A list of field names or paths in the dictionary.

    indent: ``0``
        The indentation to use, prepended to the rendered field.

    separator: ``\\n``
        The separator to use between fields.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_formula.render_fields "{'mtu': 68, 'description': 'Interface description'}" mtu description

    Jinja usage example:

    .. code-block:: jinja

        {%- set config={'mtu': 68, 'description': 'Interface description'} %}
        {{ salt.napalm_formula.render_fields(config, 'mtu', 'description', quotes=True) }}

    The Jinja example above would generate the following configuration:

    .. code-block:: text

        mtu "68"
        description "Interface description"
    """
    results = []
    for field in fields:
        res = render_field(dictionary, field, **opts)
        if res:
            results.append(res)
    if "indent" not in opts:
        opts["indent"] = 0
    if "separator" not in opts:
        opts["separator"] = "\n{ind}".format(ind=" " * opts["indent"])
    return opts["separator"].join(results)

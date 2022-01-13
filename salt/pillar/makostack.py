"""
Simple and flexible YAML ext_pillar which can read pillar from within pillar.

.. versionadded:: 2016.3.0

This custom saltstack ``ext_pillar`` is a direct ripoff of the 'stack'
ext_pillar, simply ported to use mako instead of jinja2 for templating.

It supports the following features:

- multiple config files that are mako templates with support for ``pillar``,
  ``__grains__``, ``__salt__``, ``__opts__`` variable dereferencing.
- a config file renders as an ordered list of files. Unless absolute, the paths
  of these files are relative to the current config file - if absolute, they
  will be treated literally.
- this list of files are read in order as mako templates with support for
  ``stack``, ``pillar``, ``__grains__``, ``__salt__``, ``__opts__`` variable
  dereferencing.
- all these rendered files are then parsed as ``yaml``.
- then all yaml dicts are merged in order, with support for the following
  merging strategies: ``merge-first``
  ``merge-last``
  ``remove``
  ``overwrite``
- MakoStack config files can be matched based on ``pillar``, ``grains``, or
  ``opts`` values, which make it possible to support kind of self-contained
  environments.

Configuration in Salt
---------------------

Like any other external pillar, its configuration is declared via the
``ext_pillar`` key in the master config file.

However, you can configure MakoStack in 3 different ways:

Single config file
~~~~~~~~~~~~~~~~~~

This is the simplest option, you just need to set the path to your single
MakoStack config file as shown below:

.. code:: yaml

    ext_pillar:
    - makostack: /path/to/stack.cfg

List of config files
~~~~~~~~~~~~~~~~~~~~

You can also provide a list of config files:

.. code:: yaml

    ext_pillar:
    - makostack:
      - /path/to/infrastructure.cfg
      - /path/to/production.cfg

Select config files through grains|pillar|opts matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also use a much more flexible configuration:  MakoStack allows one to
select the config files for the current minion based on matching values from
either grains, or pillar, or opts.

Here is an example of such a configuration, which should hopefully speak for
itself:

.. code:: yaml

    ext_pillar:
    - makostack:
        pillar:environment:
          dev: /path/to/dev/stack.cfg
          prod: /path/to/prod/stack.cfg
        grains:custom:grain:
          value:
          - /path/to/stack1.cfg
          - /path/to/stack2.cfg
        opts:custom:opt:
          value: /path/to/stack0.cfg

Grafting data from files to arbitrary namespaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An extended syntax for config files permits defining "graft points" on a
per-config-file basis.  As an example, if the file foo.cfg would produce the
following:

.. code:: yaml

    foo:
    - bar
    - baz

and you specified the cfg file as ``/path/to/foo.cfg:yummy:fur``, the following
would actually end up in pillar after all merging was complete:

.. code:: yaml

    yummy:
      fur:
        foo:
        - bar
        - baz

MakoStack configuration files
-----------------------------

The config files that are referenced in the above ``ext_pillar`` configuration
are mako templates, which must (eventually) render as a single, simple, flat
ordered list of ``yaml`` files which will then be themselves templated with
mako, with their results merged to build pillar data.

Unless an absolute path name is specified, the path of these ``yaml`` files is
assumed to be relative to the directory containing the MakoStack config file.
If a path begins with '/', however, it will be treated literally and can be
anywhere on the filesystem.

The following variables are available for interpolation in makostack
configuration files:

- ``pillar``: the pillar data (as passed by Salt to our ``ext_pillar`` function)
- ``minion_id``: the minion id ;-)
- ``__opts__``: a dictionary of mostly Salt configuration options
- ``__grains__``: a dictionary of the grains of the minion making this pillar
  call
- ``__salt__``: a dictionary of Salt module functions, useful so you don't have
  to duplicate functions that already exist (note: runs on the master)

So you can use all the power of mako to build your list of ``yaml`` files that
then will be merged in pillar data.

For example, you could have a MakoStack config file which looks like:

.. code:: mako

    $ cat /path/to/makostack/config.cfg
    core.yaml
    osarchs/%{ __grains__['osarch'] }}.yaml
    oscodenames/%{ __grains__['oscodename'] }.yaml
    % for role in pillar.get('roles', []):
    roles/%{ role }.yaml
    % endfor
    minions/%{ minion_id }.yaml

while the directory structure could look like:

.. code::

    $ tree /path/to/makostack/
    /path/to/makostack/
    ├── config.cfg
    ├── core.yaml
    ├── osarchs/
    │   ├── amd64.yaml
    │   └── armhf.yaml
    ├── oscodenames/
    │   ├── wheezy.yaml
    │   └── jessie.yaml
    ├── roles/
    │   ├── web.yaml
    │   └── db.yaml
    └── minions/
        ├── test-1-dev.yaml
        └── test-2-dev.yaml

Overall process
---------------

In the above configuration, given the test-1-dev minion is an amd64 platform
running Debian Jessie and that pillar ``roles`` is ``["db"]``, the following
``yaml`` files would be merged in order:

- ``core.yml``
- ``osarchs/amd64.yml``
- ``oscodenames/jessie.yml``
- ``roles/db.yml``
- ``minions/test-1-dev.yml``

Before merging, every files above will be preprocessed as mako templates.  The
following variables are available in mako templating of ``yaml`` files:

- ``stack``: the MakoStack pillar data object under construction (e.g. data
  from any and all previous ``yaml`` files in MakoStack configuration loaded so
  far).
- ``pillar``: the pillar data (as passed by Salt to our ``ext_pillar``
  function).
- ``minion_id``: the minion id ;-)
- ``__opts__``: a dictionary of mostly Salt configuration options.
- ``__grains__``: a dictionary of the grains of the minion making this pillar
  call.
- ``__salt__``: a dictionary of Salt module functions, useful so you don't have
  to duplicate functions that already exist (note: runs on the master).

So you can use all the power of mako to build your pillar data, and even use
other MakoStack values that have already been parsed and evaluated (from
``yaml`` files earlier in the configuration) through the ``stack`` variable.

Once a ``yaml`` file is processed by mako, we obtain a Python dict - let's call
it ``yml_data``.  This ``yml_data`` dict is then merged into in the main
``stack`` dict (which itself is the already merged MakoStack pillar data).,
based on the declared ``merge-strategy``.  By default, MakoStack will deeply
merge ``yml_data`` into ``stack`` (much like the ``recurse`` option for salt's
``pillar_source_merging_strategy``), but 3 other merging strategies (see next
section) are also available, on a per-object basis, to give you full control
over the rendered data.

Once all ``yaml`` files have been processed, the ``stack`` dict will contain
MakoStack's copmlete pillar data.  At this point the MakoStack ``ext_pillar``
returns the ``stack`` dict to Salt, which then merges it in with any other
pillars, finally returning the whole pillar to the minion.

Merging strategies
------------------

The way the data from a new ``yaml_data`` dict is merged with the existing
``stack`` data can be controlled by specifying a merging strategy.  Available
strategies are:
- ``merge-last`` (the default)
- ``merge-first``
- ``remove``
- ``overwrite``

Note that scalar values like strings, integers, booleans, etc. (`leaf nodes` in
yaml parlance) are always (necessarily) evaluated using ``overwrite`` (other
strategies don't make sense in that case).

The merging strategy can be set by including a dict in the form of:

.. code:: yaml

    __: <merging strategy>

as the first item of the dict or list.  This allows fine grained control over
the merging process.

``merge-last`` (default) strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the ``merge-last`` strategy is selected (the default), then content of dict
or list variables is merged recursively with previous definitions of this
variable (similarly to the ``recurse`` salt
``pillar_source_merging_strategy``).  This allows for extending previously
defined data.

``merge-first`` strategy
~~~~~~~~~~~~~~~~~~~~~~~~

If the ``merge-first`` strategy is selected, then the content of dict or list
variables are swapped between the ``yaml_data`` and ``stack`` objects before
being merged recursively with the previous ``merge-last`` strategy.  This
allows for e.g. prepending to list items and such, and keeping previously
defined dictionary keys (to prevent overwriting "default values" for instance).

``remove`` strategy
~~~~~~~~~~~~~~~~~~~

If the ``remove`` strategy is selected, then content of dict or list variables
in ``stack`` are removed only if the corresponding item is present in the
``yaml_data`` dict.  This allows for removing items entirely from previously
defined data without replacing them with something else.

``overwrite`` strategy
~~~~~~~~~~~~~~~~~~~~~~

If the ``overwrite`` strategy is selected, then the content of dict or list
variables in ``stack`` is overwritten by the content of ``yaml_data`` dict.
This allows one to overwrite variables from previous definitions.

Merging examples
----------------

Let's go through small examples that should clarify what's going on when a
``yaml_data`` dict is merged in the ``stack`` dict.

When you don't specify any strategy, the default ``merge-last`` strategy is
selected:

+----------------------+-----------------------+-------------------------+
| ``stack``            | ``yaml_data``         | ``stack`` (after merge) |
+======================+=======================+=========================+
| .. code:: yaml       | .. code:: yaml        | .. code:: yaml          |
|                      |                       |                         |
|     users:           |     users:            |     users:              |
|       tom:           |       tom:            |       tom:              |
|         uid: 500     |         uid: 1000     |         uid: 1000       |
|         roles:       |         roles:        |         roles:          |
|           - sysadmin |           - developer |           - sysadmin    |
|       root:          |       mat:            |           - developer   |
|         uid: 0       |         uid: 1001     |       mat:              |
|                      |                       |         uid: 1001       |
|                      |                       |       root:             |
|                      |                       |         uid: 0          |
+----------------------+-----------------------+-------------------------+

Then you can select a custom merging strategy using the ``__`` key in a dict:

+----------------------+-----------------------+-------------------------+
| ``stack``            | ``yaml_data``         | ``stack`` (after merge) |
+======================+=======================+=========================+
| .. code:: yaml       | .. code:: yaml        | .. code:: yaml          |
|                      |                       |                         |
|     users:           |     users:            |     users:              |
|       tom:           |       __: merge-last  |       tom:              |
|         uid: 500     |       tom:            |         uid: 1000       |
|         roles:       |         uid: 1000     |         roles:          |
|           - sysadmin |         roles:        |           - sysadmin    |
|       root:          |           - developer |           - developer   |
|         uid: 0       |       mat:            |       mat:              |
|                      |         uid: 1001     |         uid: 1001       |
|                      |                       |       root:             |
|                      |                       |         uid: 0          |
+----------------------+-----------------------+-------------------------+
| .. code:: yaml       | .. code:: yaml        | .. code:: yaml          |
|                      |                       |                         |
|     users:           |     users:            |     users:              |
|       tom:           |       __: merge-first |       tom:              |
|         uid: 500     |       tom:            |         uid: 500        |
|         roles:       |         uid: 1000     |         roles:          |
|           - sysadmin |         roles:        |           - developer   |
|       root:          |           - developer |           - sysadmin    |
|         uid: 0       |       mat:            |       mat:              |
|                      |         uid: 1001     |         uid: 1001       |
|                      |                       |       root:             |
|                      |                       |         uid: 0          |
+----------------------+-----------------------+-------------------------+
| .. code:: yaml       | .. code:: yaml        | .. code:: yaml          |
|                      |                       |                         |
|     users:           |     users:            |     users:              |
|       tom:           |       __: remove      |       root:             |
|         uid: 500     |       tom:            |         uid: 0          |
|         roles:       |       mat:            |                         |
|           - sysadmin |                       |                         |
|       root:          |                       |                         |
|         uid: 0       |                       |                         |
+----------------------+-----------------------+-------------------------+
| .. code:: yaml       | .. code:: yaml        | .. code:: yaml          |
|                      |                       |                         |
|     users:           |     users:            |     users:              |
|       tom:           |       __: overwrite   |       tom:              |
|         uid: 500     |       tom:            |         uid: 1000       |
|         roles:       |         uid: 1000     |         roles:          |
|           - sysadmin |         roles:        |           - developer   |
|       root:          |           - developer |       mat:              |
|         uid: 0       |       mat:            |         uid: 1001       |
|                      |         uid: 1001     |                         |
+----------------------+-----------------------+-------------------------+

Similarly, list allow a custom merging strategy using a ``__`` item:

+----------------+-------------------------+-------------------------+
| ``stack``      | ``yaml_data``           | ``stack`` (after merge) |
+================+=========================+=========================+
| .. code:: yaml | .. code:: yaml          | .. code:: yaml          |
|                |                         |                         |
|     users:     |     users:              |     users:              |
|       - tom    |       - __: merge-last  |       - tom             |
|       - root   |       - mat             |       - root            |
|                |                         |       - mat             |
+----------------+-------------------------+-------------------------+
| .. code:: yaml | .. code:: yaml          | .. code:: yaml          |
|                |                         |                         |
|     users:     |     users:              |     users:              |
|       - tom    |       - __: merge-first |       - mat             |
|       - root   |       - mat             |       - tom             |
|                |                         |       - root            |
+----------------+-------------------------+-------------------------+
| .. code:: yaml | .. code:: yaml          | .. code:: yaml          |
|                |                         |                         |
|     users:     |     users:              |     users:              |
|       - tom    |       - __: remove      |       - root            |
|       - root   |       - mat             |                         |
|                |       - tom             |                         |
+----------------+-------------------------+-------------------------+
| .. code:: yaml | .. code:: yaml          | .. code:: yaml          |
|                |                         |                         |
|     users:     |     users:              |     users:              |
|       - tom    |       - __: overwrite   |       - mat             |
|       - root   |       - mat             |                         |
+----------------+-------------------------+-------------------------+

Tweaking MakoStack
------------------

Out of the box, MakoStack (following the ``stack`` module it was cribbed from),
will more or less silently pass over template files it cannot load due to mako
or yaml parsing errors.  This is convenient, but arguably WRONG, behaviour; but
for backwards compatibility, it is maintained as the default.

If desired, a configuration option may be set via a ``config`` entry under the
``ext_pillar`` definition for MakoStack, as shown in the following snippet:

It's also possible (though not really recommended) to set a
``fail_on_missing_file`` option, which will cause a compilation error whenever
a "potential" file isn't found during processing.  This is largely contrary to
the intended usage of MakoStack (which is to let it search for and utilize any
files under a directory tree, quietly loading those it finds, and ignoring any
missing), but it MIGHT be useful to someone, somewhere so I added it...

.. code:: yaml

    ext_pillar:
    - config:
        fail_on_parse_error: True
        fail_on_missing_file: False
    - makostack: /path/to/stack.cfg

This will cause MakoStack to still ignore non-existant files, but fail on
actual parse errors inside files that do exist.  Note that False is the default
for both options, so neither need be provided unless the intention is to set it
to True.

"""


import functools
import logging
import os

import salt.utils.yaml
from salt.exceptions import CommandExecutionError

try:
    from mako.lookup import TemplateLookup
    from mako import exceptions

    HAS_MAKO = True
except ImportError:
    HAS_MAKO = False

log = logging.getLogger(__name__)
strategies = ("overwrite", "merge-first", "merge-last", "remove")

__virtualname__ = "makostack"


# Only load in this module if the EC2 configurations are in place
def __virtual__():
    """
    Set up the libcloud functions and check for EC2 configurations
    """
    if HAS_MAKO is True:
        return __virtualname__
    return False


def ext_pillar(minion_id, pillar, *args, **kwargs):
    import salt.utils.data

    stack = {}
    config = {}
    stack_config_files = []
    for item in args:
        if isinstance(item, dict) and "config" in item:
            config = item["config"]
        else:
            stack_config_files += [item]
    traverse = {
        "pillar": functools.partial(salt.utils.data.traverse_dict_and_list, pillar),
        "grains": functools.partial(salt.utils.data.traverse_dict_and_list, __grains__),
        "opts": functools.partial(salt.utils.data.traverse_dict_and_list, __opts__),
    }
    for matcher, matchs in kwargs.items():
        t, matcher = matcher.split(":", 1)
        if t not in traverse:
            raise Exception(
                'Unknown traverse option "{}", should be one of {}'.format(
                    t, traverse.keys()
                )
            )
        cfgs = matchs.get(traverse[t](matcher, None), [])
        if not isinstance(cfgs, list):
            cfgs = [cfgs]
        stack_config_files += cfgs
    for cfg in stack_config_files:
        if ":" in cfg:
            cfg, namespace = cfg.split(":", 1)
        else:
            namespace = None
        if not os.path.isfile(cfg):
            log.warning("Ignoring MakoStack cfg %r: file not found", cfg)
            continue
        stack = _process_stack_cfg(cfg, stack, minion_id, pillar, namespace, config)
    return stack


def _process_stack_cfg(cfg, stack, minion_id, pillar, namespace, config):
    basedir, filename = os.path.split(cfg)
    lookup = TemplateLookup(directories=[basedir])
    data = lookup.get_template(filename).render(
        __opts__=__opts__,
        __salt__=__salt__,
        __grains__=__grains__,
        minion_id=minion_id,
        pillar=pillar,
        stack=stack,
    )
    for line in _parse_top_cfg(data, cfg):
        dirs = [basedir]
        dirs += ["/"] if line.startswith("/") else []
        lookup = TemplateLookup(directories=dirs)
        try:
            p = lookup.get_template(line).render(
                __opts__=__opts__,
                __salt__=__salt__,
                __grains__=__grains__,
                minion_id=minion_id,
                pillar=pillar,
                stack=stack,
            )
            obj = salt.utils.yaml.safe_load(p)
            if not isinstance(obj, dict):
                msg = "Can't parse makostack template `{}` as a valid yaml dictionary".format(
                    line
                )
                log.error(msg)
                raise KeyError(msg)
            if namespace:
                for sub in namespace.split(":")[::-1]:
                    obj = {sub: obj}
            stack = _merge_dict(stack, obj)
            log.debug("MakoStack template %r parsed", line)
        except exceptions.TopLevelLookupException as err:
            if config.get("fail_on_missing_file"):
                msg = (
                    "MakoStack template {!r} not found - aborting compilation.".format(
                        line
                    )
                )
                log.error(msg)
                raise CommandExecutionError(msg)
            log.info("MakoStack template %r not found.", line)
            continue
        except Exception as err:  # pylint: disable=broad-except
            # Catches the above KeyError, and any other parsing errors...
            if config.get("fail_on_parse_error"):
                msg = "Invalid MakoStack template `{}` - aborting compilation:\n{}".format(
                    line, exceptions.text_error_template().render()
                )
                log.error(msg)
                raise CommandExecutionError(msg)
            msg = "Invalid MakoStack template `{}`:\n{}".format(
                line, exceptions.text_error_template().render()
            )
            log.warning(msg)
            continue
    return stack


def _cleanup(obj):
    if obj:
        if isinstance(obj, dict):
            obj.pop("__", None)
            for k, v in obj.items():
                obj[k] = _cleanup(v)
        elif isinstance(obj, list) and isinstance(obj[0], dict) and "__" in obj[0]:
            del obj[0]
    return obj


def _merge_dict(stack, obj):
    strategy = obj.pop("__", "merge-last")
    if strategy not in strategies:
        raise Exception(
            "Unknown strategy {!r}, should be one of {}".format(strategy, strategies)
        )
    if strategy == "overwrite":
        return _cleanup(obj)
    else:
        for k, v in obj.items():
            if strategy == "remove":
                stack.pop(k, None)
                continue
            if k in stack:
                if strategy == "merge-first":
                    # merge-first is same as merge-last but the other way round
                    # so let's switch stack[k] and v
                    stack_k = stack[k]
                    stack[k] = _cleanup(v)
                    v = stack_k
                if type(stack[k]) != type(v):
                    log.debug(
                        "Force overwrite, types %r != %r (%r != %r) differ",
                        type(stack[k]),
                        type(v),
                        stack[k],
                        v,
                    )
                    stack[k] = _cleanup(v)
                elif isinstance(v, dict):
                    stack[k] = _merge_dict(stack[k], v)
                elif isinstance(v, list):
                    stack[k] = _merge_list(stack[k], v)
                else:
                    stack[k] = v
            else:
                stack[k] = _cleanup(v)
        return stack


def _merge_list(stack, obj):
    strategy = "merge-last"
    if obj and isinstance(obj[0], dict) and "__" in obj[0]:
        strategy = obj[0]["__"]
        del obj[0]
    if strategy not in strategies:
        raise Exception(
            "Unknown strategy {!r}, should be one of {!r}".format(strategy, strategies)
        )
    if strategy == "overwrite":
        return obj
    elif strategy == "remove":
        return [item for item in stack if item not in obj]
    elif strategy == "merge-first":
        return obj + stack
    else:
        return stack + obj


def _parse_top_cfg(content, filename):
    """
    Allow top_cfg to be YAML
    """
    try:
        obj = salt.utils.yaml.safe_load(content)
        if isinstance(obj, list):
            log.debug("MakoStack cfg %r parsed as YAML", filename)
            return obj
    except Exception as err:  # pylint: disable=broad-except
        pass
    log.debug("MakoStack cfg %r parsed as plain text", filename)
    return [line for line in (l.strip() for l in content.splitlines()) if line]

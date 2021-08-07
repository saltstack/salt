"""
Simple and flexible YAML ext_pillar which can read pillar from within pillar.

.. versionadded:: 2016.3.0

This custom saltstack ``ext_pillar`` is a direct ripoff of the 'stack'
ext_pillar, simply ported to use mako instead of jinja2 for templating.

It supports the following features:

- multiple config files that are mako templates with support for ``pillar``,
  ``__grains__``, ``__salt__``, ``__opts__`` objects.
- a config file renders as an ordered list of files. Unless absolute, the paths
  of these files are relative to the current config file - if absolute, they
  will be treated literally.
- this list of files are read in order as mako templates with support for
  ``stack``, ``pillar``, ``__grains__``, ``__salt__``, ``__opts__`` objects.
- all these rendered files are then parsed as ``yaml``.
- then all yaml dicts are merged in order, with support for the following.
  merging strategies: ``merge-first``, ``merge-last``, ``remove``, and
  ``overwrite``.
- stack config files can be matched based on ``pillar``, ``grains``, or
  ``opts`` values, which make it possible to support kind of self-contained
  environments.

Configuration in Salt
---------------------

Like any other external pillar, its configuration takes place through the
``ext_pillar`` key in the master config file.

However, you can configure MakoStack in 3 different ways:

Single config file
~~~~~~~~~~~~~~~~~~

This is the simplest option, you just need to set the path to your single
MakoStack config file like below:

.. code:: yaml

    ext_pillar:
      - makostack: /path/to/stack.cfg

List of config files
~~~~~~~~~~~~~~~~~~~~

You can also provide a list of config files:

.. code:: yaml

    ext_pillar:
      - makostack:
          - /path/to/stack1.cfg
          - /path/to/stack2.cfg

Select config files through grains|pillar|opts matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also opt for a much more flexible configuration: MakoStack allows one to
select the config files for the current minion based on matching values from
either grains, or pillar, or opts objects.

Here is an example of such a configuration, which should speak by itself:

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
per-config-file basis.  As an example, if the file foo.cfg would produce
the following:

.. code:: yaml

    foo:
      - bar
      - baz

and you specified the cfg file as /path/to/foo.cfg:yummy:fur, the following
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
are mako templates which must render as a simple ordered list of ``yaml``
files that will then be merged to build pillar data.

Unless an absolute path name is specified, the path of these ``yaml`` files is
assumed to be relative to the directory containing the MakoStack config file.
If a path begins with '/', however, it will be treated literally and can be
anywhere on the filesystem.

The following variables are available in mako templating of makostack
configuration files:

- ``pillar``: the pillar data (as passed by Salt to our ``ext_pillar``
  function)
- ``minion_id``: the minion id ;-)
- ``__opts__``: a dictionary of mostly Salt configuration options
- ``__grains__``: a dictionary of the grains of the minion making this pillar
  call
- ``__salt__``: a dictionary of Salt module functions, useful so you don't have
  to duplicate functions that already exist (note: runs on the master)

So you can use all the power of mako to build your list of ``yaml`` files
that will be merged in pillar data.

For example, you could have a MakoStack config file which looks like:

.. code:: mako

    $ cat /path/to/stack/config.cfg
    core.yml
    osarchs/%{ __grains__['osarch'] }}.yml
    oscodenames/%{ __grains__['oscodename'] }.yml
    % for role in pillar.get('roles', []):
    roles/%{ role }.yml
    % endfor
    minions/%{ minion_id }.yml

And the whole directory structure could look like:

.. code::

    $ tree /path/to/stack/
    /path/to/stack/
    ├── config.cfg
    ├── core.yml
    ├── osarchs/
    │   ├── amd64.yml
    │   └── armhf.yml
    ├── oscodenames/
    │   ├── wheezy.yml
    │   └── jessie.yml
    ├── roles/
    │   ├── web.yml
    │   └── db.yml
    └── minions/
        ├── test-1-dev.yml
        └── test-2-dev.yml

Overall process
---------------

In the above MakoStack configuration, given that test-1-dev minion is an
amd64 platform running Debian Jessie, and which pillar ``roles`` is ``["db"]``,
the following ``yaml`` files would be merged in order:

- ``core.yml``
- ``osarchs/amd64.yml``
- ``oscodenames/jessie.yml``
- ``roles/db.yml``
- ``minions/test-1-dev.yml``

Before merging, every files above will be preprocessed as mako templates.
The following variables are available in mako templating of ``yaml`` files:

- ``stack``: the MakoStack pillar data object that has currently been merged
  (data from previous ``yaml`` files in MakoStack configuration)
- ``pillar``: the pillar data (as passed by Salt to our ``ext_pillar``
  function)
- ``minion_id``: the minion id ;-)
- ``__opts__``: a dictionary of mostly Salt configuration options
- ``__grains__``: a dictionary of the grains of the minion making this pillar
  call
- ``__salt__``: a dictionary of Salt module functions, useful so you don't have
  to duplicate functions that already exist (note: runs on the master)

So you can use all the power of mako to build your pillar data, and even use
other pillar values that has already been merged by MakoStack (from previous
``yaml`` files in MakoStack configuration) through the ``stack`` variable.

Once a ``yaml`` file has been preprocessed by mako, we obtain a Python dict -
let's call it ``yml_data`` - then, MakoStack will merge this ``yml_data``
dict in the main ``stack`` dict (which contains already merged MakoStack
pillar data).
By default, MakoStack will deeply merge ``yml_data`` in ``stack`` (similarly
to the ``recurse`` salt ``pillar_source_merging_strategy``), but 3 merging
strategies are currently available for you to choose (see next section).

Once every ``yaml`` files have been processed, the ``stack`` dict will contain
your whole own pillar data, merged in order by MakoStack.
So MakoStack ``ext_pillar`` returns the ``stack`` dict, the contents of which
Salt takes care to merge in with all of the other pillars and finally return
the whole pillar to the minion.

Merging strategies
------------------

The way the data from a new ``yaml_data`` dict is merged with the existing
``stack`` data can be controlled by specifying a merging strategy. Right now
this strategy can either be ``merge-last`` (the default), ``merge-first``,
``remove``, or ``overwrite``.

Note that scalar values like strings, integers, booleans, etc. are always
evaluated using the ``overwrite`` strategy (other strategies don't make sense
in that case).

The merging strategy can be set by including a dict in the form of:

.. code:: yaml

    __: <merging strategy>

as the first item of the dict or list.
This allows fine grained control over the merging process.

``merge-last`` (default) strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the ``merge-last`` strategy is selected (the default), then content of dict
or list variables is merged recursively with previous definitions of this
variable (similarly to the ``recurse`` salt
``pillar_source_merging_strategy``).
This allows for extending previously defined data.

``merge-first`` strategy
~~~~~~~~~~~~~~~~~~~~~~~~

If the ``merge-first`` strategy is selected, then the content of dict or list
variables are swapped between the ``yaml_data`` and ``stack`` objects before
being merged recursively with the ``merge-last`` previous strategy.

``remove`` strategy
~~~~~~~~~~~~~~~~~~~

If the ``remove`` strategy is selected, then content of dict or list variables
in ``stack`` are removed only if the corresponding item is present in the
``yaml_data`` dict.
This allows for removing items from previously defined data.

``overwrite`` strategy
~~~~~~~~~~~~~~~~~~~~~~

If the ``overwrite`` strategy is selected, then the content of dict or list
variables in ``stack`` is overwritten by the content of ``yaml_data`` dict.
So this allows one to overwrite variables from previous definitions.

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

You can also select a custom merging strategy using a ``__`` object in a list:

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
"""


import functools
import logging
import os

import salt.utils.yaml

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
    stack_config_files = list(args)
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
            log.warning('Ignoring Stack cfg "%s": file does not exist', cfg)
            continue
        stack = _process_stack_cfg(cfg, stack, minion_id, pillar, namespace)
    return stack


def _process_stack_cfg(cfg, stack, minion_id, pillar, namespace):
    basedir, filename = os.path.split(cfg)
    lookup = TemplateLookup(directories=[basedir])
    tops = lookup.get_template(filename).render(
        __opts__=__opts__,
        __salt__=__salt__,
        __grains__=__grains__,
        minion_id=minion_id,
        pillar=pillar,
        stack=stack,
    )
    for path in _parse_top_cfg(tops):
        dirs = [basedir]
        if path.startswith("/"):
            dirs += ["/"]
        lookup = TemplateLookup(directories=dirs)
        try:
            p = lookup.get_template(path).render(
                __opts__=__opts__,
                __salt__=__salt__,
                __grains__=__grains__,
                minion_id=minion_id,
                pillar=pillar,
                stack=stack,
            )
            obj = salt.utils.yaml.safe_load(p)
            if not isinstance(obj, dict):
                log.info(
                    'Ignoring Stack template "%s": Can\'t parse as a valid '
                    "yaml dictionary",
                    path,
                )
                continue
            if namespace:
                for sub in namespace.split(":")[::-1]:
                    obj = {sub: obj}
            stack = _merge_dict(stack, obj)
            log.info('Stack template "%s" parsed', path)
        except exceptions.TopLevelLookupException as e:
            log.info('Stack template "%s" not found.', path)
            continue
        except Exception as e:  # pylint: disable=broad-except
            log.info('Ignoring Stack template "%s":', path)
            log.info("%s", exceptions.text_error_template().render())
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
            'Unknown strategy "{}", should be one of {}'.format(strategy, strategies)
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
                        "Force overwrite, types differ: '%s' != '%s'", stack[k], v
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
            'Unknown strategy "{}", should be one of {}'.format(strategy, strategies)
        )
    if strategy == "overwrite":
        return obj
    elif strategy == "remove":
        return [item for item in stack if item not in obj]
    elif strategy == "merge-first":
        return obj + stack
    else:
        return stack + obj


def _parse_top_cfg(content):
    """
    Allow top_cfg to be YAML
    """
    try:
        obj = salt.utils.yaml.safe_load(content)
        if isinstance(obj, list):
            return obj
    except Exception as e:  # pylint: disable=broad-except
        pass
    return content.splitlines()

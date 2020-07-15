# -*- coding: utf-8 -*-
"""
Saltutil State
==============

This state wraps the saltutil execution modules to make them easier to run
from a states. Rather than needing to to use ``module.run`` this state allows for
improved change detection.

    .. versionadded: 3000
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Define the module's virtual name
__virtualname__ = "saltutil"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Named saltutil
    """
    return __virtualname__


def _sync_single(name, module, **kwargs):
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "saltutil.sync_{0} would have been run".format(module)
        return ret

    try:
        sync_status = __salt__["saltutil.sync_{0}".format(module)](**kwargs)
        if sync_status:
            ret["changes"][module] = sync_status
            ret["comment"] = "Updated {0}.".format(module)
    except Exception as e:  # pylint: disable=broad-except
        log.error("Failed to run saltutil.sync_%s: %s", module, e)
        ret["result"] = False
        ret["comment"] = "Failed to run sync_{0}: {1}".format(module, e)
        return ret

    if not ret["changes"]:
        ret["comment"] = "No updates to sync"

    return ret


def sync_all(name, **kwargs):
    """
    Performs the same task as saltutil.sync_all module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_all:
            - refresh: True
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "saltutil.sync_all would have been run"
        return ret

    try:
        sync_status = __salt__["saltutil.sync_all"](**kwargs)
        for key, value in sync_status.items():
            if value:
                ret["changes"][key] = value
                ret["comment"] = "Sync performed"
    except Exception as e:  # pylint: disable=broad-except
        log.error("Failed to run saltutil.sync_all: %s", e)
        ret["result"] = False
        ret["comment"] = "Failed to run sync_all: {0}".format(e)
        return ret

    if not ret["changes"]:
        ret["comment"] = "No updates to sync"

    return ret


def sync_beacons(name, **kwargs):
    """
    Performs the same task as saltutil.sync_beacons module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_beacons:
            - refresh: True
    """
    return _sync_single(name, "beacons", **kwargs)


def sync_clouds(name, **kwargs):
    """
    Performs the same task as saltutil.sync_clouds module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_clouds:
            - refresh: True
    """
    return _sync_single(name, "clouds", **kwargs)


def sync_engines(name, **kwargs):
    """
    Performs the same task as saltutil.sync_engines module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_engines:
            - refresh: True
    """
    return _sync_single(name, "engines", **kwargs)


def sync_grains(name, **kwargs):
    """
    Performs the same task as saltutil.sync_grains module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_grains:
            - refresh: True
    """
    return _sync_single(name, "grains", **kwargs)


def sync_executors(name, **kwargs):
    """
    Performs the same task as saltutil.sync_executors module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_executors:
            - refresh: True
    """
    return _sync_single(name, "executors", **kwargs)


def sync_log_handlers(name, **kwargs):
    """
    Performs the same task as saltutil.sync_log_handlers module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_log_handlers:
            - refresh: True
    """
    return _sync_single(name, "log_handlers", **kwargs)


def sync_modules(name, **kwargs):
    """
    Performs the same task as saltutil.sync_modules module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_modules:
            - refresh: True
    """
    return _sync_single(name, "modules", **kwargs)


def sync_output(name, **kwargs):
    """
    Performs the same task as saltutil.sync_output module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_output:
            - refresh: True
    """
    return _sync_single(name, "output", **kwargs)


def sync_outputters(name, **kwargs):
    """
    Performs the same task as saltutil.sync_outputters module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_outputters:
            - refresh: True
    """
    return _sync_single(name, "outputters", **kwargs)


def sync_pillar(name, **kwargs):
    """
    Performs the same task as saltutil.sync_pillar module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_pillar:
            - refresh: True
    """
    return _sync_single(name, "pillar", **kwargs)


def sync_proxymodules(name, **kwargs):
    """
    Performs the same task as saltutil.sync_proxymodules module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_proxymodules:
            - refresh: True
    """
    return _sync_single(name, "proxymodules", **kwargs)


def sync_matchers(name, **kwargs):
    """
    Performs the same task as saltutil.sync_matchers module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_matchers:
            - refresh: True
    """
    return _sync_single(name, "matchers", **kwargs)


def sync_renderers(name, **kwargs):
    """
    Performs the same task as saltutil.sync_renderers module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_renderers:
            - refresh: True
    """
    return _sync_single(name, "renderers", **kwargs)


def sync_returners(name, **kwargs):
    """
    Performs the same task as saltutil.sync_returners module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_returners:
            - refresh: True
    """
    return _sync_single(name, "returners", **kwargs)


def sync_sdb(name, **kwargs):
    """
    Performs the same task as saltutil.sync_sdb module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_sdb:
            - refresh: True
    """
    return _sync_single(name, "sdb", **kwargs)


def sync_states(name, **kwargs):
    """
    Performs the same task as saltutil.sync_states module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_states:
            - refresh: True
    """
    return _sync_single(name, "states", **kwargs)


def sync_thorium(name, **kwargs):
    """
    Performs the same task as saltutil.sync_thorium module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_thorium:
            - refresh: True
    """
    return _sync_single(name, "thorium", **kwargs)


def sync_utils(name, **kwargs):
    """
    Performs the same task as saltutil.sync_utils module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_utils:
            - refresh: True
    """
    return _sync_single(name, "utils", **kwargs)


def sync_serializers(name, **kwargs):
    """
    Performs the same task as saltutil.sync_serializers module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_serializers:
            - refresh: True
    """
    return _sync_single(name, "serializers", **kwargs)

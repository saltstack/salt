"""
The Saltutil module is used to manage the state of the salt minion itself. It
is used to manage minion modules as well as automate updates to the salt
minion.

:depends:   - esky Python module for update functionality
"""

import copy
import fnmatch
import logging
import os
import shutil
import signal
import sys
import time
import urllib.error

import salt
import salt.channel.client
import salt.client
import salt.client.ssh.client
import salt.config
import salt.defaults.events
import salt.payload
import salt.runner
import salt.state
import salt.utils.args
import salt.utils.event
import salt.utils.extmods
import salt.utils.files
import salt.utils.functools
import salt.utils.minion
import salt.utils.path
import salt.utils.process
import salt.utils.url
import salt.wheel
from salt.exceptions import (
    CommandExecutionError,
    SaltInvocationError,
    SaltRenderError,
    SaltReqTimeoutError,
)

try:
    import esky
    from esky import EskyVersionError

    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False

# pylint: enable=import-error,no-name-in-module

# Fix a nasty bug with Win32 Python not supporting all of the standard signals
try:
    salt_SIGKILL = signal.SIGKILL
except AttributeError:
    salt_SIGKILL = signal.SIGTERM


HAS_PSUTIL = True
try:
    import salt.utils.psutil_compat
except ImportError:
    HAS_PSUTIL = False


__proxyenabled__ = ["*"]

log = logging.getLogger(__name__)


def _get_top_file_envs():
    """
    Get all environments from the top file
    """
    try:
        return __context__["saltutil._top_file_envs"]
    except KeyError:
        with salt.state.HighState(__opts__, initial_pillar=__pillar__.value()) as st_:
            try:
                top = st_.get_top()
                if top:
                    envs = list(st_.top_matches(top).keys()) or "base"
                else:
                    envs = "base"
            except SaltRenderError as exc:
                raise CommandExecutionError(
                    "Unable to render top file(s): {}".format(exc)
                )
        __context__["saltutil._top_file_envs"] = envs
        return envs


def _sync(form, saltenv=None, extmod_whitelist=None, extmod_blacklist=None):
    """
    Sync the given directory in the given environment
    """
    if saltenv is None:
        saltenv = _get_top_file_envs()
    if isinstance(saltenv, str):
        saltenv = saltenv.split(",")
    ret, touched = salt.utils.extmods.sync(
        __opts__,
        form,
        saltenv=saltenv,
        extmod_whitelist=extmod_whitelist,
        extmod_blacklist=extmod_blacklist,
    )
    # Dest mod_dir is touched? trigger reload if requested
    if touched:
        mod_file = os.path.join(__opts__["cachedir"], "module_refresh")
        with salt.utils.files.fopen(mod_file, "a"):
            pass
    if (
        form == "grains"
        and __opts__.get("grains_cache")
        and os.path.isfile(os.path.join(__opts__["cachedir"], "grains.cache.p"))
    ):
        try:
            os.remove(os.path.join(__opts__["cachedir"], "grains.cache.p"))
        except OSError:
            log.error("Could not remove grains cache!")
    return ret


def update(version=None):
    """
    Update the salt minion from the URL defined in opts['update_url']
    VMware, Inc provides the latest builds here:
    update_url: https://repo.saltproject.io/windows/

    Be aware that as of 2014-8-11 there's a bug in esky such that only the
    latest version available in the update_url can be downloaded and installed.

    This feature requires the minion to be running a bdist_esky build.

    The version number is optional and will default to the most recent version
    available at opts['update_url'].

    Returns details about the transaction upon completion.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.update
        salt '*' saltutil.update 0.10.3
    """
    ret = {}
    if not HAS_ESKY:
        ret["_error"] = "Esky not available as import"
        return ret
    if not getattr(sys, "frozen", False):
        ret["_error"] = "Minion is not running an Esky build"
        return ret
    if not __salt__["config.option"]("update_url"):
        ret["_error"] = '"update_url" not configured on this minion'
        return ret
    app = esky.Esky(sys.executable, __opts__["update_url"])
    oldversion = __grains__["saltversion"]
    if not version:
        try:
            version = app.find_update()
        except urllib.error.URLError as exc:
            ret["_error"] = "Could not connect to update_url. Error: {}".format(exc)
            return ret
    if not version:
        ret["_error"] = "No updates available"
        return ret
    try:
        app.fetch_version(version)
    except EskyVersionError as exc:
        ret["_error"] = "Unable to fetch version {}. Error: {}".format(version, exc)
        return ret
    try:
        app.install_version(version)
    except EskyVersionError as exc:
        ret["_error"] = "Unable to install version {}. Error: {}".format(version, exc)
        return ret
    try:
        app.cleanup()
    except Exception as exc:  # pylint: disable=broad-except
        ret["_error"] = "Unable to cleanup. Error: {}".format(exc)
    restarted = {}
    for service in __opts__["update_restart_services"]:
        restarted[service] = __salt__["service.restart"](service)
    ret["comment"] = "Updated from {} to {}".format(oldversion, version)
    ret["restarted"] = restarted
    return ret


def sync_beacons(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2015.5.1

    Sync beacons from ``salt://_beacons`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for beacons to sync. If no top files are
        found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available beacons on the minion. This refresh
        will be performed even if no new beacons are synced. Set to ``False``
        to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_beacons
        salt '*' saltutil.sync_beacons saltenv=dev
        salt '*' saltutil.sync_beacons saltenv=base,dev
    """
    ret = _sync("beacons", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_beacons()
    return ret


def sync_sdb(saltenv=None, extmod_whitelist=None, extmod_blacklist=None):
    """
    .. versionadded:: 2015.5.8,2015.8.3

    Sync sdb modules from ``salt://_sdb`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for sdb modules to sync. If no top files
        are found, then the ``base`` environment will be synced.

    refresh : False
        This argument has no affect and is included for consistency with the
        other sync functions.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_sdb
        salt '*' saltutil.sync_sdb saltenv=dev
        salt '*' saltutil.sync_sdb saltenv=base,dev
    """
    ret = _sync("sdb", saltenv, extmod_whitelist, extmod_blacklist)
    return ret


def sync_modules(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 0.10.0

    Sync execution modules from ``salt://_modules`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for execution modules to sync. If no top
        files are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new execution modules are
        synced. Set to ``False`` to prevent this refresh.

    .. important::

        If this function is executed using a :py:func:`module.run
        <salt.states.module.run>` state, the SLS file will not have access to
        newly synced execution modules unless a ``refresh`` argument is
        added to the state, like so:

        .. code-block:: yaml

            load_my_custom_module:
              module.run:
                - name: saltutil.sync_modules
                - refresh: True

        See :ref:`here <reloading-modules>` for a more detailed explanation of
        why this is necessary.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_modules
        salt '*' saltutil.sync_modules saltenv=dev
        salt '*' saltutil.sync_modules saltenv=base,dev
    """
    ret = _sync("modules", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_states(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 0.10.0

    Sync state modules from ``salt://_states`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for state modules to sync. If no top
        files are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available states on the minion. This refresh
        will be performed even if no new state modules are synced. Set to
        ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_states
        salt '*' saltutil.sync_states saltenv=dev
        salt '*' saltutil.sync_states saltenv=base,dev
    """
    ret = _sync("states", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def refresh_grains(**kwargs):
    """
    .. versionadded:: 2016.3.6,2016.11.4,2017.7.0

    Refresh the minion's grains without syncing custom grains modules from
    ``salt://_grains``.

    .. note::
        The available execution modules will be reloaded as part of this
        proceess, as grains can affect which modules are available.

    refresh_pillar : True
        Set to ``False`` to keep pillar data from being refreshed.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.refresh_grains
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    _refresh_pillar = kwargs.pop("refresh_pillar", True)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)
    # Modules and pillar need to be refreshed in case grains changes affected
    # them, and the module refresh process reloads the grains and assigns the
    # newly-reloaded grains to each execution module's __grains__ dunder.
    if _refresh_pillar:
        # we don't need to call refresh_modules here because it's done by refresh_pillar
        refresh_pillar()
    else:
        refresh_modules()
    return True


def sync_grains(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 0.10.0

    Sync grains modules from ``salt://_grains`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for grains modules to sync. If no top
        files are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules and recompile
        pillar data for the minion. This refresh will be performed even if no
        new grains modules are synced. Set to ``False`` to prevent this
        refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_grains
        salt '*' saltutil.sync_grains saltenv=dev
        salt '*' saltutil.sync_grains saltenv=base,dev
    """
    ret = _sync("grains", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        # we don't need to call refresh_modules here because it's done by refresh_pillar
        refresh_pillar()
    return ret


def sync_renderers(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 0.10.0

    Sync renderers from ``salt://_renderers`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for renderers to sync. If no top files
        are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new renderers are synced.
        Set to ``False`` to prevent this refresh. Set to ``False`` to prevent
        this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_renderers
        salt '*' saltutil.sync_renderers saltenv=dev
        salt '*' saltutil.sync_renderers saltenv=base,dev
    """
    ret = _sync("renderers", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_returners(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 0.10.0

    Sync returners from ``salt://_returners`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for returners to sync. If no top files
        are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new returners are synced. Set
        to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_returners
        salt '*' saltutil.sync_returners saltenv=dev
    """
    ret = _sync("returners", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_proxymodules(
    saltenv=None, refresh=False, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2015.8.2

    Sync proxy modules from ``salt://_proxy`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for proxy modules to sync. If no top
        files are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new proxy modules are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_proxymodules
        salt '*' saltutil.sync_proxymodules saltenv=dev
        salt '*' saltutil.sync_proxymodules saltenv=base,dev
    """
    ret = _sync("proxy", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_matchers(
    saltenv=None, refresh=False, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2019.2.0

    Sync engine modules from ``salt://_matchers`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for engines to sync. If no top files are
        found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new matcher modules are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_matchers
        salt '*' saltutil.sync_matchers saltenv=base,dev
    """
    ret = _sync("matchers", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_engines(
    saltenv=None, refresh=False, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2016.3.0

    Sync engine modules from ``salt://_engines`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for engines to sync. If no top files are
        found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new engine modules are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_engines
        salt '*' saltutil.sync_engines saltenv=base,dev
    """
    ret = _sync("engines", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_thorium(
    saltenv=None, refresh=False, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2018.3.0

    Sync Thorium modules from ``salt://_thorium`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for engines to sync. If no top files are
        found, then the ``base`` environment will be synced.

    refresh: ``True``
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new Thorium modules are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist
        comma-separated list of modules to sync

    extmod_blacklist
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_thorium
        salt '*' saltutil.sync_thorium saltenv=base,dev
    """
    ret = _sync("thorium", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_output(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    Sync outputters from ``salt://_output`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for outputters to sync. If no top files
        are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new outputters are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_output
        salt '*' saltutil.sync_output saltenv=dev
        salt '*' saltutil.sync_output saltenv=base,dev
    """
    ret = _sync("output", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


sync_outputters = salt.utils.functools.alias_function(sync_output, "sync_outputters")


def sync_clouds(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2017.7.0

    Sync cloud modules from ``salt://_cloud`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new utility modules are
        synced. Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_clouds
        salt '*' saltutil.sync_clouds saltenv=dev
        salt '*' saltutil.sync_clouds saltenv=base,dev
    """
    ret = _sync("clouds", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_utils(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2014.7.0

    Sync utility modules from ``salt://_utils`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for utility modules to sync. If no top
        files are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new utility modules are
        synced. Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_utils
        salt '*' saltutil.sync_utils saltenv=dev
        salt '*' saltutil.sync_utils saltenv=base,dev
    """
    ret = _sync("utils", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_serializers(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2019.2.0

    Sync serializers from ``salt://_serializers`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for serializer modules to sync. If no top
        files are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new serializer modules are
        synced. Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_serializers
        salt '*' saltutil.sync_serializers saltenv=dev
        salt '*' saltutil.sync_serializers saltenv=base,dev
    """
    ret = _sync("serializers", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def list_extmods():
    """
    .. versionadded:: 2017.7.0

    List Salt modules which have been synced externally

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.list_extmods
    """
    ret = {}
    ext_dir = os.path.join(__opts__["cachedir"], "extmods")
    mod_types = os.listdir(ext_dir)
    for mod_type in mod_types:
        ret[mod_type] = set()
        for _, _, files in salt.utils.path.os_walk(os.path.join(ext_dir, mod_type)):
            for fh_ in files:
                ret[mod_type].add(fh_.split(".")[0])
        ret[mod_type] = list(ret[mod_type])
    return ret


def sync_log_handlers(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2015.8.0

    Sync log handlers from ``salt://_log_handlers`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for log handlers to sync. If no top files
        are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new log handlers are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_log_handlers
        salt '*' saltutil.sync_log_handlers saltenv=dev
        salt '*' saltutil.sync_log_handlers saltenv=base,dev
    """
    ret = _sync("log_handlers", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_pillar(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 2015.8.11,2016.3.2

    Sync pillar modules from the ``salt://_pillar`` directory on the Salt
    fileserver. This function is environment-aware, pass the desired
    environment to grab the contents of the ``_pillar`` directory from that
    environment. The default environment, if none is specified,  is ``base``.

    refresh : True
        Also refresh the execution modules available to the minion, and refresh
        pillar data.

    extmod_whitelist : None
        comma-separated list of modules to sync

    extmod_blacklist : None
        comma-separated list of modules to blacklist based on type

    .. note::
        This function will raise an error if executed on a traditional (i.e.
        not masterless) minion

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_pillar
        salt '*' saltutil.sync_pillar saltenv=dev
    """
    if __opts__["file_client"] != "local":
        raise CommandExecutionError(
            "Pillar modules can only be synced to masterless minions"
        )
    ret = _sync("pillar", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        # we don't need to call refresh_modules here because it's done by refresh_pillar
        refresh_pillar()
    return ret


def sync_executors(
    saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None
):
    """
    .. versionadded:: 3000

    Sync executors from ``salt://_executors`` to the minion

    saltenv
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

        If not passed, then all environments configured in the :ref:`top files
        <states-top>` will be checked for log handlers to sync. If no top files
        are found, then the ``base`` environment will be synced.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new log handlers are synced.
        Set to ``False`` to prevent this refresh.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_executors
        salt '*' saltutil.sync_executors saltenv=dev
        salt '*' saltutil.sync_executors saltenv=base,dev
    """
    ret = _sync("executors", saltenv, extmod_whitelist, extmod_blacklist)
    if refresh:
        refresh_modules()
    return ret


def sync_all(saltenv=None, refresh=True, extmod_whitelist=None, extmod_blacklist=None):
    """
    .. versionchanged:: 2015.8.11,2016.3.2
        On masterless minions, pillar modules are now synced, and refreshed
        when ``refresh`` is set to ``True``.

    Sync down all of the dynamic modules from the file server for a specific
    environment. This function synchronizes custom modules, states, beacons,
    grains, returners, output modules, renderers, and utils.

    refresh : True
        Also refresh the execution modules and recompile pillar data available
        to the minion. This refresh will be performed even if no new dynamic
        modules are synced. Set to ``False`` to prevent this refresh.

    .. important::

        If this function is executed using a :py:func:`module.run
        <salt.states.module.run>` state, the SLS file will not have access to
        newly synced execution modules unless a ``refresh`` argument is
        added to the state, like so:

        .. code-block:: yaml

            load_my_custom_module:
              module.run:
                - name: saltutil.sync_all
                - refresh: True

        See :ref:`here <reloading-modules>` for a more detailed explanation of
        why this is necessary.

    extmod_whitelist : None
        dictionary of modules to sync based on type

    extmod_blacklist : None
        dictionary of modules to blacklist based on type

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_all
        salt '*' saltutil.sync_all saltenv=dev
        salt '*' saltutil.sync_all saltenv=base,dev
        salt '*' saltutil.sync_all extmod_whitelist={'modules': ['custom_module']}
    """
    log.debug("Syncing all")
    ret = {}
    ret["clouds"] = sync_clouds(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["beacons"] = sync_beacons(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["modules"] = sync_modules(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["states"] = sync_states(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["sdb"] = sync_sdb(saltenv, extmod_whitelist, extmod_blacklist)
    ret["grains"] = sync_grains(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["renderers"] = sync_renderers(
        saltenv, False, extmod_whitelist, extmod_blacklist
    )
    ret["returners"] = sync_returners(
        saltenv, False, extmod_whitelist, extmod_blacklist
    )
    ret["output"] = sync_output(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["utils"] = sync_utils(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["log_handlers"] = sync_log_handlers(
        saltenv, False, extmod_whitelist, extmod_blacklist
    )
    ret["executors"] = sync_executors(
        saltenv, False, extmod_whitelist, extmod_blacklist
    )
    ret["proxymodules"] = sync_proxymodules(
        saltenv, False, extmod_whitelist, extmod_blacklist
    )
    ret["engines"] = sync_engines(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["thorium"] = sync_thorium(saltenv, False, extmod_whitelist, extmod_blacklist)
    ret["serializers"] = sync_serializers(
        saltenv, False, extmod_whitelist, extmod_blacklist
    )
    ret["matchers"] = sync_matchers(saltenv, False, extmod_whitelist, extmod_blacklist)
    if __opts__["file_client"] == "local":
        ret["pillar"] = sync_pillar(saltenv, False, extmod_whitelist, extmod_blacklist)
    if refresh:
        # we don't need to call refresh_modules here because it's done by refresh_pillar
        refresh_pillar()
    return ret


def refresh_beacons():
    """
    Signal the minion to refresh the beacons.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_beacons
    """
    try:
        ret = __salt__["event.fire"]({}, "beacons_refresh")
    except KeyError:
        log.error("Event module not available. Module refresh failed.")
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret


def refresh_matchers():
    """
    Signal the minion to refresh its matchers.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_matchers
    """
    try:
        ret = __salt__["event.fire"]({}, "matchers_refresh")
    except KeyError:
        log.error("Event module not available. Matcher refresh failed.")
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret


def refresh_pillar(wait=False, timeout=30, clean_cache=True):
    """
    Signal the minion to refresh the in-memory pillar data. See :ref:`pillar-in-memory`.

    :param wait:            Wait for pillar refresh to complete, defaults to False.
    :type wait:             bool, optional
    :param timeout:         How long to wait in seconds, only used when wait is True, defaults to 30.
    :type timeout:          int, optional
    :param clean_cache:     Clean the pillar cache, only used when `pillar_cache` is True. Defaults to True
    :type clean_cache:      bool, optional
        .. versionadded:: 3005
    :return:                Boolean status, True when the pillar_refresh event was fired successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_pillar
        salt '*' saltutil.refresh_pillar wait=True timeout=60
    """
    data = {"clean_cache": clean_cache}
    try:
        if wait:
            #  If we're going to block, first setup a listener
            with salt.utils.event.get_event(
                "minion", opts=__opts__, listen=True
            ) as eventer:
                ret = __salt__["event.fire"](data, "pillar_refresh")
                # Wait for the finish event to fire
                log.trace("refresh_pillar waiting for pillar refresh to complete")
                # Blocks until we hear this event or until the timeout expires
                event_ret = eventer.get_event(
                    tag=salt.defaults.events.MINION_PILLAR_REFRESH_COMPLETE,
                    wait=timeout,
                )
                if not event_ret or event_ret["complete"] is False:
                    log.warning(
                        "Pillar refresh did not complete within timeout %s", timeout
                    )
        else:
            ret = __salt__["event.fire"](data, "pillar_refresh")
    except KeyError:
        log.error("Event module not available. Pillar refresh failed.")
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret


pillar_refresh = salt.utils.functools.alias_function(refresh_pillar, "pillar_refresh")


def refresh_modules(**kwargs):
    """
    Signal the minion to refresh the module and grain data

    The default is to refresh module asynchronously. To block
    until the module refresh is complete, set the 'async' flag
    to False.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_modules
    """
    asynchronous = bool(kwargs.get("async", True))
    try:
        if asynchronous:
            ret = __salt__["event.fire"]({}, "module_refresh")
        else:
            #  If we're going to block, first setup a listener
            with salt.utils.event.get_event(
                "minion", opts=__opts__, listen=True
            ) as eventer:
                ret = __salt__["event.fire"]({"notify": True}, "module_refresh")
                # Wait for the finish event to fire
                log.trace("refresh_modules waiting for module refresh to complete")
                # Blocks until we hear this event or until the timeout expires
                eventer.get_event(
                    tag=salt.defaults.events.MINION_MOD_REFRESH_COMPLETE, wait=30
                )
    except KeyError:
        log.error("Event module not available. Module refresh failed.")
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret


def is_running(fun):
    """
    If the named function is running return the data associated with it/them.
    The argument can be a glob

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.is_running state.highstate
    """
    run = running()
    ret = []
    for data in run:
        if fnmatch.fnmatch(data.get("fun", ""), fun):
            ret.append(data)
    return ret


def running():
    """
    Return the data on all running salt processes on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.running
    """
    return salt.utils.minion.running(__opts__)


def clear_cache():
    """
    Forcibly removes all caches on a minion.

    .. versionadded:: 2014.7.0

    WARNING: The safest way to clear a minion cache is by first stopping
    the minion and then deleting the cache files before restarting it.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.clear_cache
    """
    for root, dirs, files in salt.utils.files.safe_walk(
        __opts__["cachedir"], followlinks=False
    ):
        for name in files:
            try:
                os.remove(os.path.join(root, name))
            except OSError as exc:
                log.error(
                    "Attempt to clear cache with saltutil.clear_cache FAILED with: %s",
                    exc,
                )
                return False
    return True


def clear_job_cache(hours=24):
    """
    Forcibly removes job cache folders and files on a minion.

    .. versionadded:: 2018.3.0

    WARNING: The safest way to clear a minion cache is by first stopping
    the minion and then deleting the cache files before restarting it.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.clear_job_cache hours=12
    """
    threshold = time.time() - hours * 3600
    for root, dirs, files in salt.utils.files.safe_walk(
        os.path.join(__opts__["cachedir"], "minion_jobs"), followlinks=False
    ):
        for name in dirs:
            try:
                directory = os.path.join(root, name)
                mtime = os.path.getmtime(directory)
                if mtime < threshold:
                    shutil.rmtree(directory)
            except OSError as exc:
                log.error(
                    "Attempt to clear cache with saltutil.clear_job_cache FAILED"
                    " with: %s",
                    exc,
                )
                return False
    return True


def find_job(jid):
    """
    Return the data for a specific job id that is currently running.

    jid
        The job id to search for and return data.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.find_job <job id>

    Note that the find_job function only returns job information when the job is still running. If
    the job is currently running, the output looks something like this:

    .. code-block:: bash

        # salt my-minion saltutil.find_job 20160503150049487736
        my-minion:
            ----------
            arg:
                - 30
            fun:
                test.sleep
            jid:
                20160503150049487736
            pid:
                9601
            ret:
            tgt:
                my-minion
            tgt_type:
                glob
            user:
                root

    If the job has already completed, the job cannot be found and therefore the function returns
    an empty dictionary, which looks like this on the CLI:

    .. code-block:: bash

        # salt my-minion saltutil.find_job 20160503150049487736
        my-minion:
            ----------
    """
    for data in running():
        if data["jid"] == jid:
            return data
    return {}


def find_cached_job(jid):
    """
    Return the data for a specific cached job id. Note this only works if
    cache_jobs has previously been set to True on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.find_cached_job <job id>
    """
    proc_dir = os.path.join(__opts__["cachedir"], "minion_jobs")
    job_dir = os.path.join(proc_dir, str(jid))
    if not os.path.isdir(job_dir):
        if not __opts__.get("cache_jobs"):
            return (
                "Local jobs cache directory not found; you may need to"
                " enable cache_jobs on this minion"
            )
        else:
            return "Local jobs cache directory {} not found".format(job_dir)
    path = os.path.join(job_dir, "return.p")
    with salt.utils.files.fopen(path, "rb") as fp_:
        buf = fp_.read()
    if buf:
        try:
            data = salt.payload.loads(buf)
        except NameError:
            # msgpack error in salt-ssh
            pass
        else:
            if isinstance(data, dict):
                # if not a dict, this was an invalid serialized object
                return data
    return None


def signal_job(jid, sig):
    """
    Sends a signal to the named salt job's process

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.signal_job <job id> 15
    """
    if HAS_PSUTIL is False:
        log.warning(
            "saltutil.signal job called, but psutil is not installed. "
            "Install psutil to ensure more reliable and accurate PID "
            "management."
        )
    for data in running():
        if data["jid"] == jid:
            try:
                if HAS_PSUTIL:
                    for proc in salt.utils.psutil_compat.Process(
                        pid=data["pid"]
                    ).children(recursive=True):
                        proc.send_signal(sig)
                os.kill(int(data["pid"]), sig)
                if HAS_PSUTIL is False and "child_pids" in data:
                    for pid in data["child_pids"]:
                        os.kill(int(pid), sig)
                return "Signal {} sent to job {} at pid {}".format(
                    int(sig), jid, data["pid"]
                )
            except OSError:
                path = os.path.join(__opts__["cachedir"], "proc", str(jid))
                if os.path.isfile(path):
                    os.remove(path)
                return "Job {} was not running and job data has been cleaned up".format(
                    jid
                )
    return ""


def term_job(jid):
    """
    Sends a termination signal (SIGTERM 15) to the named salt job's process

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.term_job <job id>
    """
    return signal_job(jid, signal.SIGTERM)


def term_all_jobs():
    """
    Sends a termination signal (SIGTERM 15) to all currently running jobs

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.term_all_jobs
    """
    ret = []
    for data in running():
        ret.append(signal_job(data["jid"], signal.SIGTERM))
    return ret


def kill_job(jid):
    """
    Sends a kill signal (SIGKILL 9) to the named salt job's process

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.kill_job <job id>
    """
    # Some OS's (Win32) don't have SIGKILL, so use salt_SIGKILL which is set to
    # an appropriate value for the operating system this is running on.
    return signal_job(jid, salt_SIGKILL)


def kill_all_jobs():
    """
    Sends a kill signal (SIGKILL 9) to all currently running jobs

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.kill_all_jobs
    """
    # Some OS's (Win32) don't have SIGKILL, so use salt_SIGKILL which is set to
    # an appropriate value for the operating system this is running on.
    ret = []
    for data in running():
        ret.append(signal_job(data["jid"], salt_SIGKILL))
    return ret


def regen_keys():
    """
    Used to regenerate the minion keys.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.regen_keys
    """
    for fn_ in os.listdir(__opts__["pki_dir"]):
        path = os.path.join(__opts__["pki_dir"], fn_)
        try:
            os.remove(path)
        except os.error:
            pass
    # TODO: move this into a channel function? Or auth?
    # create a channel again, this will force the key regen
    with salt.channel.client.ReqChannel.factory(__opts__) as channel:
        log.debug("Recreating channel to force key regen")


def revoke_auth(preserve_minion_cache=False):
    """
    The minion sends a request to the master to revoke its own key.
    Note that the minion session will be revoked and the minion may
    not be able to return the result of this command back to the master.

    If the 'preserve_minion_cache' flag is set to True, the master
    cache for this minion will not be removed.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.revoke_auth
    """
    masters = list()
    ret = True
    if "master_uri_list" in __opts__:
        for master_uri in __opts__["master_uri_list"]:
            masters.append(master_uri)
    else:
        masters.append(__opts__["master_uri"])

    for master in masters:
        with salt.channel.client.ReqChannel.factory(
            __opts__, master_uri=master
        ) as channel:
            tok = channel.auth.gen_token(b"salt")
            load = {
                "cmd": "revoke_auth",
                "id": __opts__["id"],
                "tok": tok,
                "preserve_minion_cache": preserve_minion_cache,
            }
            try:
                channel.send(load)
            except SaltReqTimeoutError:
                ret = False
    return ret


def _get_ssh_or_api_client(cfgfile, ssh=False):
    if ssh:
        client = salt.client.ssh.client.SSHClient(cfgfile)
    else:
        client = salt.client.get_local_client(cfgfile)
    return client


def _exec(
    client,
    tgt,
    fun,
    arg,
    timeout,
    tgt_type,
    ret,
    kwarg,
    batch=False,
    subset=False,
    **kwargs
):
    fcn_ret = {}
    seen = 0

    cmd_kwargs = {
        "tgt": tgt,
        "fun": fun,
        "arg": arg,
        "timeout": timeout,
        "tgt_type": tgt_type,
        "ret": ret,
        "kwarg": kwarg,
    }

    if batch:
        _cmd = client.cmd_batch
        cmd_kwargs.update({"batch": batch})
    elif subset:
        _cmd = client.cmd_subset
        cmd_kwargs.update({"subset": subset, "cli": True})
    else:
        _cmd = client.cmd_iter

    cmd_kwargs.update(kwargs)
    for ret_comp in _cmd(**cmd_kwargs):
        fcn_ret.update(ret_comp)
        seen += 1
        # fcn_ret can be empty, so we cannot len the whole return dict
        if tgt_type == "list" and len(tgt) == seen:
            # do not wait for timeout when explicit list matching
            # and all results are there
            break

    if batch:
        old_ret, fcn_ret = fcn_ret, {}
        for key, value in old_ret.items():
            fcn_ret[key] = {
                "out": value.get("out", "highstate")
                if isinstance(value, dict)
                else "highstate",
                "ret": value,
            }

    return fcn_ret


def cmd(
    tgt,
    fun,
    arg=(),
    timeout=None,
    tgt_type="glob",
    ret="",
    kwarg=None,
    ssh=False,
    **kwargs
):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Assuming this minion is a master, execute a salt command

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.cmd
    """
    cfgfile = __opts__["conf_file"]
    with _get_ssh_or_api_client(cfgfile, ssh) as client:
        fcn_ret = _exec(client, tgt, fun, arg, timeout, tgt_type, ret, kwarg, **kwargs)
    # if return is empty, we may have not used the right conf,
    # try with the 'minion relative master configuration counter part
    # if available
    master_cfgfile = "{}master".format(cfgfile[:-6])  # remove 'minion'
    if (
        not fcn_ret
        and cfgfile.endswith("{}{}".format(os.path.sep, "minion"))
        and os.path.exists(master_cfgfile)
    ):
        with _get_ssh_or_api_client(master_cfgfile, ssh) as client:
            fcn_ret = _exec(
                client, tgt, fun, arg, timeout, tgt_type, ret, kwarg, **kwargs
            )

    return fcn_ret


def cmd_iter(
    tgt,
    fun,
    arg=(),
    timeout=None,
    tgt_type="glob",
    ret="",
    kwarg=None,
    ssh=False,
    **kwargs
):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Assuming this minion is a master, execute a salt command

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.cmd_iter
    """
    if ssh:
        client = salt.client.ssh.client.SSHClient(__opts__["conf_file"])
    else:
        client = salt.client.get_local_client(__opts__["conf_file"])
    for ret in client.cmd_iter(tgt, fun, arg, timeout, tgt_type, ret, kwarg, **kwargs):
        yield ret


def runner(
    name, arg=None, kwarg=None, full_return=False, saltenv="base", jid=None, **kwargs
):
    """
    Execute a runner function. This function must be run on the master,
    either by targeting a minion running on a master or by using
    salt-call on a master.

    .. versionadded:: 2014.7.0

    name
        The name of the function to run

    kwargs
        Any keyword arguments to pass to the runner function

    CLI Example:

    In this example, assume that `master_minion` is a minion running
    on a master.

    .. code-block:: bash

        salt master_minion saltutil.runner jobs.list_jobs
        salt master_minion saltutil.runner test.arg arg="['baz']" kwarg="{'foo': 'bar'}"
    """
    if arg is None:
        arg = []
    if kwarg is None:
        kwarg = {}
    jid = kwargs.pop("__orchestration_jid__", jid)
    saltenv = kwargs.pop("__env__", saltenv)
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    if kwargs:
        kwarg.update(kwargs)

    if "master_job_cache" not in __opts__:
        master_config = os.path.join(os.path.dirname(__opts__["conf_file"]), "master")
        master_opts = salt.config.master_config(master_config)
        rclient = salt.runner.RunnerClient(master_opts)
    else:
        rclient = salt.runner.RunnerClient(__opts__)

    if name in rclient.functions:
        aspec = salt.utils.args.get_function_argspec(rclient.functions[name])
        if "saltenv" in aspec.args:
            kwarg["saltenv"] = saltenv

    if name in ["state.orchestrate", "state.orch", "state.sls"]:
        kwarg["orchestration_jid"] = jid

    if jid:
        salt.utils.event.fire_args(
            __opts__,
            jid,
            {"type": "runner", "name": name, "args": arg, "kwargs": kwarg},
            prefix="run",
        )

    return rclient.cmd(
        name, arg=arg, kwarg=kwarg, print_event=False, full_return=full_return
    )


def wheel(name, *args, **kwargs):
    """
    Execute a wheel module and function. This function must be run against a
    minion that is local to the master.

    .. versionadded:: 2014.7.0

    name
        The name of the function to run

    args
        Any positional arguments to pass to the wheel function. A common example
        of this would be the ``match`` arg needed for key functions.

        .. versionadded:: 2015.8.11

    kwargs
        Any keyword arguments to pass to the wheel function

    CLI Example:

    .. code-block:: bash

        salt my-local-minion saltutil.wheel key.accept jerry
        salt my-local-minion saltutil.wheel minions.connected

    .. note::

        Since this function must be run against a minion that is running locally
        on the master in order to get accurate returns, if this function is run
        against minions that are not local to the master, "empty" returns are
        expected. The remote minion does not have access to wheel functions and
        their return data.

    """
    jid = kwargs.pop("__orchestration_jid__", None)
    saltenv = kwargs.pop("__env__", "base")

    if __opts__["__role"] == "minion":
        master_config = os.path.join(os.path.dirname(__opts__["conf_file"]), "master")
        master_opts = salt.config.client_config(master_config)
        wheel_client = salt.wheel.WheelClient(master_opts)
    else:
        wheel_client = salt.wheel.WheelClient(__opts__)

    # The WheelClient cmd needs args, kwargs, and pub_data separated out from
    # the "normal" kwargs structure, which at this point contains __pub_x keys.
    pub_data = {}
    valid_kwargs = {}
    for key, val in kwargs.items():
        if key.startswith("__"):
            pub_data[key] = val
        else:
            valid_kwargs[key] = val

    try:
        if name in wheel_client.functions:
            aspec = salt.utils.args.get_function_argspec(wheel_client.functions[name])
            if "saltenv" in aspec.args:
                valid_kwargs["saltenv"] = saltenv

        if jid:
            salt.utils.event.fire_args(
                __opts__,
                jid,
                {"type": "wheel", "name": name, "args": valid_kwargs},
                prefix="run",
            )

        ret = wheel_client.cmd(
            name,
            arg=args,
            pub_data=pub_data,
            kwarg=valid_kwargs,
            print_event=False,
            full_return=True,
        )
    except SaltInvocationError:
        raise CommandExecutionError(
            "This command can only be executed on a minion that is located on "
            "the master."
        )

    return ret


# this is the only way I could figure out how to get the REAL file_roots
# __opt__['file_roots'] is set to  __opt__['pillar_root']
class _MMinion:
    def __new__(cls, saltenv, reload_env=False):
        # this is to break out of salt.loaded.int and make this a true singleton
        # hack until https://github.com/saltstack/salt/pull/10273 is resolved
        # this is starting to look like PHP
        global _mminions  # pylint: disable=W0601
        if "_mminions" not in globals():
            _mminions = {}
        if saltenv not in _mminions or reload_env:
            opts = copy.deepcopy(__opts__)
            del opts["file_roots"]
            # grains at this point are in the context of the minion
            global __grains__  # pylint: disable=W0601
            grains = copy.deepcopy(__grains__)
            m = salt.minion.MasterMinion(opts)

            # this assignment is so that the rest of fxns called by salt still
            # have minion context
            __grains__ = grains

            # this assignment is so that fxns called by mminion have minion
            # context
            m.opts["grains"] = grains

            env_roots = m.opts["file_roots"][saltenv]
            m.opts["module_dirs"] = [fp + "/_modules" for fp in env_roots]
            m.gen_modules()
            _mminions[saltenv] = m
        return _mminions[saltenv]


def mmodule(saltenv, fun, *args, **kwargs):
    """
    Loads minion modules from an environment so that they can be used in pillars
    for that environment

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.mmodule base test.ping
    """
    mminion = _MMinion(saltenv)
    return mminion.functions[fun](*args, **kwargs)

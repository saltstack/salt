# -*- coding: utf-8 -*-
#
# Copyright 2015 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module for full system inspection.
"""
from __future__ import absolute_import, print_function, unicode_literals

import getpass
import logging
import os

import salt.utils.fsutils
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from salt.exceptions import get_error_message as _get_error_message

# Import Salt libs
from salt.ext import six
from salt.modules.inspectlib.exceptions import (
    InspectorKiwiProcessorException,
    InspectorQueryException,
    InspectorSnapshotException,
)

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    return not salt.utils.platform.is_windows() and "inspector"


def _(module):
    """
    Get inspectlib module for the lazy loader.

    :param module:
    :return:
    """

    mod = None
    # pylint: disable=E0598
    try:
        # importlib is in Python 2.7+ and 3+
        import importlib

        mod = importlib.import_module("salt.modules.inspectlib.{0}".format(module))
    except ImportError:
        # No importlib around (2.6)
        mod = getattr(
            __import__(
                "salt.modules.inspectlib",
                globals(),
                locals(),
                fromlist=[six.text_type(module)],
            ),
            module,
        )
    # pylint: enable=E0598

    mod.__grains__ = __grains__
    mod.__pillar__ = __pillar__
    mod.__salt__ = __salt__

    return mod


def inspect(mode="all", priority=19, **kwargs):
    """
    Start node inspection and save the data to the database for further query.

    Parameters:

    * **mode**: Clarify inspection mode: configuration, payload, all (default)

      payload
        * **filter**: Comma-separated directories to track payload.

    * **priority**: (advanced) Set priority of the inspection. Default is low priority.



    CLI Example:

    .. code-block:: bash

        salt '*' inspector.inspect
        salt '*' inspector.inspect configuration
        salt '*' inspector.inspect payload filter=/opt,/ext/oracle
    """
    collector = _("collector")
    try:
        return collector.Inspector(
            cachedir=__opts__["cachedir"], piddir=os.path.dirname(__opts__["pidfile"])
        ).request_snapshot(mode, priority=priority, **kwargs)
    except InspectorSnapshotException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:  # pylint: disable=broad-except
        log.error(_get_error_message(ex))
        raise Exception(ex)


def query(*args, **kwargs):
    """
    Query the node for specific information.

    Parameters:

    * **scope**: Specify scope of the query.

       * **System**: Return system data.

       * **Software**: Return software information.

       * **Services**: Return known services.

       * **Identity**: Return user accounts information for this system.
          accounts
            Can be either 'local', 'remote' or 'all' (equal to "local,remote").
            Remote accounts cannot be resolved on all systems, but only
            those, which supports 'passwd -S -a'.

          disabled
            True (or False, default) to return only disabled accounts.

       * **payload**: Payload scope parameters:
          filter
            Include only results which path starts from the filter string.

          time
            Display time in Unix ticks or format according to the configured TZ (default)
            Values: ticks, tz (default)

          size
            Format size. Values: B, KB, MB, GB

          type
            Include payload type.
            Values (comma-separated): directory (or dir), link, file (default)
            Example (returns everything): type=directory,link,file

          owners
            Resolve UID/GID to an actual names or leave them numeric (default).
            Values: name (default), id

          brief
            Return just a list of payload elements, if True. Default: False.

       * **all**: Return all information (default).

    CLI Example:

    .. code-block:: bash

        salt '*' inspector.query scope=system
        salt '*' inspector.query scope=payload type=file,link filter=/etc size=Kb brief=False
    """
    query = _("query")
    try:
        return query.Query(kwargs.get("scope"), cachedir=__opts__["cachedir"])(
            *args, **kwargs
        )
    except InspectorQueryException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:  # pylint: disable=broad-except
        log.error(_get_error_message(ex))
        raise Exception(ex)


def build(format="qcow2", path="/tmp/"):
    """
    Build an image from a current system description.
    The image is a system image can be output in bootable ISO or QCOW2 formats.

    Node uses the image building library Kiwi to perform the actual build.

    Parameters:

    * **format**: Specifies output format: "qcow2" or "iso. Default: `qcow2`.
    * **path**: Specifies output path where to store built image. Default: `/tmp`.

    CLI Example:

    .. code-block:: bash

        salt myminion inspector.build
        salt myminion inspector.build format=iso path=/opt/builds/
    """
    try:
        _("collector").Inspector(
            cachedir=__opts__["cachedir"],
            piddir=os.path.dirname(__opts__["pidfile"]),
            pidfilename="",
        ).reuse_snapshot().build(format=format, path=path)
    except InspectorKiwiProcessorException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:  # pylint: disable=broad-except
        log.error(_get_error_message(ex))
        raise Exception(ex)


def export(local=False, path="/tmp", format="qcow2"):
    """
    Export an image description for Kiwi.

    Parameters:

    * **local**: Specifies True or False if the export has to be in the local file. Default: False.
    * **path**: If `local=True`, then specifies the path where file with the Kiwi description is written.
                Default: `/tmp`.

    CLI Example:

    .. code-block:: bash

        salt myminion inspector.export
        salt myminion inspector.export format=iso path=/opt/builds/
    """
    if getpass.getuser() != "root":
        raise CommandExecutionError(
            'In order to export system, the minion should run as "root".'
        )
    try:
        description = _("query").Query("all", cachedir=__opts__["cachedir"])()
        return (
            _("collector")
            .Inspector()
            .reuse_snapshot()
            .export(description, local=local, path=path, format=format)
        )
    except InspectorKiwiProcessorException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:  # pylint: disable=broad-except
        log.error(_get_error_message(ex))
        raise Exception(ex)


def snapshots():
    """
    List current description snapshots.

    CLI Example:

    .. code-block:: bash

        salt myminion inspector.snapshots
    """
    try:
        return (
            _("collector")
            .Inspector(
                cachedir=__opts__["cachedir"],
                piddir=os.path.dirname(__opts__["pidfile"]),
            )
            .db.list()
        )
    except InspectorSnapshotException as err:
        raise CommandExecutionError(err)
    except Exception as err:  # pylint: disable=broad-except
        log.error(_get_error_message(err))
        raise Exception(err)


def delete(all=False, *databases):
    """
    Remove description snapshots from the system.

    ::parameter: all. Default: False. Remove all snapshots, if set to True.

    CLI example:

    .. code-block:: bash

        salt myminion inspector.delete <ID> <ID1> <ID2>..
        salt myminion inspector.delete all=True
    """
    if not all and not databases:
        raise CommandExecutionError("At least one database ID required.")

    try:
        ret = dict()
        inspector = _("collector").Inspector(
            cachedir=__opts__["cachedir"], piddir=os.path.dirname(__opts__["pidfile"])
        )
        for dbid in all and inspector.db.list() or databases:
            ret[dbid] = inspector.db._db.purge(six.text_type(dbid))
        return ret
    except InspectorSnapshotException as err:
        raise CommandExecutionError(err)
    except Exception as err:  # pylint: disable=broad-except
        log.error(_get_error_message(err))
        raise Exception(err)

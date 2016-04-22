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

'''
Module for full system inspection.
'''
from __future__ import absolute_import
import logging
from salt.modules.inspectlib.exceptions import (InspectorQueryException,
                                                InspectorSnapshotException)

# Import Salt libs
import salt.utils
import salt.utils.fsutils
from salt.exceptions import CommandExecutionError
from salt.exceptions import get_error_message as _get_error_message

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.is_windows()


def _(module):
    '''
    Get inspectlib module for the lazy loader.

    :param module:
    :return:
    '''

    mod = None
    # pylint: disable=E0598
    try:
        # importlib is in Python 2.7+ and 3+
        import importlib
        mod = importlib.import_module("salt.modules.inspectlib.{0}".format(module))
    except ImportError as err:
        # No importlib around (2.6)
        mod = getattr(__import__("salt.modules.inspectlib", globals(), locals(), fromlist=[str(module)]), module)
    # pylint: enable=E0598

    mod.__grains__ = __grains__
    mod.__pillar__ = __pillar__
    mod.__salt__ = __salt__

    return mod


def inspect(mode='all', priority=19, **kwargs):
    '''
    Start node inspection and save the data to the database for further query.

    Parameters:

    * **mode**: Clarify inspection mode: configuration, payload, all (default)

      payload
        * **filter**: Comma-separated directories to track payload.

    * **priority**: (advanced) Set priority of the inspection. Default is low priority.



    CLI Example:

    .. code-block:: bash

        salt '*' node.inspect
        salt '*' node.inspect configuration
        salt '*' node.inspect payload filter=/opt,/ext/oracle
    '''
    collector = _("collector")
    try:
        return collector.Inspector().request_snapshot(mode, priority=priority, **kwargs)
    except InspectorSnapshotException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:
        log.error(_get_error_message(ex))
        raise Exception(ex)


def query(scope, **kwargs):
    '''
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

        salt '*' node.query scope=os
        salt '*' node.query payload type=file,link filter=/etc size=Kb brief=False
    '''
    query = _("query")
    try:
        return query.Query(scope)(**kwargs)
    except InspectorQueryException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:
        log.error(_get_error_message(ex))
        raise Exception(ex)

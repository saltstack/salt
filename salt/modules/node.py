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
import importlib
from salt.modules.inspectlib.exceptions import (InspectorQueryException,
                                                InspectorSnapshotException)

# Import Salt libs
import salt.utils
import salt.utils.fsutils
from salt.exceptions import CommandExecutionError

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

    mod = importlib.import_module("salt.modules.inspectlib.{0}".format(module))
    mod.__grains__ = __grains__
    mod.__pillar__ = __pillar__
    mod.__salt__ = __salt__

    return mod


def inspect(mode='all', priority=19):
    '''
    Start node inspection and save the data to the database for further query.

    Parameters:

    * **mode**: Clarify inspection mode: configuration, payload, all (default)
    * **priority**: (advanced) Set priority of the inspection. Default is low priority.

    CLI Example:

    .. code-block:: bash

        salt '*' node.inspect
        salt '*' node.inspect configuration
    '''
    collector = _("collector")
    try:
        return collector.Inspector().request_snapshot(mode, priority=priority)
    except InspectorSnapshotException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:
        log.error(ex.message)
        raise Exception(ex)


def query(scope, **kwargs):
    '''
    Query the node for specific information.

    Parameters:

    * **scope**: Specify scope of the query.

    CLI Example:

    .. code-block:: bash

        salt '*' node.query scope=os
    '''
    query = _("query")
    try:
        return query.Query(scope)(**kwargs)
    except InspectorQueryException as ex:
        raise CommandExecutionError(ex)
    except Exception as ex:
        log.error(ex.message)
        raise Exception(ex)

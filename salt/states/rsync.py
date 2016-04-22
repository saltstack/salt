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
Rsync state.

.. versionadded:: 2016.3.0
'''

from __future__ import absolute_import
import salt.utils
import os


def __virtual__():
    '''
    Only if Rsync is available.

    :return:
    '''
    return salt.utils.which('rsync') and 'rsync' or False


def _get_summary(rsync_out):
    '''
    Get summary from the rsync successfull output.

    :param rsync_out:
    :return:
    '''

    return "- " + "\n- ".join([elm for elm in rsync_out.split("\n\n")[-1].replace("  ", "\n").split("\n") if elm])


def _get_changes(rsync_out):
    '''
    Get changes from the rsync successfull output.

    :param rsync_out:
    :return:
    '''
    copied = list()
    deleted = list()

    for line in rsync_out.split("\n\n")[0].split("\n")[1:]:
        if line.startswith("deleting "):
            deleted.append(line.split(" ", 1)[-1])
        else:
            copied.append(line)

    return {
        'copied': os.linesep.join(sorted(copied)) or "N/A",
        'deleted': os.linesep.join(sorted(deleted)) or "N/A",
    }


def synchronized(name, source,
                 delete=False,
                 force=False,
                 update=False,
                 passwordfile=None,
                 exclude=None,
                 excludefrom=None,
                 prepare=False):
    '''
    Guarantees that the source directory is always copied to the target.

    :param name: Name of the target directory.
    :param source: Source directory.
    :param prepare: Create destination directory if it does not exists.
    :param delete: Delete extraneous files from the destination dirs (True or False)
    :param force: Force deletion of dirs even if not empty
    :param update: Skip files that are newer on the receiver (True or False)
    :param passwordfile: Read daemon-access password from the file (path)
    :param exclude: Exclude files, that matches pattern.
    :param excludefrom: Read exclude patterns from the file (path)
    :return:

    .. code-block:: yaml

        /opt/user-backups:
          rsync.synchronized:
            - source: /home
            - force: True
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    if not os.path.exists(source):
        ret['result'] = False
        ret['comment'] = "Source directory {src} was not found.".format(src=source)
    elif not os.path.exists(name) and not force and not prepare:
        ret['result'] = False
        ret['comment'] = "Destination directory {dest} was not found.".format(dest=name)
    else:
        if not os.path.exists(name) and prepare:
            os.makedirs(name)

        result = __salt__['rsync.rsync'](source, name, delete=delete, force=force, update=update,
                                         passwordfile=passwordfile, exclude=exclude, excludefrom=excludefrom)
        if result.get('retcode'):
            ret['result'] = False
            ret['comment'] = result['stderr']
            ret['changes'] = result['stdout']
        else:
            ret['comment'] = _get_summary(result['stdout'])
            ret['changes'] = _get_changes(result['stdout'])

    return ret

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
State to synchronize files and directories with rsync.

.. versionadded:: 2016.3.0

.. code-block:: yaml

    /opt/user-backups:
      rsync.synchronized:
        - source: /home
        - force: True

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
    '''

    return "- " + "\n- ".join([elm for elm in rsync_out.split("\n\n")[-1].replace("  ", "\n").split("\n") if elm])


def _get_changes(rsync_out):
    '''
    Get changes from the rsync successfull output.
    '''
    copied = list()
    deleted = list()

    for line in rsync_out.split("\n\n")[0].split("\n")[1:]:
        if line.startswith("deleting "):
            deleted.append(line.split(" ", 1)[-1])
        else:
            copied.append(line)

    ret = {
        'copied': os.linesep.join(sorted(copied)) or "N/A",
        'deleted': os.linesep.join(sorted(deleted)) or "N/A",
    }

    # Return whether anything really changed
    ret['changed'] = not ((ret['copied'] == 'N/A') and (ret['deleted'] == 'N/A'))

    return ret


def synchronized(name, source,
                 delete=False,
                 force=False,
                 update=False,
                 passwordfile=None,
                 exclude=None,
                 excludefrom=None,
                 prepare=False,
                 dryrun=False):
    '''
    Guarantees that the source directory is always copied to the target.

    name
        Name of the target directory.

    source
        Source directory.

    prepare
        Create destination directory if it does not exists.

    delete
        Delete extraneous files from the destination dirs (True or False)

    force
        Force deletion of dirs even if not empty

    update
        Skip files that are newer on the receiver (True or False)

    passwordfile
        Read daemon-access password from the file (path)

    exclude
        Exclude files, that matches pattern.

    excludefrom
        Read exclude patterns from the file (path)

    dryrun
        Perform a trial run with no changes made. Is the same as
        doing test=True

        .. versionadded:: 2016.3.1
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    if not os.path.exists(name) and not force and not prepare:
        ret['result'] = False
        ret['comment'] = "Destination directory {dest} was not found.".format(dest=name)
    else:
        if not os.path.exists(name) and prepare:
            os.makedirs(name)

        if __opts__['test']:
            dryrun = True

        result = __salt__['rsync.rsync'](source, name, delete=delete, force=force, update=update,
                                         passwordfile=passwordfile, exclude=exclude, excludefrom=excludefrom,
                                         dryrun=dryrun)

        if __opts__['test'] or dryrun:
            ret['result'] = None
            ret['comment'] = _get_summary(result['stdout'])
            return ret

        # Failed
        if result.get('retcode'):
            ret['result'] = False
            ret['comment'] = result['stderr']
            ret['changes'] = result['stdout']
        # Changed
        elif _get_changes(result['stdout'])['changed']:
            ret['comment'] = _get_summary(result['stdout'])
            ret['changes'] = _get_changes(result['stdout'])
            del ret['changes']['changed']  # Don't need to print the boolean
        # Clean
        else:
            ret['comment'] = _get_summary(result['stdout'])
            ret['changes'] = {}
    return ret

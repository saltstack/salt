# -*- coding: utf-8 -*-
'''
Operations on regular files, special files, directories, and symlinks
=====================================================================

Salt States can aggressively manipulate files on a system. There are a number
of ways in which files can be managed.

Regular files can be enforced with the :mod:`file.managed
<salt.states.file.managed>` state. This state downloads files from the salt
master and places them on the target system. Managed files can be rendered as a
jinja, mako, or wempy template, adding a dynamic component to file management.
An example of :mod:`file.managed <salt.states.file.managed>` which makes use of
the jinja templating system would look like this:

.. code-block:: jinja

    /etc/http/conf/http.conf:
      file.managed:
        - source: salt://apache/http.conf
        - user: root
        - group: root
        - mode: 644
        - attrs: ai
        - template: jinja
        - defaults:
            custom_var: "default value"
            other_var: 123
    {% if grains['os'] == 'Ubuntu' %}
        - context:
            custom_var: "override"
    {% endif %}

It is also possible to use the :mod:`py renderer <salt.renderers.py>` as a
templating option. The template would be a Python script which would need to
contain a function called ``run()``, which returns a string. All arguments
to the state will be made available to the Python script as globals. The
returned string will be the contents of the managed file. For example:

.. code-block:: python

    def run():
        lines = ['foo', 'bar', 'baz']
        lines.extend([source, name, user, context])  # Arguments as globals
        return '\\n\\n'.join(lines)

.. note::

    The ``defaults`` and ``context`` arguments require extra indentation (four
    spaces instead of the normal two) in order to create a nested dictionary.
    :ref:`More information <nested-dict-indentation>`.

If using a template, any user-defined template variables in the file defined in
``source`` must be passed in using the ``defaults`` and/or ``context``
arguments. The general best practice is to place default values in
``defaults``, with conditional overrides going into ``context``, as seen above.

The template will receive a variable ``custom_var``, which would be accessed in
the template using ``{{ custom_var }}``. If the operating system is Ubuntu, the
value of the variable ``custom_var`` would be *override*, otherwise it is the
default *default value*

The ``source`` parameter can be specified as a list. If this is done, then the
first file to be matched will be the one that is used. This allows you to have
a default file on which to fall back if the desired file does not exist on the
salt fileserver. Here's an example:

.. code-block:: jinja

    /etc/foo.conf:
      file.managed:
        - source:
          - salt://foo.conf.{{ grains['fqdn'] }}
          - salt://foo.conf.fallback
        - user: foo
        - group: users
        - mode: 644
        - attrs: i
        - backup: minion

.. note::

    Salt supports backing up managed files via the backup option. For more
    details on this functionality please review the
    :ref:`backup_mode documentation <file-state-backups>`.

The ``source`` parameter can also specify a file in another Salt environment.
In this example ``foo.conf`` in the ``dev`` environment will be used instead.

.. code-block:: yaml

    /etc/foo.conf:
      file.managed:
        - source:
          - 'salt://foo.conf?saltenv=dev'
        - user: foo
        - group: users
        - mode: '0644'
        - attrs: i

.. warning::

    When using a mode that includes a leading zero you must wrap the
    value in single quotes. If the value is not wrapped in quotes it
    will be read by YAML as an integer and evaluated as an octal.

The ``names`` parameter, which is part of the state compiler, can be used to
expand the contents of a single state declaration into multiple, single state
declarations. Each item in the ``names`` list receives its own individual state
``name`` and is converted into its own low-data structure. This is a convenient
way to manage several files with similar attributes.

.. code-block:: yaml

    salt_master_conf:
      file.managed:
        - user: root
        - group: root
        - mode: '0644'
        - names:
          - /etc/salt/master.d/master.conf:
            - source: salt://saltmaster/master.conf
          - /etc/salt/minion.d/minion-99.conf:
            - source: salt://saltmaster/minion.conf

.. note::

    There is more documentation about this feature in the :ref:`Names declaration
    <names-declaration>` section of the :ref:`Highstate docs <states-highstate>`.

Special files can be managed via the ``mknod`` function. This function will
create and enforce the permissions on a special file. The function supports the
creation of character devices, block devices, and FIFO pipes. The function will
create the directory structure up to the special file if it is needed on the
minion. The function will not overwrite or operate on (change major/minor
numbers) existing special files with the exception of user, group, and
permissions. In most cases the creation of some special files require root
permissions on the minion. This would require that the minion to be run as the
root user. Here is an example of a character device:

.. code-block:: yaml

    /var/named/chroot/dev/random:
      file.mknod:
        - ntype: c
        - major: 1
        - minor: 8
        - user: named
        - group: named
        - mode: 660

Here is an example of a block device:

.. code-block:: yaml

    /var/named/chroot/dev/loop0:
      file.mknod:
        - ntype: b
        - major: 7
        - minor: 0
        - user: named
        - group: named
        - mode: 660

Here is an example of a fifo pipe:

.. code-block:: yaml

    /var/named/chroot/var/log/logfifo:
      file.mknod:
        - ntype: p
        - user: named
        - group: named
        - mode: 660

Directories can be managed via the ``directory`` function. This function can
create and enforce the permissions on a directory. A directory statement will
look like this:

.. code-block:: yaml

    /srv/stuff/substuf:
      file.directory:
        - user: fred
        - group: users
        - mode: 755
        - makedirs: True

If you need to enforce user and/or group ownership or permissions recursively
on the directory's contents, you can do so by adding a ``recurse`` directive:

.. code-block:: yaml

    /srv/stuff/substuf:
      file.directory:
        - user: fred
        - group: users
        - mode: 755
        - makedirs: True
        - recurse:
          - user
          - group
          - mode

As a default, ``mode`` will resolve to ``dir_mode`` and ``file_mode``, to
specify both directory and file permissions, use this form:

.. code-block:: yaml

    /srv/stuff/substuf:
      file.directory:
        - user: fred
        - group: users
        - file_mode: 744
        - dir_mode: 755
        - makedirs: True
        - recurse:
          - user
          - group
          - mode

Symlinks can be easily created; the symlink function is very simple and only
takes a few arguments:

.. code-block:: yaml

    /etc/grub.conf:
      file.symlink:
        - target: /boot/grub/grub.conf

Recursive directory management can also be set via the ``recurse``
function. Recursive directory management allows for a directory on the salt
master to be recursively copied down to the minion. This is a great tool for
deploying large code and configuration systems. A state using ``recurse``
would look something like this:

.. code-block:: yaml

    /opt/code/flask:
      file.recurse:
        - source: salt://code/flask
        - include_empty: True

A more complex ``recurse`` example:

.. code-block:: jinja

    {% set site_user = 'testuser' %}
    {% set site_name = 'test_site' %}
    {% set project_name = 'test_proj' %}
    {% set sites_dir = 'test_dir' %}

    django-project:
      file.recurse:
        - name: {{ sites_dir }}/{{ site_name }}/{{ project_name }}
        - user: {{ site_user }}
        - dir_mode: 2775
        - file_mode: '0644'
        - template: jinja
        - source: salt://project/templates_dir
        - include_empty: True

Retention scheduling can be applied to manage contents of backup directories.
For example:

.. code-block:: yaml

    /var/backups/example_directory:
      file.retention_schedule:
        - strptime_format: example_name_%Y%m%dT%H%M%S.tar.bz2
        - retain:
            most_recent: 5
            first_of_hour: 4
            first_of_day: 14
            first_of_week: 6
            first_of_month: 6
            first_of_year: all

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import difflib
import itertools
import logging
import os
import posixpath
import re
import shutil
import sys
import time
import traceback
from collections import Iterable, Mapping, defaultdict
from datetime import datetime, date   # python3 problem in the making?

# Import salt libs
import salt.loader
import salt.payload
import salt.utils.data
import salt.utils.dateutils
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.hashutils
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.url
import salt.utils.versions
from salt.exceptions import CommandExecutionError
from salt.serializers import DeserializationError
from salt.state import get_accumulator_dir as _get_accumulator_dir

if salt.utils.platform.is_windows():
    import salt.utils.win_dacl
    import salt.utils.win_functions
    import salt.utils.winapi

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import zip_longest
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module
if salt.utils.platform.is_windows():
    import pywintypes
    import win32com.client

log = logging.getLogger(__name__)

COMMENT_REGEX = r'^([[:space:]]*){0}[[:space:]]?'
__NOT_FOUND = object()

__func_alias__ = {
    'copy_': 'copy',
}


def _get_accumulator_filepath():
    '''
    Return accumulator data path.
    '''
    return os.path.join(
        _get_accumulator_dir(__opts__['cachedir']),
        __instance_id__
    )


def _load_accumulators():
    def _deserialize(path):
        serial = salt.payload.Serial(__opts__)
        ret = {'accumulators': {}, 'accumulators_deps': {}}
        try:
            with salt.utils.files.fopen(path, 'rb') as f:
                loaded = serial.load(f)
                return loaded if loaded else ret
        except (IOError, NameError):
            # NameError is a msgpack error from salt-ssh
            return ret

    loaded = _deserialize(_get_accumulator_filepath())

    return loaded['accumulators'], loaded['accumulators_deps']


def _persist_accummulators(accumulators, accumulators_deps):
    accumm_data = {'accumulators': accumulators,
                   'accumulators_deps': accumulators_deps}

    serial = salt.payload.Serial(__opts__)
    try:
        with salt.utils.files.fopen(_get_accumulator_filepath(), 'w+b') as f:
            serial.dump(accumm_data, f)
    except NameError:
        # msgpack error from salt-ssh
        pass


def _check_user(user, group):
    '''
    Checks if the named user and group are present on the minion
    '''
    err = ''
    if user:
        uid = __salt__['file.user_to_uid'](user)
        if uid == '':
            err += 'User {0} is not available '.format(user)
    if group:
        gid = __salt__['file.group_to_gid'](group)
        if gid == '':
            err += 'Group {0} is not available'.format(group)
    return err


def _is_valid_relpath(
        relpath,
        maxdepth=None):
    '''
    Performs basic sanity checks on a relative path.

    Requires POSIX-compatible paths (i.e. the kind obtained through
    cp.list_master or other such calls).

    Ensures that the path does not contain directory transversal, and
    that it does not exceed a stated maximum depth (if specified).
    '''
    # Check relpath surrounded by slashes, so that `..` can be caught as
    # a path component at the start, end, and in the middle of the path.
    sep, pardir = posixpath.sep, posixpath.pardir
    if sep + pardir + sep in sep + relpath + sep:
        return False

    # Check that the relative path's depth does not exceed maxdepth
    if maxdepth is not None:
        path_depth = relpath.strip(sep).count(sep)
        if path_depth > maxdepth:
            return False

    return True


def _salt_to_os_path(path):
    '''
    Converts a path from the form received via salt master to the OS's native
    path format.
    '''
    return os.path.normpath(path.replace(posixpath.sep, os.path.sep))


def _gen_recurse_managed_files(
        name,
        source,
        keep_symlinks=False,
        include_pat=None,
        exclude_pat=None,
        maxdepth=None,
        include_empty=False,
        **kwargs):
    '''
    Generate the list of files managed by a recurse state
    '''

    # Convert a relative path generated from salt master paths to an OS path
    # using "name" as the base directory
    def full_path(master_relpath):
        return os.path.join(name, _salt_to_os_path(master_relpath))

    # Process symlinks and return the updated filenames list
    def process_symlinks(filenames, symlinks):
        for lname, ltarget in six.iteritems(symlinks):
            srelpath = posixpath.relpath(lname, srcpath)
            if not _is_valid_relpath(srelpath, maxdepth=maxdepth):
                continue
            if not salt.utils.stringutils.check_include_exclude(
                    srelpath, include_pat, exclude_pat):
                continue
            # Check for all paths that begin with the symlink
            # and axe it leaving only the dirs/files below it.
            # This needs to use list() otherwise they reference
            # the same list.
            _filenames = list(filenames)
            for filename in _filenames:
                if filename.startswith(lname):
                    log.debug('** skipping file ** {0}, it intersects a '
                              'symlink'.format(filename))
                    filenames.remove(filename)
            # Create the symlink along with the necessary dirs.
            # The dir perms/ownership will be adjusted later
            # if needed
            managed_symlinks.add((srelpath, ltarget))

            # Add the path to the keep set in case clean is set to True
            keep.add(full_path(srelpath))
        vdir.update(keep)
        return filenames

    managed_files = set()
    managed_directories = set()
    managed_symlinks = set()
    keep = set()
    vdir = set()

    srcpath, senv = salt.utils.url.parse(source)
    if senv is None:
        senv = __env__
    if not srcpath.endswith(posixpath.sep):
        # we're searching for things that start with this *directory*.
        srcpath = srcpath + posixpath.sep
    fns_ = __salt__['cp.list_master'](senv, srcpath)

    # If we are instructed to keep symlinks, then process them.
    if keep_symlinks:
        # Make this global so that emptydirs can use it if needed.
        symlinks = __salt__['cp.list_master_symlinks'](senv, srcpath)
        fns_ = process_symlinks(fns_, symlinks)

    for fn_ in fns_:
        if not fn_.strip():
            continue

        # fn_ here is the absolute (from file_roots) source path of
        # the file to copy from; it is either a normal file or an
        # empty dir(if include_empty==true).

        relname = salt.utils.data.decode(posixpath.relpath(fn_, srcpath))
        if not _is_valid_relpath(relname, maxdepth=maxdepth):
            continue

        # Check if it is to be excluded. Match only part of the path
        # relative to the target directory
        if not salt.utils.stringutils.check_include_exclude(
                relname, include_pat, exclude_pat):
            continue
        dest = full_path(relname)
        dirname = os.path.dirname(dest)
        keep.add(dest)

        if dirname not in vdir:
            # verify the directory perms if they are set
            managed_directories.add(dirname)
            vdir.add(dirname)

        src = salt.utils.url.create(fn_, saltenv=senv)
        managed_files.add((dest, src))

    if include_empty:
        mdirs = __salt__['cp.list_master_dirs'](senv, srcpath)
        for mdir in mdirs:
            relname = posixpath.relpath(mdir, srcpath)
            if not _is_valid_relpath(relname, maxdepth=maxdepth):
                continue
            if not salt.utils.stringutils.check_include_exclude(
                    relname, include_pat, exclude_pat):
                continue
            mdest = full_path(relname)
            # Check for symlinks that happen to point to an empty dir.
            if keep_symlinks:
                islink = False
                for link in symlinks:
                    if mdir.startswith(link, 0):
                        log.debug('** skipping empty dir ** {0}, it intersects'
                                  ' a symlink'.format(mdir))
                        islink = True
                        break
                if islink:
                    continue

            managed_directories.add(mdest)
            keep.add(mdest)

    return managed_files, managed_directories, managed_symlinks, keep


def _gen_keep_files(name, require, walk_d=None):
    '''
    Generate the list of files that need to be kept when a dir based function
    like directory or recurse has a clean.
    '''
    def _is_child(path, directory):
        '''
        Check whether ``path`` is child of ``directory``
        '''
        path = os.path.abspath(path)
        directory = os.path.abspath(directory)

        relative = os.path.relpath(path, directory)

        return not relative.startswith(os.pardir)

    def _add_current_path(path):
        _ret = set()
        if os.path.isdir(path):
            dirs, files = walk_d.get(path, ((), ()))
            _ret.add(path)
            for _name in files:
                _ret.add(os.path.join(path, _name))
            for _name in dirs:
                _ret.add(os.path.join(path, _name))
        return _ret

    def _process_by_walk_d(name, ret):
        if os.path.isdir(name):
            walk_ret.update(_add_current_path(name))
            dirs, _ = walk_d.get(name, ((), ()))
            for _d in dirs:
                p = os.path.join(name, _d)
                walk_ret.update(_add_current_path(p))
                _process_by_walk_d(p, ret)

    def _process(name):
        ret = set()
        if os.path.isdir(name):
            for root, dirs, files in salt.utils.path.os_walk(name):
                ret.add(name)
                for name in files:
                    ret.add(os.path.join(root, name))
                for name in dirs:
                    ret.add(os.path.join(root, name))
        return ret

    keep = set()
    if isinstance(require, list):
        required_files = [comp for comp in require if 'file' in comp]
        for comp in required_files:
            for low in __lowstate__:
                # A requirement should match either the ID and the name of
                # another state.
                if low['name'] == comp['file'] or low['__id__'] == comp['file']:
                    fn = low['name']
                    fun = low['fun']
                    if os.path.isdir(fn):
                        if _is_child(fn, name):
                            if fun == 'recurse':
                                fkeep = _gen_recurse_managed_files(**low)[3]
                                log.debug('Keep from {0}: {1}'.format(fn, fkeep))
                                keep.update(fkeep)
                            elif walk_d:
                                walk_ret = set()
                                _process_by_walk_d(fn, walk_ret)
                                keep.update(walk_ret)
                            else:
                                keep.update(_process(fn))
                    else:
                        keep.add(fn)
    log.debug('Files to keep from required states: {0}'.format(list(keep)))
    return list(keep)


def _check_file(name):
    ret = True
    msg = ''

    if not os.path.isabs(name):
        ret = False
        msg = 'Specified file {0} is not an absolute path'.format(name)
    elif not os.path.exists(name):
        ret = False
        msg = '{0}: file not found'.format(name)

    return ret, msg


def _find_keep_files(root, keep):
    '''
    Compile a list of valid keep files (and directories).
    Used by _clean_dir()
    '''
    real_keep = set()
    real_keep.add(root)
    if isinstance(keep, list):
        for fn_ in keep:
            if not os.path.isabs(fn_):
                continue
            fn_ = os.path.normcase(os.path.abspath(fn_))
            real_keep.add(fn_)
            while True:
                fn_ = os.path.abspath(os.path.dirname(fn_))
                real_keep.add(fn_)
                drive, path = os.path.splitdrive(fn_)
                if not path.lstrip(os.sep):
                    break
    return real_keep


def _clean_dir(root, keep, exclude_pat):
    '''
    Clean out all of the files and directories in a directory (root) while
    preserving the files in a list (keep) and part of exclude_pat
    '''
    root = os.path.normcase(root)
    real_keep = _find_keep_files(root, keep)
    removed = set()

    def _delete_not_kept(nfn):
        if nfn not in real_keep:
            # -- check if this is a part of exclude_pat(only). No need to
            # check include_pat
            if not salt.utils.stringutils.check_include_exclude(
                    os.path.relpath(nfn, root), None, exclude_pat):
                return
            removed.add(nfn)
            if not __opts__['test']:
                try:
                    os.remove(nfn)
                except OSError:
                    __salt__['file.remove'](nfn)

    for roots, dirs, files in salt.utils.path.os_walk(root):
        for name in itertools.chain(dirs, files):
            _delete_not_kept(os.path.join(roots, name))
    return list(removed)


def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


def _check_directory(name,
                     user=None,
                     group=None,
                     recurse=False,
                     dir_mode=None,
                     file_mode=None,
                     clean=False,
                     require=False,
                     exclude_pat=None,
                     max_depth=None,
                     follow_symlinks=False):
    '''
    Check what changes need to be made on a directory
    '''
    changes = {}
    if recurse or clean:
        assert max_depth is None or not clean
        # walk path only once and store the result
        walk_l = list(_depth_limited_walk(name, max_depth))
        # root: (dirs, files) structure, compatible for python2.6
        walk_d = {}
        for i in walk_l:
            walk_d[i[0]] = (i[1], i[2])

    if recurse:
        try:
            recurse_set = _get_recurse_set(recurse)
        except (TypeError, ValueError) as exc:
            return False, '{0}'.format(exc), changes
        if 'user' not in recurse_set:
            user = None
        if 'group' not in recurse_set:
            group = None
        if 'mode' not in recurse_set:
            dir_mode = None
            file_mode = None

        check_files = 'ignore_files' not in recurse_set
        check_dirs = 'ignore_dirs' not in recurse_set
        for root, dirs, files in walk_l:
            if check_files:
                for fname in files:
                    fchange = {}
                    path = os.path.join(root, fname)
                    stats = __salt__['file.stats'](
                        path, None, follow_symlinks
                    )
                    if user is not None and user != stats.get('user'):
                        fchange['user'] = user
                    if group is not None and group != stats.get('group'):
                        fchange['group'] = group
                    if file_mode is not None and salt.utils.files.normalize_mode(file_mode) != salt.utils.files.normalize_mode(stats.get('mode')):
                        fchange['mode'] = file_mode
                    if fchange:
                        changes[path] = fchange
            if check_dirs:
                for name_ in dirs:
                    path = os.path.join(root, name_)
                    fchange = _check_dir_meta(path, user, group, dir_mode, follow_symlinks)
                    if fchange:
                        changes[path] = fchange
    # Recurse skips root (we always do dirs, not root), so always check root:
    fchange = _check_dir_meta(name, user, group, dir_mode, follow_symlinks)
    if fchange:
        changes[name] = fchange
    if clean:
        keep = _gen_keep_files(name, require, walk_d)

        def _check_changes(fname):
            path = os.path.join(root, fname)
            if path in keep:
                return {}
            else:
                if not salt.utils.stringutils.check_include_exclude(
                        os.path.relpath(path, name), None, exclude_pat):
                    return {}
                else:
                    return {path: {'removed': 'Removed due to clean'}}

        for root, dirs, files in walk_l:
            for fname in files:
                changes.update(_check_changes(fname))
            for name_ in dirs:
                changes.update(_check_changes(name_))

    if not os.path.isdir(name):
        changes[name] = {'directory': 'new'}
    if changes:
        comments = ['The following files will be changed:\n']
        for fn_ in changes:
            for key, val in six.iteritems(changes[fn_]):
                comments.append('{0}: {1} - {2}\n'.format(fn_, key, val))
        return None, ''.join(comments), changes
    return True, 'The directory {0} is in the correct state'.format(name), changes


def _check_directory_win(name,
                         win_owner=None,
                         win_perms=None,
                         win_deny_perms=None,
                         win_inheritance=None,
                         win_perms_reset=None):
    '''
    Check what changes need to be made on a directory
    '''
    changes = {}

    if not os.path.isdir(name):
        changes = {name: {'directory': 'new'}}
    else:
        # Check owner by SID
        if win_owner is not None:
            current_owner = salt.utils.win_dacl.get_owner(name)
            current_owner_sid = salt.utils.win_functions.get_sid_from_name(current_owner)
            expected_owner_sid = salt.utils.win_functions.get_sid_from_name(win_owner)
            if not current_owner_sid == expected_owner_sid:
                changes['owner'] = win_owner

        # Check perms
        perms = salt.utils.win_dacl.get_permissions(name)

        # Verify Permissions
        if win_perms is not None:
            for user in win_perms:
                # Check that user exists:
                try:
                    salt.utils.win_dacl.get_name(user)
                except CommandExecutionError:
                    continue

                grant_perms = []
                # Check for permissions
                if isinstance(win_perms[user]['perms'], six.string_types):
                    if not salt.utils.win_dacl.has_permission(
                            name, user, win_perms[user]['perms']):
                        grant_perms = win_perms[user]['perms']
                else:
                    for perm in win_perms[user]['perms']:
                        if not salt.utils.win_dacl.has_permission(
                                name, user, perm, exact=False):
                            grant_perms.append(win_perms[user]['perms'])
                if grant_perms:
                    if 'grant_perms' not in changes:
                        changes['grant_perms'] = {}
                    if user not in changes['grant_perms']:
                        changes['grant_perms'][user] = {}
                    changes['grant_perms'][user]['perms'] = grant_perms

                # Check Applies to
                if 'applies_to' not in win_perms[user]:
                    applies_to = 'this_folder_subfolders_files'
                else:
                    applies_to = win_perms[user]['applies_to']

                if user in perms:
                    user = salt.utils.win_dacl.get_name(user)

                    # Get the proper applies_to text
                    at_flag = salt.utils.win_dacl.flags().ace_prop['file'][applies_to]
                    applies_to_text = salt.utils.win_dacl.flags().ace_prop['file'][at_flag]

                    if 'grant' in perms[user]:
                        if not perms[user]['grant']['applies to'] == applies_to_text:
                            if 'grant_perms' not in changes:
                                changes['grant_perms'] = {}
                            if user not in changes['grant_perms']:
                                changes['grant_perms'][user] = {}
                            changes['grant_perms'][user]['applies_to'] = applies_to

        # Verify Deny Permissions
        if win_deny_perms is not None:
            for user in win_deny_perms:
                # Check that user exists:
                try:
                    salt.utils.win_dacl.get_name(user)
                except CommandExecutionError:
                    continue

                deny_perms = []
                # Check for permissions
                if isinstance(win_deny_perms[user]['perms'], six.string_types):
                    if not salt.utils.win_dacl.has_permission(
                            name, user, win_deny_perms[user]['perms'], 'deny'):
                        deny_perms = win_deny_perms[user]['perms']
                else:
                    for perm in win_deny_perms[user]['perms']:
                        if not salt.utils.win_dacl.has_permission(
                                name, user, perm, 'deny', exact=False):
                            deny_perms.append(win_deny_perms[user]['perms'])
                if deny_perms:
                    if 'deny_perms' not in changes:
                        changes['deny_perms'] = {}
                    if user not in changes['deny_perms']:
                        changes['deny_perms'][user] = {}
                    changes['deny_perms'][user]['perms'] = deny_perms

                # Check Applies to
                if 'applies_to' not in win_deny_perms[user]:
                    applies_to = 'this_folder_subfolders_files'
                else:
                    applies_to = win_deny_perms[user]['applies_to']

                if user in perms:
                    user = salt.utils.win_dacl.get_name(user)

                    # Get the proper applies_to text
                    at_flag = salt.utils.win_dacl.flags().ace_prop['file'][applies_to]
                    applies_to_text = salt.utils.win_dacl.flags().ace_prop['file'][at_flag]

                    if 'deny' in perms[user]:
                        if not perms[user]['deny']['applies to'] == applies_to_text:
                            if 'deny_perms' not in changes:
                                changes['deny_perms'] = {}
                            if user not in changes['deny_perms']:
                                changes['deny_perms'][user] = {}
                            changes['deny_perms'][user]['applies_to'] = applies_to

        # Check inheritance
        if win_inheritance is not None:
            if not win_inheritance == salt.utils.win_dacl.get_inheritance(name):
                changes['inheritance'] = win_inheritance

        # Check reset
        if win_perms_reset:
            for user_name in perms:
                if user_name not in win_perms:
                    if 'grant' in perms[user_name] and not perms[user_name]['grant']['inherited']:
                        if 'remove_perms' not in changes:
                            changes['remove_perms'] = {}
                        changes['remove_perms'].update({user_name: perms[user_name]})
                if user_name not in win_deny_perms:
                    if 'deny' in perms[user_name] and not perms[user_name]['deny']['inherited']:
                        if 'remove_perms' not in changes:
                            changes['remove_perms'] = {}
                        changes['remove_perms'].update({user_name: perms[user_name]})

    if changes:
        return None, 'The directory "{0}" will be changed'.format(name), changes

    return True, 'The directory {0} is in the correct state'.format(name), changes


def _check_dir_meta(name,
                    user,
                    group,
                    mode,
                    follow_symlinks=False):
    '''
    Check the changes in directory metadata
    '''
    try:
        stats = __salt__['file.stats'](name, None, follow_symlinks)
    except CommandExecutionError:
        stats = {}

    changes = {}
    if not stats:
        changes['directory'] = 'new'
        return changes
    if (user is not None
            and user != stats['user']
            and user != stats.get('uid')):
        changes['user'] = user
    if (group is not None
            and group != stats['group']
            and group != stats.get('gid')):
        changes['group'] = group
    # Normalize the dir mode
    smode = salt.utils.files.normalize_mode(stats['mode'])
    mode = salt.utils.files.normalize_mode(mode)
    if mode is not None and mode != smode:
        changes['mode'] = mode
    return changes


def _check_touch(name, atime, mtime):
    '''
    Check to see if a file needs to be updated or created
    '''
    ret = {
        'result': None,
        'comment': '',
        'changes': {'new': name},
    }
    if not os.path.exists(name):
        ret['comment'] = 'File {0} is set to be created'.format(name)
    else:
        stats = __salt__['file.stats'](name, follow_symlinks=False)
        if ((atime is not None
             and six.text_type(atime) != six.text_type(stats['atime'])) or
            (mtime is not None
                and six.text_type(mtime) != six.text_type(stats['mtime']))):
            ret['comment'] = 'Times set to be updated on file {0}'.format(name)
            ret['changes'] = {'touched': name}
        else:
            ret['result'] = True
            ret['comment'] = 'File {0} exists and has the correct times'.format(name)
    return ret


def _get_symlink_ownership(path):
    if salt.utils.platform.is_windows():
        owner = salt.utils.win_dacl.get_owner(path)
        return owner, owner
    else:
        return (
            __salt__['file.get_user'](path, follow_symlinks=False),
            __salt__['file.get_group'](path, follow_symlinks=False)
        )


def _check_symlink_ownership(path, user, group, win_owner):
    '''
    Check if the symlink ownership matches the specified user and group
    '''
    cur_user, cur_group = _get_symlink_ownership(path)
    if salt.utils.platform.is_windows():
        return win_owner == cur_user
    else:
        return (cur_user == user) and (cur_group == group)


def _set_symlink_ownership(path, user, group, win_owner):
    '''
    Set the ownership of a symlink and return a boolean indicating
    success/failure
    '''
    if salt.utils.platform.is_windows():
        try:
            salt.utils.win_dacl.set_owner(path, win_owner)
        except CommandExecutionError:
            pass
    else:
        try:
            __salt__['file.lchown'](path, user, group)
        except OSError:
            pass
    return _check_symlink_ownership(path, user, group, win_owner)


def _symlink_check(name, target, force, user, group, win_owner):
    '''
    Check the symlink function
    '''
    changes = {}
    if not os.path.exists(name) and not __salt__['file.is_link'](name):
        changes['new'] = name
        return None, 'Symlink {0} to {1} is set for creation'.format(
            name, target
        ), changes
    if __salt__['file.is_link'](name):
        if __salt__['file.readlink'](name) != target:
            changes['change'] = name
            return None, 'Link {0} target is set to be changed to {1}'.format(
                name, target
            ), changes
        else:
            result = True
            msg = 'The symlink {0} is present'.format(name)
            if not _check_symlink_ownership(name, user, group, win_owner):
                result = None
                changes['ownership'] = '{0}:{1}'.format(*_get_symlink_ownership(name))
                msg += (
                    ', but the ownership of the symlink would be changed '
                    'from {2}:{3} to {0}:{1}'
                ).format(user, group, *_get_symlink_ownership(name))
            return result, msg, changes
    else:
        if force:
            return None, ('The file or directory {0} is set for removal to '
                          'make way for a new symlink targeting {1}'
                          .format(name, target)), changes
        return False, ('File or directory exists where the symlink {0} '
                       'should be. Did you mean to use force?'.format(name)), changes


def _hardlink_same(name, target):
    '''
    Check to see if the inodes match for the name and the target
    '''
    res = __salt__['file.stats'](name, None, follow_symlinks=False)
    if 'inode' not in res:
        return False
    name_i = res['inode']

    res = __salt__['file.stats'](target, None, follow_symlinks=False)
    if 'inode' not in res:
        return False
    target_i = res['inode']

    return name_i == target_i


def _hardlink_check(name, target, force):
    '''
    Check the hardlink function
    '''
    changes = {}
    if not os.path.exists(target):
        msg = 'Target {0} for hard link does not exist'.format(target)
        return False, msg, changes

    elif os.path.isdir(target):
        msg = 'Unable to hard link from directory {0}'.format(target)
        return False, msg, changes

    if os.path.isdir(name):
        msg = 'Unable to hard link to directory {0}'.format(name)
        return False, msg, changes

    elif not os.path.exists(name):
        msg = 'Hard link {0} to {1} is set for creation'.format(name, target)
        changes['new'] = name
        return None, msg, changes

    elif __salt__['file.is_hardlink'](name):
        if _hardlink_same(name, target):
            msg = 'The hard link {0} is presently targetting {1}'.format(name, target)
            return True, msg, changes

        msg = 'Link {0} target is set to be changed to {1}'.format(name, target)
        changes['change'] = name
        return None, msg, changes

    if force:
        msg = (
            'The file or directory {0} is set for removal to '
            'make way for a new hard link targeting {1}'.format(name, target)
        )
        return None, msg, changes

    msg = (
        'File or directory exists where the hard link {0} '
        'should be. Did you mean to use force?'.format(name)
    )
    return False, msg, changes


def _test_owner(kwargs, user=None):
    '''
    Convert owner to user, since other config management tools use owner,
    no need to punish people coming from other systems.
    PLEASE DO NOT DOCUMENT THIS! WE USE USER, NOT OWNER!!!!
    '''
    if user:
        return user
    if 'owner' in kwargs:
        log.warning(
            'Use of argument owner found, "owner" is invalid, please '
            'use "user"'
        )
        return kwargs['owner']

    return user


def _unify_sources_and_hashes(source=None, source_hash=None,
                              sources=None, source_hashes=None):
    '''
    Silly little function to give us a standard tuple list for sources and
    source_hashes
    '''
    if sources is None:
        sources = []

    if source_hashes is None:
        source_hashes = []

    if source and sources:
        return (False,
                "source and sources are mutually exclusive", [])

    if source_hash and source_hashes:
        return (False,
                "source_hash and source_hashes are mutually exclusive", [])

    if source:
        return (True, '', [(source, source_hash)])

    # Make a nice neat list of tuples exactly len(sources) long..
    return True, '', list(zip_longest(sources, source_hashes[:len(sources)]))


def _get_template_texts(source_list=None,
                        template='jinja',
                        defaults=None,
                        context=None,
                        **kwargs):
    '''
    Iterate a list of sources and process them as templates.
    Returns a list of 'chunks' containing the rendered templates.
    '''

    ret = {'name': '_get_template_texts',
           'changes': {},
           'result': True,
           'comment': '',
           'data': []}

    if source_list is None:
        return _error(ret,
                      '_get_template_texts called with empty source_list')

    txtl = []

    for (source, source_hash) in source_list:

        tmpctx = defaults if defaults else {}
        if context:
            tmpctx.update(context)
        rndrd_templ_fn = __salt__['cp.get_template'](
            source,
            '',
            template=template,
            saltenv=__env__,
            context=tmpctx,
            **kwargs
        )
        msg = 'cp.get_template returned {0} (Called with: {1})'
        log.debug(msg.format(rndrd_templ_fn, source))
        if rndrd_templ_fn:
            tmplines = None
            with salt.utils.files.fopen(rndrd_templ_fn, 'rb') as fp_:
                tmplines = fp_.read()
                tmplines = salt.utils.stringutils.to_unicode(tmplines)
                tmplines = tmplines.splitlines(True)
            if not tmplines:
                msg = 'Failed to read rendered template file {0} ({1})'
                log.debug(msg.format(rndrd_templ_fn, source))
                ret['name'] = source
                return _error(ret, msg.format(rndrd_templ_fn, source))
            txtl.append(''.join(tmplines))
        else:
            msg = 'Failed to load template file {0}'.format(source)
            log.debug(msg)
            ret['name'] = source
            return _error(ret, msg)

    ret['data'] = txtl
    return ret


def _validate_str_list(arg, encoding=None):
    '''
    ensure ``arg`` is a list of strings
    '''
    if isinstance(arg, six.binary_type):
        ret = [salt.utils.stringutils.to_unicode(arg, encoding=encoding)]
    elif isinstance(arg, six.string_types):
        ret = [arg]
    elif isinstance(arg, Iterable) and not isinstance(arg, Mapping):
        ret = []
        for item in arg:
            if isinstance(item, six.string_types):
                ret.append(item)
            else:
                ret.append(six.text_type(item))
    else:
        ret = [six.text_type(arg)]
    return ret


def _get_shortcut_ownership(path):
    return __salt__['file.get_user'](path, follow_symlinks=False)


def _check_shortcut_ownership(path, user):
    '''
    Check if the shortcut ownership matches the specified user
    '''
    cur_user = _get_shortcut_ownership(path)
    return cur_user == user


def _set_shortcut_ownership(path, user):
    '''
    Set the ownership of a shortcut and return a boolean indicating
    success/failure
    '''
    try:
        __salt__['file.lchown'](path, user)
    except OSError:
        pass
    return _check_shortcut_ownership(path, user)


def _shortcut_check(name,
                    target,
                    arguments,
                    working_dir,
                    description,
                    icon_location,
                    force,
                    user):
    '''
    Check the shortcut function
    '''
    changes = {}
    if not os.path.exists(name):
        changes['new'] = name
        return None, 'Shortcut "{0}" to "{1}" is set for creation'.format(
            name, target
        ), changes

    if os.path.isfile(name):
        with salt.utils.winapi.Com():
            shell = win32com.client.Dispatch("WScript.Shell")
        scut = shell.CreateShortcut(name)
        state_checks = [scut.TargetPath.lower() == target.lower()]
        if arguments is not None:
            state_checks.append(scut.Arguments == arguments)
        if working_dir is not None:
            state_checks.append(
                scut.WorkingDirectory.lower() == working_dir.lower()
            )
        if description is not None:
            state_checks.append(scut.Description == description)
        if icon_location is not None:
            state_checks.append(
                scut.IconLocation.lower() == icon_location.lower()
            )

        if not all(state_checks):
            changes['change'] = name
            return None, 'Shortcut "{0}" target is set to be changed to "{1}"'.format(
                name, target
            ), changes
        else:
            result = True
            msg = 'The shortcut "{0}" is present'.format(name)
            if not _check_shortcut_ownership(name, user):
                result = None
                changes['ownership'] = '{0}'.format(_get_shortcut_ownership(name))
                msg += (
                    ', but the ownership of the shortcut would be changed '
                    'from {1} to {0}'
                ).format(user, _get_shortcut_ownership(name))
            return result, msg, changes
    else:
        if force:
            return None, ('The link or directory "{0}" is set for removal to '
                          'make way for a new shortcut targeting "{1}"'
                          .format(name, target)), changes
        return False, ('Link or directory exists where the shortcut "{0}" '
                       'should be. Did you mean to use force?'.format(name)), changes


def _makedirs(name,
              user=None,
              group=None,
              dir_mode=None,
              win_owner=None,
              win_perms=None,
              win_deny_perms=None,
              win_inheritance=None):
    '''
    Helper function for creating directories when the ``makedirs`` option is set
    to ``True``. Handles Unix and Windows based systems

    .. versionadded:: 2017.7.8

    Args:
        name (str): The directory path to create
        user (str): The linux user to own the directory
        group (str): The linux group to own the directory
        dir_mode (str): The linux mode to apply to the directory
        win_owner (str): The Windows user to own the directory
        win_perms (dict): A dictionary of grant permissions for Windows
        win_deny_perms (dict): A dictionary of deny permissions for Windows
        win_inheritance (bool): True to inherit permissions on Windows

    Returns:
        bool: True if successful, otherwise False on Windows
        str: Error messages on failure on Linux
        None: On successful creation on Linux

    Raises:
        CommandExecutionError: If the drive is not mounted on Windows
    '''
    if salt.utils.platform.is_windows():
        # Make sure the drive is mapped before trying to create the
        # path in windows
        drive, path = os.path.splitdrive(name)
        if not os.path.isdir(drive):
            raise CommandExecutionError(drive)
        win_owner = win_owner if win_owner else user
        return __salt__['file.makedirs'](path=name,
                                         owner=win_owner,
                                         grant_perms=win_perms,
                                         deny_perms=win_deny_perms,
                                         inheritance=win_inheritance)
    else:
        return __salt__['file.makedirs'](path=name,
                                         user=user,
                                         group=group,
                                         mode=dir_mode)


def hardlink(
        name,
        target,
        force=False,
        makedirs=False,
        user=None,
        group=None,
        dir_mode=None,
        **kwargs):
    '''
    Create a hard link
    If the file already exists and is a hard link pointing to any location other
    than the specified target, the hard link will be replaced. If the hard link
    is a regular file or directory then the state will return False. If the
    regular file is desired to be replaced with a hard link pass force: True

    name
        The location of the hard link to create
    target
        The location that the hard link points to
    force
        If the name of the hard link exists and force is set to False, the
        state will fail. If force is set to True, the file or directory in the
        way of the hard link file will be deleted to make room for the hard
        link, unless backupname is set, when it will be renamed
    makedirs
        If the location of the hard link does not already have a parent directory
        then the state will fail, setting makedirs to True will allow Salt to
        create the parent directory
    user
        The user to own any directories made if makedirs is set to true. This
        defaults to the user salt is running as on the minion
    group
        The group ownership set on any directories made if makedirs is set to
        true. This defaults to the group salt is running as on the minion. On
        Windows, this is ignored
    dir_mode
        If directories are to be created, passing this option specifies the
        permissions for those directories.
    '''
    name = os.path.expanduser(name)

    # Make sure that leading zeros stripped by YAML loader are added back
    dir_mode = salt.utils.files.normalize_mode(dir_mode)

    user = _test_owner(kwargs, user=user)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.hardlink')

    if user is None:
        user = __opts__['user']

    if salt.utils.is_windows():
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this '
                'is a Windows system.'.format(name)
            )
        group = user

    if group is None:
        group = __salt__['file.gid_to_group'](
            __salt__['user.info'](user).get('gid', 0)
        )

    preflight_errors = []
    uid = __salt__['file.user_to_uid'](user)
    gid = __salt__['file.group_to_gid'](group)

    if uid == '':
        preflight_errors.append('User {0} does not exist'.format(user))

    if gid == '':
        preflight_errors.append('Group {0} does not exist'.format(group))

    if not os.path.isabs(name):
        preflight_errors.append(
            'Specified file {0} is not an absolute path'.format(name)
        )

    if not os.path.isabs(target):
        preflight_errors.append(
            'Specified target {0} is not an absolute path'.format(target)
        )

    if preflight_errors:
        msg = '. '.join(preflight_errors)
        if len(preflight_errors) > 1:
            msg += '.'
        return _error(ret, msg)

    if __opts__['test']:
        presult, pcomment, pchanges = _hardlink_check(name, target, force)
        ret['result'] = presult
        ret['comment'] = pcomment
        ret['changes'] = pchanges
        return ret

    # We use zip_longest here because there's a number of issues in pylint's
    # tracker that complains about not linking the zip builtin.
    for direction, item in zip_longest(['to', 'from'], [name, target]):
        if os.path.isdir(item):
            msg = 'Unable to hard link {0} directory {1}'.format(direction, item)
            return _error(ret, msg)

    if not os.path.exists(target):
        msg = 'Target {0} for hard link does not exist'.format(target)
        return _error(ret, msg)

    # Check that the directory to write the hard link to exists
    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            __salt__['file.makedirs'](
                name,
                user=user,
                group=group,
                mode=dir_mode)

        else:
            return _error(
                ret,
                'Directory {0} for hard link is not present'.format(
                    os.path.dirname(name)
                )
            )

    # If file is not a hard link and we're actually overwriting it, then verify
    # that this was forced.
    if os.path.isfile(name) and not __salt__['file.is_hardlink'](name):

        # Remove whatever is in the way. This should then hit the else case
        # of the file.is_hardlink check below
        if force:
            os.remove(name)
            ret['changes']['forced'] = 'File for hard link was forcibly replaced'

        # Otherwise throw an error
        else:
            return _error(ret,
                          ('File exists where the hard link {0} should be'
                           .format(name)))

    # If the file is a hard link, then we can simply rewrite its target since
    # nothing is really being lost here.
    if __salt__['file.is_hardlink'](name):

        # If the inodes point to the same thing, then there's nothing to do
        # except for let the user know that this has already happened.
        if _hardlink_same(name, target):
            ret['result'] = True
            ret['comment'] = ('Target of hard link {0} is already pointing '
                                'to {1}'.format(name, target))
            return ret

        # First remove the old hard link since a reference to it already exists
        os.remove(name)

        # Now we can remake it
        try:
            __salt__['file.link'](target, name)

        # Or not...
        except CommandExecutionError as E:
            ret['result'] = False
            ret['comment'] = ('Unable to set target of hard link {0} -> '
                              '{1}: {2}'.format(name, target, E))
            return ret

        # Good to go
        ret['result'] = True
        ret['comment'] = 'Set target of hard link {0} -> {1}'.format(name, target)
        ret['changes']['new'] = name

    # The link is not present, so simply make it
    elif not os.path.exists(name):
        try:
            __salt__['file.link'](target, name)

        # Or not...
        except CommandExecutionError as E:
            ret['result'] = False
            ret['comment'] = ('Unable to create new hard link {0} -> '
                              '{1}: {2}'.format(name, target, E))
            return ret

        # Made a new hard link, things are ok
        ret['result'] = True
        ret['comment'] = 'Created new hard link {0} -> {1}'.format(name, target)
        ret['changes']['new'] = name

    return ret


def symlink(
        name,
        target,
        force=False,
        backupname=None,
        makedirs=False,
        user=None,
        group=None,
        mode=None,
        win_owner=None,
        win_perms=None,
        win_deny_perms=None,
        win_inheritance=None,
        **kwargs):
    '''
    Create a symbolic link (symlink, soft link)

    If the file already exists and is a symlink pointing to any location other
    than the specified target, the symlink will be replaced. If the symlink is
    a regular file or directory then the state will return False. If the
    regular file or directory is desired to be replaced with a symlink pass
    force: True, if it is to be renamed, pass a backupname.

    name
        The location of the symlink to create

    target
        The location that the symlink points to

    force
        If the name of the symlink exists and is not a symlink and
        force is set to False, the state will fail. If force is set to
        True, the file or directory in the way of the symlink file
        will be deleted to make room for the symlink, unless
        backupname is set, when it will be renamed

    backupname
        If the name of the symlink exists and is not a symlink, it will be
        renamed to the backupname. If the backupname already
        exists and force is False, the state will fail. Otherwise, the
        backupname will be removed first.
        An absolute path OR a basename file/directory name must be provided.
        The latter will be placed relative to the symlink destination's parent
        directory.

    makedirs
        If the location of the symlink does not already have a parent directory
        then the state will fail, setting makedirs to True will allow Salt to
        create the parent directory

    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

    group
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion. On Windows, this is ignored

    mode
        The permissions to set on this file, aka 644, 0775, 4664. Not supported
        on Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    win_owner : None
        The owner of the symlink and directories if ``makedirs`` is True. If
        this is not passed, ``user`` will be used. If ``user`` is not passed,
        the account under which Salt is running will be used.

        .. versionadded:: 2017.7.7

    win_perms : None
        A dictionary containing permissions to grant

        .. versionadded:: 2017.7.7

    win_deny_perms : None
        A dictionary containing permissions to deny

        .. versionadded:: 2017.7.7

    win_inheritance : None
        True to inherit permissions from parent, otherwise False

        .. versionadded:: 2017.7.7
    '''
    name = os.path.expanduser(name)

    # Make sure that leading zeros stripped by YAML loader are added back
    mode = salt.utils.files.normalize_mode(mode)

    user = _test_owner(kwargs, user=user)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.symlink')

    if user is None:
        user = __opts__['user']

    if salt.utils.platform.is_windows():

        # Make sure the user exists in Windows
        # Salt default is 'root'
        if not __salt__['user.info'](user):
            # User not found, use the account salt is running under
            # If username not found, use System
            user = __salt__['user.current']()
            if not user:
                user = 'SYSTEM'

        # If win_owner is not passed, use user
        if win_owner is None:
            win_owner = user if user else None

        # Group isn't relevant to Windows, use win_perms/win_deny_perms
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this '
                'is a Windows system. Please use the `win_*` parameters to set '
                'permissions in Windows.'.format(name)
            )
        group = user

    if group is None:
        group = __salt__['file.gid_to_group'](
            __salt__['user.info'](user).get('gid', 0)
        )

    preflight_errors = []
    if salt.utils.platform.is_windows():
        # Make sure the passed owner exists
        try:
            salt.utils.win_functions.get_sid_from_name(win_owner)
        except CommandExecutionError as exc:
            preflight_errors.append('User {0} does not exist'.format(win_owner))

        # Make sure users passed in win_perms exist
        if win_perms:
            for name_check in win_perms:
                try:
                    salt.utils.win_functions.get_sid_from_name(name_check)
                except CommandExecutionError as exc:
                    preflight_errors.append('User {0} does not exist'.format(name_check))

        # Make sure users passed in win_deny_perms exist
        if win_deny_perms:
            for name_check in win_deny_perms:
                try:
                    salt.utils.win_functions.get_sid_from_name(name_check)
                except CommandExecutionError as exc:
                    preflight_errors.append('User {0} does not exist'.format(name_check))
    else:
        uid = __salt__['file.user_to_uid'](user)
        gid = __salt__['file.group_to_gid'](group)

        if uid == '':
            preflight_errors.append('User {0} does not exist'.format(user))

        if gid == '':
            preflight_errors.append('Group {0} does not exist'.format(group))

    if not os.path.isabs(name):
        preflight_errors.append(
            'Specified file {0} is not an absolute path'.format(name)
        )

    if preflight_errors:
        msg = '. '.join(preflight_errors)
        if len(preflight_errors) > 1:
            msg += '.'
        return _error(ret, msg)

    presult, pcomment, pchanges = _symlink_check(name,
                                                 target,
                                                 force,
                                                 user,
                                                 group,
                                                 win_owner)

    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            if __opts__['test']:
                pcomment += '\n{0} will be created'.format(os.path.dirname(name))
            else:
                try:
                    _makedirs(name=name,
                              user=user,
                              group=group,
                              dir_mode=mode,
                              win_owner=win_owner,
                              win_perms=win_perms,
                              win_deny_perms=win_deny_perms,
                              win_inheritance=win_inheritance)
                except CommandExecutionError as exc:
                    return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
        else:
            if __opts__['test']:
                pcomment += '\nDirectory {0} for symlink is not present' \
                            ''.format(os.path.dirname(name))
            else:
                return _error(
                    ret,
                    'Directory {0} for symlink is not present'.format(
                        os.path.dirname(name)
                    )
                )

    if __opts__['test']:
        ret['result'] = presult
        ret['comment'] = pcomment
        ret['changes'] = pchanges
        return ret

    if __salt__['file.is_link'](name):
        # The link exists, verify that it matches the target
        if os.path.normpath(__salt__['file.readlink'](name)) != os.path.normpath(target):
            # The target is wrong, delete the link
            os.remove(name)
        else:
            if _check_symlink_ownership(name, user, group, win_owner):
                # The link looks good!
                if salt.utils.platform.is_windows():
                    ret['comment'] = ('Symlink {0} is present and owned by {1}'
                                      ''.format(name, win_owner))
                else:
                    ret['comment'] = ('Symlink {0} is present and owned by '
                                      '{1}:{2}'.format(name, user, group))
            else:
                if _set_symlink_ownership(name, user, group, win_owner):
                    if salt.utils.platform.is_windows():
                        ret['comment'] = ('Set ownership of symlink {0} to '
                                          '{1}'.format(name, win_owner))
                        ret['changes']['ownership'] = win_owner
                    else:
                        ret['comment'] = ('Set ownership of symlink {0} to '
                                          '{1}:{2}'.format(name, user, group))
                        ret['changes']['ownership'] = '{0}:{1}'.format(user,
                                                                       group)
                else:
                    ret['result'] = False
                    if salt.utils.platform.is_windows():
                        ret['comment'] += (
                            'Failed to set ownership of symlink '
                            '{0} to {1}'.format(name, win_owner))
                    else:
                        ret['comment'] += (
                            'Failed to set ownership of symlink {0} to '
                            '{1}:{2}'.format(name, user, group))
            return ret

    elif os.path.isfile(name) or os.path.isdir(name):
        # It is not a link, but a file or dir
        if backupname is not None:
            if not os.path.isabs(backupname):
                if backupname == os.path.basename(backupname):
                    backupname = os.path.join(
                        os.path.dirname(os.path.normpath(name)),
                        backupname)
                else:
                    return _error(ret, (('Backupname must be an absolute path '
                                         'or a file name: {0}').format(backupname)))
            # Make a backup first
            if os.path.lexists(backupname):
                if not force:
                    return _error(ret, (('Symlink & backup dest exists and Force not set.'
                                         ' {0} -> {1} - backup: {2}').format(
                                             name, target, backupname)))
                else:
                    __salt__['file.remove'](backupname)
            try:
                __salt__['file.move'](name, backupname)
            except Exception as exc:
                ret['changes'] = {}
                log.debug(
                    'Encountered error renaming %s to %s',
                    name, backupname, exc_info=True
                )
                return _error(ret, ('Unable to rename {0} to backup {1} -> '
                                    ': {2}'.format(name, backupname, exc)))
        elif force:
            # Remove whatever is in the way
            if __salt__['file.is_link'](name):
                __salt__['file.remove'](name)
                ret['changes']['forced'] = 'Symlink was forcibly replaced'
            else:
                __salt__['file.remove'](name)
        else:
            # Otherwise throw an error
            if os.path.isfile(name):
                return _error(ret,
                              ('File exists where the symlink {0} should be'
                               .format(name)))
            else:
                return _error(ret, ((
                                        'Directory exists where the symlink {0} should be'
                                    ).format(name)))

    if not os.path.exists(name):
        # The link is not present, make it
        try:
            __salt__['file.symlink'](target, name)
        except OSError as exc:
            ret['result'] = False
            ret['comment'] = ('Unable to create new symlink {0} -> '
                              '{1}: {2}'.format(name, target, exc))
            return ret
        else:
            ret['comment'] = ('Created new symlink {0} -> '
                              '{1}'.format(name, target))
            ret['changes']['new'] = name

        if not _check_symlink_ownership(name, user, group, win_owner):
            if not _set_symlink_ownership(name, user, group, win_owner):
                ret['result'] = False
                ret['comment'] += (', but was unable to set ownership to '
                                   '{0}:{1}'.format(user, group))
    return ret


def absent(name,
           **kwargs):
    '''
    Make sure that the named file or directory is absent. If it exists, it will
    be deleted. This will work to reverse any of the functions in the file
    state module. If a directory is supplied, it will be recursively deleted.

    name
        The path which should be deleted
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.absent')
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name)
        )
    if name == '/':
        return _error(ret, 'Refusing to make "/" absent')
    if os.path.isfile(name) or os.path.islink(name):
        if __opts__['test']:
            ret['result'] = None
            ret['changes']['removed'] = name
            ret['comment'] = 'File {0} is set for removal'.format(name)
            return ret
        try:
            if salt.utils.platform.is_windows():
                __salt__['file.remove'](name, force=True)
            else:
                __salt__['file.remove'](name)
            ret['comment'] = 'Removed file {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except CommandExecutionError as exc:
            return _error(ret, '{0}'.format(exc))

    elif os.path.isdir(name):
        if __opts__['test']:
            ret['result'] = None
            ret['changes']['removed'] = name
            ret['comment'] = 'Directory {0} is set for removal'.format(name)
            return ret
        try:
            if salt.utils.platform.is_windows():
                __salt__['file.remove'](name, force=True)
            else:
                __salt__['file.remove'](name)
            ret['comment'] = 'Removed directory {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except (OSError, IOError):
            return _error(ret, 'Failed to remove directory {0}'.format(name))

    ret['comment'] = 'File {0} is not present'.format(name)
    return ret


def tidied(name,
           age=0,
           matches=None,
           rmdirs=False,
           size=0,
           **kwargs):
    '''
    Remove unwanted files based on specific criteria. Multiple criteria
    are OR’d together, so a file that is too large but is not old enough
    will still get tidied.

    If neither age nor size is given all files which match a pattern in
    matches will be removed.

    name
        The directory tree that should be tidied

    age
        Maximum age in days after which files are considered for removal

    matches
        List of regular expressions to restrict what gets removed.  Default: ['.*']

    rmdirs
        Whether or not it's allowed to remove directories

    size
        Maximum allowed file size. Files greater or equal to this size are
        removed. Doesn't apply to directories or symbolic links

    .. code-block:: yaml

        cleanup:
          file.tidied:
            - name: /tmp/salt_test
            - rmdirs: True
            - matches:
              - foo
              - b.*r
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': True,
           'comment': ''}

    # Check preconditions
    if not os.path.isabs(name):
        return _error(ret, 'Specified file {0} is not an absolute path'.format(name))
    if not os.path.isdir(name):
        return _error(ret, '{0} does not exist or is not a directory.'.format(name))

    # Define some variables
    todelete = []
    today = date.today()

    # Compile regular expressions
    if matches is None:
        matches = ['.*']
    progs = []
    for regex in matches:
        progs.append(re.compile(regex))

    # Helper to match a given name against one or more pre-compiled regular
    # expressions
    def _matches(name):
        for prog in progs:
            if prog.match(name):
                return True
        return False

    # Iterate over given directory tree, depth-first
    for root, dirs, files in os.walk(top=name, topdown=False):
        # Check criteria for the found files and directories
        for elem in files + dirs:
            myage = 0
            mysize = 0
            deleteme = True
            path = os.path.join(root, elem)
            if os.path.islink(path):
                # Get age of symlink (not symlinked file)
                myage = abs(today - date.fromtimestamp(os.lstat(path).st_atime))
            elif elem in dirs:
                # Get age of directory, check if directories should be deleted at all
                myage = abs(today - date.fromtimestamp(os.path.getatime(path)))
                deleteme = rmdirs
            else:
                # Get age and size of regular file
                myage = abs(today - date.fromtimestamp(os.path.getatime(path)))
                mysize = os.path.getsize(path)
            # Verify against given criteria, collect all elements that should be removed
            if (mysize >= size or myage.days >= age) and _matches(name=elem) and deleteme:
                todelete.append(path)

    # Now delete the stuff
    if todelete:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = '{0} is set for tidy'.format(name)
            ret['changes'] = {'removed': todelete}
            return ret
        ret['changes']['removed'] = []
        # Iterate over collected items
        try:
            for path in todelete:
                if salt.utils.platform.is_windows():
                    __salt__['file.remove'](path, force=True)
                else:
                    __salt__['file.remove'](path)
                # Remember what we've removed, will appear in the summary
                ret['changes']['removed'].append(path)
        except CommandExecutionError as exc:
            return _error(ret, '{0}'.format(exc))
        # Set comment for the summary
        ret['comment'] = 'Removed {0} files or directories from directory {1}'.format(len(todelete), name)
    else:
        # Set comment in case there was nothing to remove
        ret['comment'] = 'Nothing to remove from directory {0}'.format(name)
    return ret


def exists(name,
           **kwargs):
    '''
    Verify that the named file or directory is present or exists.
    Ensures pre-requisites outside of Salt's purview
    (e.g., keytabs, private keys, etc.) have been previously satisfied before
    deployment.

    This function does not create the file if it doesn't exist, it will return
    an error.

    name
        Absolute path which must exist
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.exists')
    if not os.path.exists(name):
        return _error(ret, 'Specified path {0} does not exist'.format(name))

    ret['comment'] = 'Path {0} exists'.format(name)
    return ret


def missing(name,
            **kwargs):
    '''
    Verify that the named file or directory is missing, this returns True only
    if the named file is missing but does not remove the file if it is present.

    name
        Absolute path which must NOT exist
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.missing')
    if os.path.exists(name):
        return _error(ret, 'Specified path {0} exists'.format(name))

    ret['comment'] = 'Path {0} is missing'.format(name)
    return ret


def managed(name,
            source=None,
            source_hash='',
            source_hash_name=None,
            keep_source=True,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            template=None,
            makedirs=False,
            dir_mode=None,
            context=None,
            replace=True,
            defaults=None,
            backup='',
            show_changes=True,
            create=True,
            contents=None,
            tmp_dir='',
            tmp_ext='',
            contents_pillar=None,
            contents_grains=None,
            contents_newline=True,
            contents_delimiter=':',
            encoding=None,
            encoding_errors='strict',
            allow_empty=True,
            follow_symlinks=True,
            check_cmd=None,
            skip_verify=False,
            win_owner=None,
            win_perms=None,
            win_deny_perms=None,
            win_inheritance=True,
            win_perms_reset=False,
            **kwargs):
    r'''
    Manage a given file, this function allows for a file to be downloaded from
    the salt master and potentially run through a templating system.

    name
        The location of the file to manage, as an absolute path.

    source
        The source file to download to the minion, this source file can be
        hosted on either the salt master server (``salt://``), the salt minion
        local file system (``/``), or on an HTTP or FTP server (``http(s)://``,
        ``ftp://``).

        Both HTTPS and HTTP are supported as well as downloading directly
        from Amazon S3 compatible URLs with both pre-configured and automatic
        IAM credentials. (see s3.get state documentation)
        File retrieval from Openstack Swift object storage is supported via
        swift://container/object_path URLs, see swift.get documentation.
        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs. If source is left blank or None
        (use ~ in YAML), the file will be created as an empty file and
        the content will not be managed. This is also the case when a file
        already exists and the source is undefined; the contents of the file
        will not be changed or managed.

        If the file is hosted on a HTTP or FTP server then the source_hash
        argument is also required.

        A list of sources can also be passed in to provide a default source and
        a set of fallbacks. The first source in the list that is found to exist
        will be used and subsequent entries in the list will be ignored. Source
        list functionality only supports local files and remote files hosted on
        the salt master server or retrievable via HTTP, HTTPS, or FTP.

        .. code-block:: yaml

            file_override_example:
              file.managed:
                - source:
                  - salt://file_that_does_not_exist
                  - salt://file_that_exists

    source_hash
        This can be one of the following:
            1. a source hash string
            2. the URI of a file that contains source hash strings

        The function accepts the first encountered long unbroken alphanumeric
        string of correct length as a valid hash, in order from most secure to
        least secure:

        .. code-block:: text

            Type    Length
            ======  ======
            sha512     128
            sha384      96
            sha256      64
            sha224      56
            sha1        40
            md5         32

        **Using a Source Hash File**
            The file can contain several checksums for several files. Each line
            must contain both the file name and the hash.  If no file name is
            matched, the first hash encountered will be used, otherwise the most
            secure hash with the correct source file name will be used.

            When using a source hash file the source_hash argument needs to be a
            url, the standard download urls are supported, ftp, http, salt etc:

            Example:

            .. code-block:: yaml

                tomdroid-src-0.7.3.tar.gz:
                  file.managed:
                    - name: /tmp/tomdroid-src-0.7.3.tar.gz
                    - source: https://launchpad.net/tomdroid/beta/0.7.3/+download/tomdroid-src-0.7.3.tar.gz
                    - source_hash: https://launchpad.net/tomdroid/beta/0.7.3/+download/tomdroid-src-0.7.3.hash

            The following lines are all supported formats:

            .. code-block:: text

                /etc/rc.conf ef6e82e4006dee563d98ada2a2a80a27
                sha254c8525aee419eb649f0233be91c151178b30f0dff8ebbdcc8de71b1d5c8bcc06a  /etc/resolv.conf
                ead48423703509d37c4a90e6a0d53e143b6fc268

            Debian file type ``*.dsc`` files are also supported.

        **Inserting the Source Hash in the SLS Data**

        The source_hash can be specified as a simple checksum, like so:

        .. code-block:: yaml

            tomdroid-src-0.7.3.tar.gz:
              file.managed:
                - name: /tmp/tomdroid-src-0.7.3.tar.gz
                - source: https://launchpad.net/tomdroid/beta/0.7.3/+download/tomdroid-src-0.7.3.tar.gz
                - source_hash: 79eef25f9b0b2c642c62b7f737d4f53f

        .. note::
            Releases prior to 2016.11.0 must also include the hash type, like
            in the below example:

            .. code-block:: yaml

                tomdroid-src-0.7.3.tar.gz:
                  file.managed:
                    - name: /tmp/tomdroid-src-0.7.3.tar.gz
                    - source: https://launchpad.net/tomdroid/beta/0.7.3/+download/tomdroid-src-0.7.3.tar.gz
                    - source_hash: md5=79eef25f9b0b2c642c62b7f737d4f53f

        Known issues:
            If the remote server URL has the hash file as an apparent
            sub-directory of the source file, the module will discover that it
            has already cached a directory where a file should be cached. For
            example:

            .. code-block:: yaml

                tomdroid-src-0.7.3.tar.gz:
                  file.managed:
                    - name: /tmp/tomdroid-src-0.7.3.tar.gz
                    - source: https://launchpad.net/tomdroid/beta/0.7.3/+download/tomdroid-src-0.7.3.tar.gz
                    - source_hash: https://launchpad.net/tomdroid/beta/0.7.3/+download/tomdroid-src-0.7.3.tar.gz/+md5

    source_hash_name
        When ``source_hash`` refers to a hash file, Salt will try to find the
        correct hash by matching the filename/URI associated with that hash. By
        default, Salt will look for the filename being managed. When managing a
        file at path ``/tmp/foo.txt``, then the following line in a hash file
        would match:

        .. code-block:: text

            acbd18db4cc2f85cedef654fccc4a4d8    foo.txt

        However, sometimes a hash file will include multiple similar paths:

        .. code-block:: text

            37b51d194a7513e45b56f6524f2d51f2    ./dir1/foo.txt
            acbd18db4cc2f85cedef654fccc4a4d8    ./dir2/foo.txt
            73feffa4b7f6bb68e44cf984c85f6e88    ./dir3/foo.txt

        In cases like this, Salt may match the incorrect hash. This argument
        can be used to tell Salt which filename to match, to ensure that the
        correct hash is identified. For example:

        .. code-block:: yaml

            /tmp/foo.txt:
              file.managed:
                - source: https://mydomain.tld/dir2/foo.txt
                - source_hash: https://mydomain.tld/hashes
                - source_hash_name: ./dir2/foo.txt

        .. note::
            This argument must contain the full filename entry from the
            checksum file, as this argument is meant to disambiguate matches
            for multiple files that have the same basename. So, in the
            example above, simply using ``foo.txt`` would not match.

        .. versionadded:: 2016.3.5

    keep_source : True
        Set to ``False`` to discard the cached copy of the source file once the
        state completes. This can be useful for larger files to keep them from
        taking up space in minion cache. However, keep in mind that discarding
        the source file will result in the state needing to re-download the
        source file if the state is run again.

        .. versionadded:: 2017.7.3

    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

    group
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion. On Windows, this is ignored

    mode
        The permissions to set on this file, e.g. ``644``, ``0775``, or
        ``4664``.

        The default mode for new files and directories corresponds to the
        umask of the salt process. The mode of existing files and directories
        will only be changed if ``mode`` is specified.

        .. note::
            This option is **not** supported on Windows.

        .. versionchanged:: 2016.11.0
            This option can be set to ``keep``, and Salt will keep the mode
            from the Salt fileserver. This is only supported when the
            ``source`` URL begins with ``salt://``, or for files local to the
            minion. Because the ``source`` option cannot be used with any of
            the ``contents`` options, setting the ``mode`` to ``keep`` is also
            incompatible with the ``contents`` options.

        .. note:: keep does not work with salt-ssh.

            As a consequence of how the files are transferred to the minion, and
            the inability to connect back to the master with salt-ssh, salt is
            unable to stat the file as it exists on the fileserver and thus
            cannot mirror the mode on the salt-ssh minion

    attrs
        The attributes to have on this file, e.g. ``a``, ``i``. The attributes
        can be any or a combination of the following characters:
        ``aAcCdDeijPsStTu``.

        .. note::
            This option is **not** supported on Windows.

        .. versionadded:: 2018.3.0

    template
        If this setting is applied, the named templating engine will be used to
        render the downloaded file. The following templates are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    makedirs : False
        If set to ``True``, then the parent directories will be created to
        facilitate the creation of the named file. If ``False``, and the parent
        directory of the destination file doesn't exist, the state will fail.

    dir_mode
        If directories are to be created, passing this option specifies the
        permissions for those directories. If this is not set, directories
        will be assigned permissions by adding the execute bit to the mode of
        the files.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    replace : True
        If set to ``False`` and the file already exists, the file will not be
        modified even if changes would otherwise be made. Permissions and
        ownership will still be enforced, however.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    backup
        Overrides the default backup mode for this specific file. See
        :ref:`backup_mode documentation <file-state-backups>` for more details.

    show_changes
        Output a unified diff of the old file and the new file. If ``False``
        return a boolean if any changes were made.

    create : True
        If set to ``False``, then the file will only be managed if the file
        already exists on the system.

    contents
        Specify the contents of the file. Cannot be used in combination with
        ``source``. Ignores hashes and does not use a templating engine.

        This value can be either a single string, a multiline YAML string or a
        list of strings.  If a list of strings, then the strings will be joined
        together with newlines in the resulting file. For example, the below
        two example states would result in identical file contents:

        .. code-block:: yaml

            /path/to/file1:
              file.managed:
                - contents:
                  - This is line 1
                  - This is line 2

            /path/to/file2:
              file.managed:
                - contents: |
                    This is line 1
                    This is line 2


    contents_pillar
        .. versionadded:: 0.17.0
        .. versionchanged:: 2016.11.0
            contents_pillar can also be a list, and the pillars will be
            concatenated together to form one file.


        Operates like ``contents``, but draws from a value stored in pillar,
        using the pillar path syntax used in :mod:`pillar.get
        <salt.modules.pillar.get>`. This is useful when the pillar value
        contains newlines, as referencing a pillar variable using a jinja/mako
        template can result in YAML formatting issues due to the newlines
        causing indentation mismatches.

        For example, the following could be used to deploy an SSH private key:

        .. code-block:: yaml

            /home/deployer/.ssh/id_rsa:
              file.managed:
                - user: deployer
                - group: deployer
                - mode: 600
                - attrs: a
                - contents_pillar: userdata:deployer:id_rsa

        This would populate ``/home/deployer/.ssh/id_rsa`` with the contents of
        ``pillar['userdata']['deployer']['id_rsa']``. An example of this pillar
        setup would be like so:

        .. code-block:: yaml

            userdata:
              deployer:
                id_rsa: |
                    -----BEGIN RSA PRIVATE KEY-----
                    MIIEowIBAAKCAQEAoQiwO3JhBquPAalQF9qP1lLZNXVjYMIswrMe2HcWUVBgh+vY
                    U7sCwx/dH6+VvNwmCoqmNnP+8gTPKGl1vgAObJAnMT623dMXjVKwnEagZPRJIxDy
                    B/HaAre9euNiY3LvIzBTWRSeMfT+rWvIKVBpvwlgGrfgz70m0pqxu+UyFbAGLin+
                    GpxzZAMaFpZw4sSbIlRuissXZj/sHpQb8p9M5IeO4Z3rjkCP1cxI
                    -----END RSA PRIVATE KEY-----

        .. note::
            The private key above is shortened to keep the example brief, but
            shows how to do multiline string in YAML. The key is followed by a
            pipe character, and the multiline string is indented two more
            spaces.

            To avoid the hassle of creating an indented multiline YAML string,
            the :mod:`file_tree external pillar <salt.pillar.file_tree>` can
            be used instead. However, this will not work for binary files in
            Salt releases before 2015.8.4.

    contents_grains
        .. versionadded:: 2014.7.0

        Operates like ``contents``, but draws from a value stored in grains,
        using the grains path syntax used in :mod:`grains.get
        <salt.modules.grains.get>`. This functionality works similarly to
        ``contents_pillar``, but with grains.

        For example, the following could be used to deploy a "message of the day"
        file:

        .. code-block:: yaml

            write_motd:
              file.managed:
                - name: /etc/motd
                - contents_grains: motd

        This would populate ``/etc/motd`` file with the contents of the ``motd``
        grain. The ``motd`` grain is not a default grain, and would need to be
        set prior to running the state:

        .. code-block:: bash

            salt '*' grains.set motd 'Welcome! This system is managed by Salt.'

    contents_newline : True
        .. versionadded:: 2014.7.0
        .. versionchanged:: 2015.8.4
            This option is now ignored if the contents being deployed contain
            binary data.

        If ``True``, files managed using ``contents``, ``contents_pillar``, or
        ``contents_grains`` will have a newline added to the end of the file if
        one is not present. Setting this option to ``False`` will omit this
        final newline.

    contents_delimiter
        .. versionadded:: 2015.8.4

        Can be used to specify an alternate delimiter for ``contents_pillar``
        or ``contents_grains``. This delimiter will be passed through to
        :py:func:`pillar.get <salt.modules.pillar.get>` or :py:func:`grains.get
        <salt.modules.grains.get>` when retrieving the contents.

    encoding
        If specified, then the specified encoding will be used. Otherwise, the
        file will be encoded using the system locale (usually UTF-8). See
        https://docs.python.org/3/library/codecs.html#standard-encodings for
        the list of available encodings.

        .. versionadded:: 2017.7.0

    encoding_errors : 'strict'
        Error encoding scheme. Default is ```'strict'```.
        See https://docs.python.org/2/library/codecs.html#codec-base-classes
        for the list of available schemes.

        .. versionadded:: 2017.7.0

    allow_empty : True
        .. versionadded:: 2015.8.4

        If set to ``False``, then the state will fail if the contents specified
        by ``contents_pillar`` or ``contents_grains`` are empty.

    follow_symlinks : True
        .. versionadded:: 2014.7.0

        If the desired path is a symlink follow it and make changes to the
        file to which the symlink points.

    check_cmd
        .. versionadded:: 2014.7.0

        The specified command will be run with an appended argument of a
        *temporary* file containing the new managed contents.  If the command
        exits with a zero status the new managed contents will be written to
        the managed destination. If the command exits with a nonzero exit
        code, the state will fail and no changes will be made to the file.

        For example, the following could be used to verify sudoers before making
        changes:

        .. code-block:: yaml

            /etc/sudoers:
              file.managed:
                - user: root
                - group: root
                - mode: 0440
                - attrs: i
                - source: salt://sudoers/files/sudoers.jinja
                - template: jinja
                - check_cmd: /usr/sbin/visudo -c -f

        **NOTE**: This ``check_cmd`` functions differently than the requisite
        ``check_cmd``.

    tmp_dir
        Directory for temp file created by ``check_cmd``. Useful for checkers
        dependent on config file location (e.g. daemons restricted to their
        own config directories by an apparmor profile).

        .. code-block:: yaml

            /etc/dhcp/dhcpd.conf:
              file.managed:
                - user: root
                - group: root
                - mode: 0755
                - tmp_dir: '/etc/dhcp'
                - contents: "# Managed by Salt"
                - check_cmd: dhcpd -t -cf

    tmp_ext
        Suffix for temp file created by ``check_cmd``. Useful for checkers
        dependent on config file extension (e.g. the init-checkconf upstart
        config checker).

        .. code-block:: yaml

            /etc/init/test.conf:
              file.managed:
                - user: root
                - group: root
                - mode: 0440
                - tmp_ext: '.conf'
                - contents:
                  - 'description "Salt Minion"'
                  - 'start on started mountall'
                  - 'stop on shutdown'
                  - 'respawn'
                  - 'exec salt-minion'
                - check_cmd: init-checkconf -f

    skip_verify : False
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``) will be skipped, and the ``source_hash``
        argument will be ignored.

        .. versionadded:: 2016.3.0

    win_owner : None
        The owner of the directory. If this is not passed, user will be used. If
        user is not passed, the account under which Salt is running will be
        used.

        .. versionadded:: 2017.7.0

    win_perms : None
        A dictionary containing permissions to grant and their propagation. For
        example: ``{'Administrators': {'perms': 'full_control'}}`` Can be a
        single basic perm or a list of advanced perms. ``perms`` must be
        specified. ``applies_to`` does not apply to file objects.

        .. versionadded:: 2017.7.0

    win_deny_perms : None
        A dictionary containing permissions to deny and their propagation. For
        example: ``{'Administrators': {'perms': 'full_control'}}`` Can be a
        single basic perm or a list of advanced perms. ``perms`` must be
        specified. ``applies_to`` does not apply to file objects.

        .. versionadded:: 2017.7.0

    win_inheritance : True
        True to inherit permissions from the parent directory, False not to
        inherit permission.

        .. versionadded:: 2017.7.0

    win_perms_reset : False
        If ``True`` the existing DACL will be cleared and replaced with the
        settings defined in this function. If ``False``, new entries will be
        appended to the existing DACL. Default is ``False``.

        .. versionadded:: 2018.3.0

    Here's an example using the above ``win_*`` parameters:

    .. code-block:: yaml

        create_config_file:
          file.managed:
            - name: C:\config\settings.cfg
            - source: salt://settings.cfg
            - win_owner: Administrators
            - win_perms:
                # Basic Permissions
                dev_ops:
                  perms: full_control
                # List of advanced permissions
                appuser:
                  perms:
                    - read_attributes
                    - read_ea
                    - create_folders
                    - read_permissions
                joe_snuffy:
                  perms: read
            - win_deny_perms:
                fred_snuffy:
                  perms: full_control
            - win_inheritance: False
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    name = os.path.expanduser(name)

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if not name:
        return _error(ret, 'Destination file name is required')

    if mode is not None and salt.utils.platform.is_windows():
        return _error(ret, 'The \'mode\' option is not supported on Windows')

    if attrs is not None and salt.utils.platform.is_windows():
        return _error(ret, 'The \'attrs\' option is not supported on Windows')

    try:
        keep_mode = mode.lower() == 'keep'
        if keep_mode:
            # We're not hard-coding the mode, so set it to None
            mode = None
    except AttributeError:
        keep_mode = False

    # Make sure that any leading zeros stripped by YAML loader are added back
    mode = salt.utils.files.normalize_mode(mode)

    contents_count = len(
        [x for x in (contents, contents_pillar, contents_grains)
         if x is not None]
    )

    if source and contents_count > 0:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'contents\', '
            '\'contents_pillar\', or \'contents_grains\''
        )
    elif keep_mode and contents_count > 0:
        return _error(
            ret,
            'Mode preservation cannot be used in combination with \'contents\', '
            '\'contents_pillar\', or \'contents_grains\''
        )
    elif contents_count > 1:
        return _error(
            ret,
            'Only one of \'contents\', \'contents_pillar\', and '
            '\'contents_grains\' is permitted'
        )

    # If no source is specified, set replace to False, as there is nothing
    # with which to replace the file.
    if not source and contents_count == 0 and replace:
        replace = False
        log.warning(
            'State for file: {0} - Neither \'source\' nor \'contents\' nor '
            '\'contents_pillar\' nor \'contents_grains\' was defined, yet '
            '\'replace\' was set to \'True\'. As there is no source to '
            'replace the file with, \'replace\' has been set to \'False\' to '
            'avoid reading the file unnecessarily.'.format(name)
        )

    if 'file_mode' in kwargs:
        ret.setdefault('warnings', []).append(
            'The \'file_mode\' argument will be ignored.  '
            'Please use \'mode\' instead to set file permissions.'
        )

    # Use this below to avoid multiple '\0' checks and save some CPU cycles
    if contents_pillar is not None:
        if isinstance(contents_pillar, list):
            list_contents = []
            for nextp in contents_pillar:
                nextc = __salt__['pillar.get'](nextp, __NOT_FOUND,
                                               delimiter=contents_delimiter)
                if nextc is __NOT_FOUND:
                    return _error(
                        ret,
                        'Pillar {0} does not exist'.format(nextp)
                    )
                list_contents.append(nextc)
            use_contents = os.linesep.join(list_contents)
        else:
            use_contents = __salt__['pillar.get'](contents_pillar, __NOT_FOUND,
                                                  delimiter=contents_delimiter)
            if use_contents is __NOT_FOUND:
                return _error(
                    ret,
                    'Pillar {0} does not exist'.format(contents_pillar)
                )

    elif contents_grains is not None:
        if isinstance(contents_grains, list):
            list_contents = []
            for nextg in contents_grains:
                nextc = __salt__['grains.get'](nextg, __NOT_FOUND,
                                               delimiter=contents_delimiter)
                if nextc is __NOT_FOUND:
                    return _error(
                        ret,
                        'Grain {0} does not exist'.format(nextc)
                    )
                list_contents.append(nextc)
            use_contents = os.linesep.join(list_contents)
        else:
            use_contents = __salt__['grains.get'](contents_grains, __NOT_FOUND,
                                                  delimiter=contents_delimiter)
            if use_contents is __NOT_FOUND:
                return _error(
                    ret,
                    'Grain {0} does not exist'.format(contents_grains)
                )

    elif contents is not None:
        use_contents = contents

    else:
        use_contents = None

    if use_contents is not None:
        if not allow_empty and not use_contents:
            if contents_pillar:
                contents_id = 'contents_pillar {0}'.format(contents_pillar)
            elif contents_grains:
                contents_id = 'contents_grains {0}'.format(contents_grains)
            else:
                contents_id = '\'contents\''
            return _error(
                ret,
                '{0} value would result in empty contents. Set allow_empty '
                'to True to allow the managed file to be empty.'
                .format(contents_id)
            )

        try:
            validated_contents = _validate_str_list(use_contents, encoding=encoding)
            if not validated_contents:
                return _error(
                    ret,
                    'Contents specified by contents/contents_pillar/'
                    'contents_grains is not a string or list of strings, and '
                    'is not binary data. SLS is likely malformed.'
                )
            contents = ''
            for part in validated_contents:
                for line in part.splitlines():
                    contents += line.rstrip('\n').rstrip('\r') + os.linesep
            if contents_newline and not contents.endswith(os.linesep):
                contents += os.linesep
        except UnicodeDecodeError:
            # Either something terrible happened, or we have binary data.
            if template:
                return _error(
                    ret,
                    'Contents specified by contents/contents_pillar/'
                    'contents_grains appears to be binary data, and'
                    ' as will not be able to be treated as a Jinja'
                    ' template.'
                )
            contents = use_contents
        if template:
            contents = __salt__['file.apply_template_on_contents'](
                contents,
                template=template,
                context=context,
                defaults=defaults,
                saltenv=__env__)
            if not isinstance(contents, six.string_types):
                if 'result' in contents:
                    ret['result'] = contents['result']
                else:
                    ret['result'] = False
                if 'comment' in contents:
                    ret['comment'] = contents['comment']
                else:
                    ret['comment'] = 'Error while applying template on contents'
                return ret

    user = _test_owner(kwargs, user=user)
    if salt.utils.platform.is_windows():

        # If win_owner not passed, use user
        if win_owner is None:
            win_owner = user if user else None

        # Group isn't relevant to Windows, use win_perms/win_deny_perms
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this is '
                'a Windows system. Please use the `win_*` parameters to set '
                'permissions in Windows.'.format(name)
            )
        group = user

    if not create:
        if not os.path.isfile(name):
            # Don't create a file that is not already present
            ret['comment'] = ('File {0} is not present and is not set for '
                              'creation').format(name)
            return ret
    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if os.path.isdir(name):
        ret['comment'] = 'Specified target {0} is a directory'.format(name)
        ret['result'] = False
        return ret

    if context is None:
        context = {}
    elif not isinstance(context, dict):
        return _error(
            ret, 'Context must be formed as a dict')
    if defaults and not isinstance(defaults, dict):
        return _error(
            ret, 'Defaults must be formed as a dict')

    if not replace and os.path.exists(name):
        ret_perms = {}
        # Check and set the permissions if necessary
        if salt.utils.platform.is_windows():
            ret = __salt__['file.check_perms'](
                path=name,
                ret=ret,
                owner=win_owner,
                grant_perms=win_perms,
                deny_perms=win_deny_perms,
                inheritance=win_inheritance,
                reset=win_perms_reset)
        else:
            ret, ret_perms = __salt__['file.check_perms'](
                name, ret, user, group, mode, attrs, follow_symlinks)
        if __opts__['test']:
            if isinstance(ret_perms, dict) and \
               'lmode' in ret_perms and \
               mode != ret_perms['lmode']:
                ret['comment'] = ('File {0} will be updated with permissions '
                                  '{1} from its current '
                                  'state of {2}'.format(name,
                                                        mode,
                                                        ret_perms['lmode']))
            else:
                ret['comment'] = 'File {0} not updated'.format(name)
        elif not ret['changes'] and ret['result']:
            ret['comment'] = ('File {0} exists with proper permissions. '
                              'No changes made.'.format(name))
        return ret

    accum_data, _ = _load_accumulators()
    if name in accum_data:
        if not context:
            context = {}
        context['accumulator'] = accum_data[name]

    try:
        if __opts__['test']:
            if 'file.check_managed_changes' in __salt__:
                ret['changes'] = __salt__['file.check_managed_changes'](
                    name,
                    source,
                    source_hash,
                    source_hash_name,
                    user,
                    group,
                    mode,
                    attrs,
                    template,
                    context,
                    defaults,
                    __env__,
                    contents,
                    skip_verify,
                    keep_mode,
                    **kwargs
                )

                if salt.utils.platform.is_windows():
                    try:
                        ret = __salt__['file.check_perms'](
                            path=name,
                            ret=ret,
                            owner=win_owner,
                            grant_perms=win_perms,
                            deny_perms=win_deny_perms,
                            inheritance=win_inheritance,
                            reset=win_perms_reset)
                    except CommandExecutionError as exc:
                        if exc.strerror.startswith('Path not found'):
                            ret['changes']['newfile'] = name

            if isinstance(ret['changes'], tuple):
                ret['result'], ret['comment'] = ret['changes']
            elif ret['changes']:
                ret['result'] = None
                ret['comment'] = 'The file {0} is set to be changed'.format(name)
                ret['comment'] += ('\nNote: No changes made, actual changes may\n'
                                   'be different due to other states.')
                if 'diff' in ret['changes'] and not show_changes:
                    ret['changes']['diff'] = '<show_changes=False>'
            else:
                ret['result'] = True
                ret['comment'] = 'The file {0} is in the correct state'.format(name)

            return ret

        # If the source is a list then find which file exists
        source, source_hash = __salt__['file.source_list'](
            source,
            source_hash,
            __env__
        )
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = 'Unable to manage file: {0}'.format(exc)
        return ret

    # Gather the source file from the server
    try:
        sfn, source_sum, comment_ = __salt__['file.get_managed'](
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            attrs,
            __env__,
            context,
            defaults,
            skip_verify,
            **kwargs
        )
    except Exception as exc:
        ret['changes'] = {}
        log.debug(traceback.format_exc())
        return _error(ret, 'Unable to manage file: {0}'.format(exc))

    tmp_filename = None

    if check_cmd:
        tmp_filename = salt.utils.files.mkstemp(suffix=tmp_ext, dir=tmp_dir)

        # if exists copy existing file to tmp to compare
        if __salt__['file.file_exists'](name):
            try:
                __salt__['file.copy'](name, tmp_filename)
            except Exception as exc:
                return _error(
                    ret,
                    'Unable to copy file {0} to {1}: {2}'.format(
                        name, tmp_filename, exc
                    )
                )

        try:
            ret = __salt__['file.manage_file'](
                tmp_filename,
                sfn,
                ret,
                source,
                source_sum,
                user,
                group,
                mode,
                attrs,
                __env__,
                backup,
                makedirs,
                template,
                show_changes,
                contents,
                dir_mode,
                follow_symlinks,
                skip_verify,
                keep_mode,
                win_owner=win_owner,
                win_perms=win_perms,
                win_deny_perms=win_deny_perms,
                win_inheritance=win_inheritance,
                win_perms_reset=win_perms_reset,
                encoding=encoding,
                encoding_errors=encoding_errors,
                **kwargs)
        except Exception as exc:
            ret['changes'] = {}
            log.debug(traceback.format_exc())
            salt.utils.files.remove(tmp_filename)
            if not keep_source:
                if not sfn \
                        and source \
                        and _urlparse(source).scheme == 'salt':
                    # The file would not have been cached until manage_file was
                    # run, so check again here for a cached copy.
                    sfn = __salt__['cp.is_cached'](source, __env__)
                if sfn:
                    salt.utils.files.remove(sfn)
            return _error(ret, 'Unable to check_cmd file: {0}'.format(exc))

        # file being updated to verify using check_cmd
        if ret['changes']:
            # Reset ret
            ret = {'changes': {},
                   'comment': '',
                   'name': name,
                   'result': True}

            check_cmd_opts = {}
            if 'shell' in __grains__:
                check_cmd_opts['shell'] = __grains__['shell']

            cret = mod_run_check_cmd(check_cmd, tmp_filename, **check_cmd_opts)
            if isinstance(cret, dict):
                ret.update(cret)
                salt.utils.files.remove(tmp_filename)
                return ret

            # Since we generated a new tempfile and we are not returning here
            # lets change the original sfn to the new tempfile or else we will
            # get file not found

            sfn = tmp_filename

        else:
            ret = {'changes': {},
                   'comment': '',
                   'name': name,
                   'result': True}

    if comment_ and contents is None:
        return _error(ret, comment_)
    else:
        try:
            return __salt__['file.manage_file'](
                name,
                sfn,
                ret,
                source,
                source_sum,
                user,
                group,
                mode,
                attrs,
                __env__,
                backup,
                makedirs,
                template,
                show_changes,
                contents,
                dir_mode,
                follow_symlinks,
                skip_verify,
                keep_mode,
                win_owner=win_owner,
                win_perms=win_perms,
                win_deny_perms=win_deny_perms,
                win_inheritance=win_inheritance,
                win_perms_reset=win_perms_reset,
                encoding=encoding,
                encoding_errors=encoding_errors,
                **kwargs)
        except Exception as exc:
            ret['changes'] = {}
            log.debug(traceback.format_exc())
            return _error(ret, 'Unable to manage file: {0}'.format(exc))
        finally:
            if tmp_filename:
                salt.utils.files.remove(tmp_filename)
            if not keep_source:
                if not sfn \
                        and source \
                        and _urlparse(source).scheme == 'salt':
                    # The file would not have been cached until manage_file was
                    # run, so check again here for a cached copy.
                    sfn = __salt__['cp.is_cached'](source, __env__)
                if sfn:
                    salt.utils.files.remove(sfn)


_RECURSE_TYPES = ['user', 'group', 'mode', 'ignore_files', 'ignore_dirs']


def _get_recurse_set(recurse):
    '''
    Converse *recurse* definition to a set of strings.

    Raises TypeError or ValueError when *recurse* has wrong structure.
    '''
    if not recurse:
        return set()
    if not isinstance(recurse, list):
        raise TypeError('"recurse" must be formed as a list of strings')
    try:
        recurse_set = set(recurse)
    except TypeError:  # non-hashable elements
        recurse_set = None
    if recurse_set is None or not set(_RECURSE_TYPES) >= recurse_set:
        raise ValueError('Types for "recurse" limited to {0}.'.format(
            ', '.join('"{0}"'.format(rtype) for rtype in _RECURSE_TYPES)))
    if 'ignore_files' in recurse_set and 'ignore_dirs' in recurse_set:
        raise ValueError('Must not specify "recurse" options "ignore_files"'
                         ' and "ignore_dirs" at the same time.')
    return recurse_set


def _depth_limited_walk(top, max_depth=None):
    '''
    Walk the directory tree under root up till reaching max_depth.
    With max_depth=None (default), do not limit depth.
    '''
    for root, dirs, files in salt.utils.path.os_walk(top):
        if max_depth is not None:
            rel_depth = root.count(os.path.sep) - top.count(os.path.sep)
            if rel_depth >= max_depth:
                del dirs[:]
        yield (six.text_type(root), list(dirs), list(files))


def directory(name,
              user=None,
              group=None,
              recurse=None,
              max_depth=None,
              dir_mode=None,
              file_mode=None,
              makedirs=False,
              clean=False,
              require=None,
              exclude_pat=None,
              follow_symlinks=False,
              force=False,
              backupname=None,
              allow_symlink=True,
              children_only=False,
              win_owner=None,
              win_perms=None,
              win_deny_perms=None,
              win_inheritance=True,
              win_perms_reset=False,
              **kwargs):
    r'''
    Ensure that a named directory is present and has the right perms

    name
        The location to create or manage a directory, as an absolute path

    user
        The user to own the directory; this defaults to the user salt is
        running as on the minion

    group
        The group ownership set for the directory; this defaults to the group
        salt is running as on the minion. On Windows, this is ignored

    recurse
        Enforce user/group ownership and mode of directory recursively. Accepts
        a list of strings representing what you would like to recurse.  If
        ``mode`` is defined, will recurse on both ``file_mode`` and ``dir_mode`` if
        they are defined.  If ``ignore_files`` or ``ignore_dirs`` is included, files or
        directories will be left unchanged respectively.
        Example:

        .. code-block:: yaml

            /var/log/httpd:
              file.directory:
                - user: root
                - group: root
                - dir_mode: 755
                - file_mode: 644
                - recurse:
                  - user
                  - group
                  - mode

        Leave files or directories unchanged:

        .. code-block:: yaml

            /var/log/httpd:
              file.directory:
                - user: root
                - group: root
                - dir_mode: 755
                - file_mode: 644
                - recurse:
                  - user
                  - group
                  - mode
                  - ignore_dirs

        .. versionadded:: 2015.5.0

    max_depth
        Limit the recursion depth. The default is no limit=None.
        'max_depth' and 'clean' are mutually exclusive.

        .. versionadded:: 2016.11.0

    dir_mode / mode
        The permissions mode to set any directories created. Not supported on
        Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    file_mode
        The permissions mode to set any files created if 'mode' is run in
        'recurse'. This defaults to dir_mode. Not supported on Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    makedirs
        If the directory is located in a path without a parent directory, then
        the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.

    clean
        Make sure that only files that are set up by salt and required by this
        function are kept. If this option is set then everything in this
        directory will be deleted unless it is required.
        'clean' and 'max_depth' are mutually exclusive.

    require
        Require other resources such as packages or files

    exclude_pat
        When 'clean' is set to True, exclude this pattern from removal list
        and preserve in the destination.

    follow_symlinks : False
        If the desired path is a symlink (or ``recurse`` is defined and a
        symlink is encountered while recursing), follow it and check the
        permissions of the directory/file to which the symlink points.

        .. versionadded:: 2014.1.4

    force
        If the name of the directory exists and is not a directory and
        force is set to False, the state will fail. If force is set to
        True, the file in the way of the directory will be deleted to
        make room for the directory, unless backupname is set,
        then it will be renamed.

        .. versionadded:: 2014.7.0

    backupname
        If the name of the directory exists and is not a directory, it will be
        renamed to the backupname. If the backupname already
        exists and force is False, the state will fail. Otherwise, the
        backupname will be removed first.

        .. versionadded:: 2014.7.0

    allow_symlink : True
        If allow_symlink is True and the specified path is a symlink, it will be
        allowed to remain if it points to a directory. If allow_symlink is False
        then the state will fail, unless force is also set to True, in which case
        it will be removed or renamed, depending on the value of the backupname
        argument.

        .. versionadded:: 2014.7.0

    children_only : False
        If children_only is True the base of a path is excluded when performing
        a recursive operation. In case of /path/to/base, base will be ignored
        while all of /path/to/base/* are still operated on.

    win_owner : None
        The owner of the directory. If this is not passed, user will be used. If
        user is not passed, the account under which Salt is running will be
        used.

        .. versionadded:: 2017.7.0

    win_perms : None
        A dictionary containing permissions to grant and their propagation. For
        example: ``{'Administrators': {'perms': 'full_control', 'applies_to':
        'this_folder_only'}}`` Can be a single basic perm or a list of advanced
        perms. ``perms`` must be specified. ``applies_to`` is optional and
        defaults to ``this_folder_subfolder_files``.

        .. versionadded:: 2017.7.0

    win_deny_perms : None
        A dictionary containing permissions to deny and their propagation. For
        example: ``{'Administrators': {'perms': 'full_control', 'applies_to':
        'this_folder_only'}}`` Can be a single basic perm or a list of advanced
        perms.

        .. versionadded:: 2017.7.0

    win_inheritance : True
        True to inherit permissions from the parent directory, False not to
        inherit permission.

        .. versionadded:: 2017.7.0

    win_perms_reset : False
        If ``True`` the existing DACL will be cleared and replaced with the
        settings defined in this function. If ``False``, new entries will be
        appended to the existing DACL. Default is ``False``.

        .. versionadded:: 2018.3.0

    Here's an example using the above ``win_*`` parameters:

    .. code-block:: yaml

        create_config_dir:
          file.directory:
            - name: 'C:\config\'
            - win_owner: Administrators
            - win_perms:
                # Basic Permissions
                dev_ops:
                  perms: full_control
                # List of advanced permissions
                appuser:
                  perms:
                    - read_attributes
                    - read_ea
                    - create_folders
                    - read_permissions
                  applies_to: this_folder_only
                joe_snuffy:
                  perms: read
                  applies_to: this_folder_files
            - win_deny_perms:
                fred_snuffy:
                  perms: full_control
            - win_inheritance: False
    '''
    name = os.path.expanduser(name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.directory')
    # Remove trailing slash, if present and we're not working on "/" itself
    if name[-1] == '/' and name != '/':
        name = name[:-1]

    if max_depth is not None and clean:
        return _error(ret, 'Cannot specify both max_depth and clean')

    user = _test_owner(kwargs, user=user)
    if salt.utils.platform.is_windows():

        # If win_owner not passed, use user
        if win_owner is None:
            win_owner = user if user else salt.utils.win_functions.get_current_user()

        # Group isn't relevant to Windows, use win_perms/win_deny_perms
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this is '
                'a Windows system. Please use the `win_*` parameters to set '
                'permissions in Windows.'.format(name)
            )
        group = user

    if 'mode' in kwargs and not dir_mode:
        dir_mode = kwargs.get('mode', [])

    if not file_mode:
        file_mode = dir_mode

    # Make sure that leading zeros stripped by YAML loader are added back
    dir_mode = salt.utils.files.normalize_mode(dir_mode)
    file_mode = salt.utils.files.normalize_mode(file_mode)

    if salt.utils.platform.is_windows():
        # Verify win_owner is valid on the target system
        try:
            salt.utils.win_dacl.get_sid(win_owner)
        except CommandExecutionError as exc:
            return _error(ret, exc)
    else:
        # Verify user and group are valid
        u_check = _check_user(user, group)
        if u_check:
            # The specified user or group do not exist
            return _error(ret, u_check)

    # Must be an absolute path
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    # Check for existing file or symlink
    if os.path.isfile(name) or (not allow_symlink and os.path.islink(name)) \
       or (force and os.path.islink(name)):
        # Was a backupname specified
        if backupname is not None:
            # Make a backup first
            if os.path.lexists(backupname):
                if not force:
                    return _error(ret, ((
                                            'File exists where the backup target {0} should go'
                                        ).format(backupname)))
                else:
                    __salt__['file.remove'](backupname)
            os.rename(name, backupname)
        elif force:
            # Remove whatever is in the way
            if os.path.isfile(name):
                if __opts__['test']:
                    ret['changes']['forced'] = 'File would be forcibly replaced'
                else:
                    os.remove(name)
                    ret['changes']['forced'] = 'File was forcibly replaced'
            elif __salt__['file.is_link'](name):
                if __opts__['test']:
                    ret['changes']['forced'] = 'Symlink would be forcibly replaced'
                else:
                    __salt__['file.remove'](name)
                    ret['changes']['forced'] = 'Symlink was forcibly replaced'
            else:
                if __opts__['test']:
                    ret['changes']['forced'] = 'Directory would be forcibly replaced'
                else:
                    __salt__['file.remove'](name)
                    ret['changes']['forced'] = 'Directory was forcibly replaced'
        else:
            if os.path.isfile(name):
                return _error(
                    ret,
                    'Specified location {0} exists and is a file'.format(name))
            elif os.path.islink(name):
                return _error(
                    ret,
                    'Specified location {0} exists and is a symlink'.format(name))

    # Check directory?
    if salt.utils.platform.is_windows():
        presult, pcomment, pchanges = _check_directory_win(
            name=name,
            win_owner=win_owner,
            win_perms=win_perms,
            win_deny_perms=win_deny_perms,
            win_inheritance=win_inheritance,
            win_perms_reset=win_perms_reset)
    else:
        presult, pcomment, pchanges = _check_directory(
            name, user, group, recurse or [], dir_mode, file_mode, clean,
            require, exclude_pat, max_depth, follow_symlinks)

    if pchanges:
        ret['changes'].update(pchanges)

    # Don't run through the reset of the function if there are no changes to be
    # made
    if __opts__['test'] or not ret['changes']:
        ret['result'] = presult
        ret['comment'] = pcomment
        return ret

    if not os.path.isdir(name):
        # The dir does not exist, make it
        if not os.path.isdir(os.path.dirname(name)):
            # The parent directory does not exist, create them
            if makedirs:
                # Everything's good, create the parent Dirs
                try:
                    _makedirs(name=name,
                              user=user,
                              group=group,
                              dir_mode=dir_mode,
                              win_owner=win_owner,
                              win_perms=win_perms,
                              win_deny_perms=win_deny_perms,
                              win_inheritance=win_inheritance)
                except CommandExecutionError as exc:
                    return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
            else:
                return _error(
                    ret, 'No directory to create {0} in'.format(name))

        if salt.utils.platform.is_windows():
            __salt__['file.mkdir'](
                path=name,
                owner=win_owner,
                grant_perms=win_perms,
                deny_perms=win_deny_perms,
                inheritance=win_inheritance,
                reset=win_perms_reset)
        else:
            __salt__['file.mkdir'](name, user=user, group=group, mode=dir_mode)

        ret['changes'][name] = 'New Dir'

    if not os.path.isdir(name):
        return _error(ret, 'Failed to create directory {0}'.format(name))

    # issue 32707: skip this __salt__['file.check_perms'] call if children_only == True
    # Check permissions
    if not children_only:
        if salt.utils.platform.is_windows():
            ret = __salt__['file.check_perms'](
                path=name,
                ret=ret,
                owner=win_owner,
                grant_perms=win_perms,
                deny_perms=win_deny_perms,
                inheritance=win_inheritance,
                reset=win_perms_reset)
        else:
            ret, perms = __salt__['file.check_perms'](
                name, ret, user, group, dir_mode, None, follow_symlinks)

    errors = []
    if recurse or clean:
        # walk path only once and store the result
        walk_l = list(_depth_limited_walk(name, max_depth))
        # root: (dirs, files) structure, compatible for python2.6
        walk_d = {}
        for i in walk_l:
            walk_d[i[0]] = (i[1], i[2])

    recurse_set = None
    if recurse:
        try:
            recurse_set = _get_recurse_set(recurse)
        except (TypeError, ValueError) as exc:
            ret['result'] = False
            ret['comment'] = '{0}'.format(exc)
            # NOTE: Should this be enough to stop the whole check altogether?
    if recurse_set:
        if 'user' in recurse_set:
            if user or isinstance(user, int):
                uid = __salt__['file.user_to_uid'](user)
                # file.user_to_uid returns '' if user does not exist. Above
                # check for user is not fatal, so we need to be sure user
                # exists.
                if isinstance(uid, six.string_types):
                    ret['result'] = False
                    ret['comment'] = 'Failed to enforce ownership for ' \
                                     'user {0} (user does not ' \
                                     'exist)'.format(user)
            else:
                ret['result'] = False
                ret['comment'] = 'user not specified, but configured as ' \
                                 'a target for recursive ownership ' \
                                 'management'
        else:
            user = None
        if 'group' in recurse_set:
            if group or isinstance(group, int):
                gid = __salt__['file.group_to_gid'](group)
                # As above with user, we need to make sure group exists.
                if isinstance(gid, six.string_types):
                    ret['result'] = False
                    ret['comment'] = 'Failed to enforce group ownership ' \
                                     'for group {0}'.format(group)
            else:
                ret['result'] = False
                ret['comment'] = 'group not specified, but configured ' \
                                 'as a target for recursive ownership ' \
                                 'management'
        else:
            group = None

        if 'mode' not in recurse_set:
            file_mode = None
            dir_mode = None

        check_files = 'ignore_files' not in recurse_set
        check_dirs = 'ignore_dirs' not in recurse_set

        for root, dirs, files in walk_l:
            if check_files:
                for fn_ in files:
                    full = os.path.join(root, fn_)
                    try:
                        if salt.utils.platform.is_windows():
                            ret = __salt__['file.check_perms'](
                                path=full,
                                ret=ret,
                                owner=win_owner,
                                grant_perms=win_perms,
                                deny_perms=win_deny_perms,
                                inheritance=win_inheritance,
                                reset=win_perms_reset)
                        else:
                            ret, _ = __salt__['file.check_perms'](
                                full, ret, user, group, file_mode, None, follow_symlinks)
                    except CommandExecutionError as exc:
                        if not exc.strerror.startswith('Path not found'):
                            errors.append(exc.strerror)

            if check_dirs:
                for dir_ in dirs:
                    full = os.path.join(root, dir_)
                    try:
                        if salt.utils.platform.is_windows():
                            ret = __salt__['file.check_perms'](
                                path=full,
                                ret=ret,
                                owner=win_owner,
                                grant_perms=win_perms,
                                deny_perms=win_deny_perms,
                                inheritance=win_inheritance,
                                reset=win_perms_reset)
                        else:
                            ret, _ = __salt__['file.check_perms'](
                                full, ret, user, group, dir_mode, None, follow_symlinks)
                    except CommandExecutionError as exc:
                        if not exc.strerror.startswith('Path not found'):
                            errors.append(exc.strerror)

    if clean:
        keep = _gen_keep_files(name, require, walk_d)
        log.debug('List of kept files when use file.directory with clean: %s',
                  keep)
        removed = _clean_dir(name, list(keep), exclude_pat)
        if removed:
            ret['changes']['removed'] = removed
            ret['comment'] = 'Files cleaned from directory {0}'.format(name)

    # issue 32707: reflect children_only selection in comments
    if not ret['comment']:
        if children_only:
            ret['comment'] = 'Directory {0}/* updated'.format(name)
        else:
            if ret['changes']:
                ret['comment'] = 'Directory {0} updated'.format(name)

    if __opts__['test']:
        ret['comment'] = 'Directory {0} not updated'.format(name)
    elif not ret['changes'] and ret['result']:
        orig_comment = None
        if ret['comment']:
            orig_comment = ret['comment']

        ret['comment'] = 'Directory {0} is in the correct state'.format(name)
        if orig_comment:
            ret['comment'] = '\n'.join([ret['comment'], orig_comment])

    if errors:
        ret['result'] = False
        ret['comment'] += '\n\nThe following errors were encountered:\n'
        for error in errors:
            ret['comment'] += '\n- {0}'.format(error)

    return ret


def recurse(name,
            source,
            keep_source=True,
            clean=False,
            require=None,
            user=None,
            group=None,
            dir_mode=None,
            file_mode=None,
            sym_mode=None,
            template=None,
            context=None,
            replace=True,
            defaults=None,
            include_empty=False,
            backup='',
            include_pat=None,
            exclude_pat=None,
            maxdepth=None,
            keep_symlinks=False,
            force_symlinks=False,
            win_owner=None,
            win_perms=None,
            win_deny_perms=None,
            win_inheritance=True,
            **kwargs):
    '''
    Recurse through a subdirectory on the master and copy said subdirectory
    over to the specified path.

    name
        The directory to set the recursion in

    source
        The source directory, this directory is located on the salt master file
        server and is specified with the salt:// protocol. If the directory is
        located on the master in the directory named spam, and is called eggs,
        the source string is salt://spam/eggs

    keep_source : True
        Set to ``False`` to discard the cached copy of the source file once the
        state completes. This can be useful for larger files to keep them from
        taking up space in minion cache. However, keep in mind that discarding
        the source file will result in the state needing to re-download the
        source file if the state is run again.

        .. versionadded:: 2017.7.3

    clean
        Make sure that only files that are set up by salt and required by this
        function are kept. If this option is set then everything in this
        directory will be deleted unless it is required.

    require
        Require other resources such as packages or files

    user
        The user to own the directory. This defaults to the user salt is
        running as on the minion

    group
        The group ownership set for the directory. This defaults to the group
        salt is running as on the minion. On Windows, this is ignored

    dir_mode
        The permissions mode to set on any directories created.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

        .. note::
            This option is **not** supported on Windows.

    file_mode
        The permissions mode to set on any files created.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

        .. note::
            This option is **not** supported on Windows.

        .. versionchanged:: 2016.11.0
            This option can be set to ``keep``, and Salt will keep the mode
            from the Salt fileserver. This is only supported when the
            ``source`` URL begins with ``salt://``, or for files local to the
            minion. Because the ``source`` option cannot be used with any of
            the ``contents`` options, setting the ``mode`` to ``keep`` is also
            incompatible with the ``contents`` options.

    sym_mode
        The permissions mode to set on any symlink created.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

        .. note::
            This option is **not** supported on Windows.

    template
        If this setting is applied, the named templating engine will be used to
        render the downloaded file. The following templates are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

        .. note::

            The template option is required when recursively applying templates.

    replace : True
        If set to ``False`` and the file already exists, the file will not be
        modified even if changes would otherwise be made. Permissions and
        ownership will still be enforced, however.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    include_empty
        Set this to True if empty directories should also be created
        (default is False)

    backup
        Overrides the default backup mode for all replaced files. See
        :ref:`backup_mode documentation <file-state-backups>` for more details.

    include_pat
        When copying, include only this pattern from the source. Default
        is glob match; if prefixed with 'E@', then regexp match.
        Example:

        .. code-block:: text

          - include_pat: hello*       :: glob matches 'hello01', 'hello02'
                                         ... but not 'otherhello'
          - include_pat: E@hello      :: regexp matches 'otherhello',
                                         'hello01' ...

    exclude_pat
        Exclude this pattern from the source when copying. If both
        `include_pat` and `exclude_pat` are supplied, then it will apply
        conditions cumulatively. i.e. first select based on include_pat, and
        then within that result apply exclude_pat.

        Also, when 'clean=True', exclude this pattern from the removal
        list and preserve in the destination.
        Example:

        .. code-block:: text

          - exclude_pat: APPDATA*               :: glob matches APPDATA.01,
                                                   APPDATA.02,.. for exclusion
          - exclude_pat: E@(APPDATA)|(TEMPDATA) :: regexp matches APPDATA
                                                   or TEMPDATA for exclusion

    maxdepth
        When copying, only copy paths which are of depth `maxdepth` from the
        source path.
        Example:

        .. code-block:: text

          - maxdepth: 0      :: Only include files located in the source
                                directory
          - maxdepth: 1      :: Only include files located in the source
                                or immediate subdirectories

    keep_symlinks
        Keep symlinks when copying from the source. This option will cause
        the copy operation to terminate at the symlink. If desire behavior
        similar to rsync, then set this to True.

    force_symlinks
        Force symlink creation. This option will force the symlink creation.
        If a file or directory is obstructing symlink creation it will be
        recursively removed so that symlink creation can proceed. This
        option is usually not needed except in special circumstances.

    win_owner : None
        The owner of the symlink and directories if ``makedirs`` is True. If
        this is not passed, ``user`` will be used. If ``user`` is not passed,
        the account under which Salt is running will be used.

        .. versionadded:: 2017.7.7

    win_perms : None
        A dictionary containing permissions to grant

        .. versionadded:: 2017.7.7

    win_deny_perms : None
        A dictionary containing permissions to deny

        .. versionadded:: 2017.7.7

    win_inheritance : None
        True to inherit permissions from parent, otherwise False

        .. versionadded:: 2017.7.7
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    name = os.path.expanduser(salt.utils.data.decode(name))

    user = _test_owner(kwargs, user=user)
    if salt.utils.platform.is_windows():
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this '
                'is a Windows system.'.format(name)
            )
        group = user
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': {}  # { path: [comment, ...] }
    }

    if 'mode' in kwargs:
        ret['result'] = False
        ret['comment'] = (
            '\'mode\' is not allowed in \'file.recurse\'. Please use '
            '\'file_mode\' and \'dir_mode\'.'
        )
        return ret

    if any([x is not None for x in (dir_mode, file_mode, sym_mode)]) \
            and salt.utils.platform.is_windows():
        return _error(ret, 'mode management is not supported on Windows')

    # Make sure that leading zeros stripped by YAML loader are added back
    dir_mode = salt.utils.files.normalize_mode(dir_mode)

    try:
        keep_mode = file_mode.lower() == 'keep'
        if keep_mode:
            # We're not hard-coding the mode, so set it to None
            file_mode = None
    except AttributeError:
        keep_mode = False

    file_mode = salt.utils.files.normalize_mode(file_mode)

    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    # expand source into source_list
    source_list = _validate_str_list(source)

    for idx, val in enumerate(source_list):
        source_list[idx] = val.rstrip('/')

    for precheck in source_list:
        if not precheck.startswith('salt://'):
            return _error(ret, ('Invalid source \'{0}\' '
                                '(must be a salt:// URI)'.format(precheck)))

    # Select the first source in source_list that exists
    try:
        source, source_hash = __salt__['file.source_list'](source_list, '', __env__)
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = 'Recurse failed: {0}'.format(exc)
        return ret

    # Check source path relative to fileserver root, make sure it is a
    # directory
    srcpath, senv = salt.utils.url.parse(source)
    if senv is None:
        senv = __env__
    master_dirs = __salt__['cp.list_master_dirs'](saltenv=senv)
    if srcpath not in master_dirs \
            and not any((x for x in master_dirs
                         if x.startswith(srcpath + '/'))):
        ret['result'] = False
        ret['comment'] = (
            'The directory \'{0}\' does not exist on the salt fileserver '
            'in saltenv \'{1}\''.format(srcpath, senv)
        )
        return ret

    # Verify the target directory
    if not os.path.isdir(name):
        if os.path.exists(name):
            # it is not a dir, but it exists - fail out
            return _error(
                ret, 'The path {0} exists and is not a directory'.format(name))
        if not __opts__['test']:
            if salt.utils.platform.is_windows():
                win_owner = win_owner if win_owner else user
                __salt__['file.makedirs_perms'](path=name,
                                                owner=win_owner,
                                                grant_perms=win_perms,
                                                deny_perms=win_deny_perms,
                                                inheritance=win_inheritance)
            else:
                __salt__['file.makedirs_perms'](name=name,
                                                user=user,
                                                group=group,
                                                mode=dir_mode)

    def add_comment(path, comment):
        comments = ret['comment'].setdefault(path, [])
        if isinstance(comment, six.string_types):
            comments.append(comment)
        else:
            comments.extend(comment)

    def merge_ret(path, _ret):
        # Use the most "negative" result code (out of True, None, False)
        if _ret['result'] is False or ret['result'] is True:
            ret['result'] = _ret['result']

        # Only include comments about files that changed
        if _ret['result'] is not True and _ret['comment']:
            add_comment(path, _ret['comment'])

        if _ret['changes']:
            ret['changes'][path] = _ret['changes']

    def manage_file(path, source, replace):
        if clean and os.path.exists(path) and os.path.isdir(path) and replace:
            _ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
            if __opts__['test']:
                _ret['comment'] = 'Replacing directory {0} with a ' \
                                  'file'.format(path)
                _ret['result'] = None
                merge_ret(path, _ret)
                return
            else:
                __salt__['file.remove'](path)
                _ret['changes'] = {'diff': 'Replaced directory with a '
                                           'new file'}
                merge_ret(path, _ret)

        # Conflicts can occur if some kwargs are passed in here
        pass_kwargs = {}
        faults = ['mode', 'makedirs']
        for key in kwargs:
            if key not in faults:
                pass_kwargs[key] = kwargs[key]

        _ret = managed(
            path,
            source=source,
            keep_source=keep_source,
            user=user,
            group=group,
            mode='keep' if keep_mode else file_mode,
            attrs=None,
            template=template,
            makedirs=True,
            replace=replace,
            context=context,
            defaults=defaults,
            backup=backup,
            **pass_kwargs)
        merge_ret(path, _ret)

    def manage_directory(path):
        if os.path.basename(path) == '..':
            return
        if clean and os.path.exists(path) and not os.path.isdir(path):
            _ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
            if __opts__['test']:
                _ret['comment'] = 'Replacing {0} with a directory'.format(path)
                _ret['result'] = None
                merge_ret(path, _ret)
                return
            else:
                __salt__['file.remove'](path)
                _ret['changes'] = {'diff': 'Replaced file with a directory'}
                merge_ret(path, _ret)

        _ret = directory(
            path,
            user=user,
            group=group,
            recurse=[],
            dir_mode=dir_mode,
            file_mode=None,
            makedirs=True,
            clean=False,
            require=None)
        merge_ret(path, _ret)

    mng_files, mng_dirs, mng_symlinks, keep = _gen_recurse_managed_files(
        name,
        source,
        keep_symlinks,
        include_pat,
        exclude_pat,
        maxdepth,
        include_empty)

    for srelpath, ltarget in mng_symlinks:
        _ret = symlink(os.path.join(name, srelpath),
                       ltarget,
                       makedirs=True,
                       force=force_symlinks,
                       user=user,
                       group=group,
                       mode=sym_mode)
        if not _ret:
            continue
        merge_ret(os.path.join(name, srelpath), _ret)
    for dirname in mng_dirs:
        manage_directory(dirname)
    for dest, src in mng_files:
        manage_file(dest, src, replace)

    if clean:
        # TODO: Use directory(clean=True) instead
        keep.update(_gen_keep_files(name, require))
        removed = _clean_dir(name, list(keep), exclude_pat)
        if removed:
            if __opts__['test']:
                if ret['result']:
                    ret['result'] = None
                add_comment('removed', removed)
            else:
                ret['changes']['removed'] = removed

    # Flatten comments until salt command line client learns
    # to display structured comments in a readable fashion
    ret['comment'] = '\n'.join('\n#### {0} ####\n{1}'.format(
        k, v if isinstance(v, six.string_types) else '\n'.join(v)
    ) for (k, v) in six.iteritems(ret['comment'])).strip()

    if not ret['comment']:
        ret['comment'] = 'Recursively updated {0}'.format(name)

    if not ret['changes'] and ret['result']:
        ret['comment'] = 'The directory {0} is in the correct state'.format(
            name
        )

    return ret


def retention_schedule(name, retain, strptime_format=None, timezone=None):
    '''
    Apply retention scheduling to backup storage directory.

    .. versionadded:: 2016.11.0

    :param name:
        The filesystem path to the directory containing backups to be managed.

    :param retain:
        Delete the backups, except for the ones we want to keep.
        The N below should be an integer but may also be the special value of ``all``,
        which keeps all files matching the criteria.
        All of the retain options default to None,
        which means to not keep files based on this criteria.

        :most_recent N:
            Keep the most recent N files.

        :first_of_hour N:
            For the last N hours from now, keep the first file after the hour.

        :first_of_day N:
            For the last N days from now, keep the first file after midnight.
            See also ``timezone``.

        :first_of_week N:
            For the last N weeks from now, keep the first file after Sunday midnight.

        :first_of_month N:
            For the last N months from now, keep the first file after the start of the month.

        :first_of_year N:
            For the last N years from now, keep the first file after the start of the year.

    :param strptime_format:
        A python strptime format string used to first match the filenames of backups
        and then parse the filename to determine the datetime of the file.
        https://docs.python.org/2/library/datetime.html#datetime.datetime.strptime
        Defaults to None, which considers all files in the directory to be backups eligible for deletion
        and uses ``os.path.getmtime()`` to determine the datetime.

    :param timezone:
        The timezone to use when determining midnight.
        This is only used when datetime is pulled from ``os.path.getmtime()``.
        Defaults to ``None`` which uses the timezone from the locale.

    Usage example:

    .. code-block:: yaml

        /var/backups/example_directory:
          file.retention_schedule:
            - retain:
                most_recent: 5
                first_of_hour: 4
                first_of_day: 7
                first_of_week: 6    # NotImplemented yet.
                first_of_month: 6
                first_of_year: all
            - strptime_format: example_name_%Y%m%dT%H%M%S.tar.bz2
            - timezone: None

    '''
    name = os.path.expanduser(name)
    ret = {'name': name,
           'changes': {'retained': [], 'deleted': [], 'ignored': []},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.retention_schedule')
    if not os.path.isdir(name):
        return _error(ret, 'Name provided to file.retention must be a directory')

    # get list of files in directory
    all_files = __salt__['file.readdir'](name)

    # if strptime_format is set, filter through the list to find names which parse and get their datetimes.
    beginning_of_unix_time = datetime(1970, 1, 1)

    def get_file_time_from_strptime(f):
        try:
            ts = datetime.strptime(f, strptime_format)
            ts_epoch = salt.utils.dateutils.total_seconds(ts - beginning_of_unix_time)
            return (ts, ts_epoch)
        except ValueError:
            # Files which don't match the pattern are not relevant files.
            return (None, None)

    def get_file_time_from_mtime(f):
        if f == '.' or f == '..':
            return (None, None)
        lstat = __salt__['file.lstat'](os.path.join(name, f))
        if lstat:
            mtime = lstat['st_mtime']
            return (datetime.fromtimestamp(mtime, timezone), mtime)
        else:   # maybe it was deleted since we did the readdir?
            return (None, None)

    get_file_time = get_file_time_from_strptime if strptime_format else get_file_time_from_mtime

    # data structures are nested dicts:
    # files_by_ymd = year.month.day.hour.unixtime: filename
    # files_by_y_week_dow = year.week_of_year.day_of_week.unixtime: filename
    # http://the.randomengineer.com/2015/04/28/python-recursive-defaultdict/
    # TODO: move to an ordered dict model and reduce the number of sorts in the rest of the code?
    def dict_maker():
        return defaultdict(dict_maker)
    files_by_ymd = dict_maker()
    files_by_y_week_dow = dict_maker()
    relevant_files = set()
    ignored_files = set()
    for f in all_files:
        ts, ts_epoch = get_file_time(f)
        if ts:
            files_by_ymd[ts.year][ts.month][ts.day][ts.hour][ts_epoch] = f
            week_of_year = ts.isocalendar()[1]
            files_by_y_week_dow[ts.year][week_of_year][ts.weekday()][ts_epoch] = f
            relevant_files.add(f)
        else:
            ignored_files.add(f)

    # This is tightly coupled with the file_with_times data-structure above.
    RETAIN_TO_DEPTH = {
        'first_of_year': 1,
        'first_of_month': 2,
        'first_of_day': 3,
        'first_of_hour': 4,
        'most_recent': 5,
    }

    def get_first(fwt):
        if isinstance(fwt, dict):
            first_sub_key = sorted(fwt.keys())[0]
            return get_first(fwt[first_sub_key])
        else:
            return set([fwt, ])

    def get_first_n_at_depth(fwt, depth, n):
        if depth <= 0:
            return get_first(fwt)
        else:
            result_set = set()
            for k in sorted(fwt.keys(), reverse=True):
                needed = n - len(result_set)
                if needed < 1:
                    break
                result_set |= get_first_n_at_depth(fwt[k], depth - 1, needed)
            return result_set

    # for each retain criteria, add filenames which match the criteria to the retain set.
    retained_files = set()
    for retention_rule, keep_count in retain.items():
        # This is kind of a hack, since 'all' should really mean all,
        # but I think it's a large enough number that even modern filesystems would
        # choke if they had this many files in a single directory.
        keep_count = sys.maxsize if 'all' == keep_count else int(keep_count)
        if 'first_of_week' == retention_rule:
            first_of_week_depth = 2   # year + week_of_year = 2
            # I'm adding 1 to keep_count below because it fixed an off-by one
            # issue in the tests. I don't understand why, and that bothers me.
            retained_files |= get_first_n_at_depth(files_by_y_week_dow,
                                                   first_of_week_depth,
                                                   keep_count + 1)
        else:
            retained_files |= get_first_n_at_depth(files_by_ymd,
                                                   RETAIN_TO_DEPTH[retention_rule],
                                                   keep_count)

    deletable_files = list(relevant_files - retained_files)
    deletable_files.sort(reverse=True)
    changes = {
            'retained': sorted(list(retained_files), reverse=True),
            'deleted': deletable_files,
            'ignored': sorted(list(ignored_files), reverse=True),
        }
    ret['changes'] = changes

    # TODO: track and report how much space was / would be reclaimed
    if __opts__['test']:
        ret['comment'] = '{0} backups would have been removed from {1}.\n'.format(len(deletable_files), name)
        if deletable_files:
            ret['result'] = None
    else:
        for f in deletable_files:
            __salt__['file.remove'](os.path.join(name, f))
        ret['comment'] = '{0} backups were removed from {1}.\n'.format(len(deletable_files), name)
        ret['changes'] = changes

    return ret


def line(name, content=None, match=None, mode=None, location=None,
         before=None, after=None, show_changes=True, backup=False,
         quiet=False, indent=True, create=False, user=None,
         group=None, file_mode=None):
    '''
    Line-based editing of a file.

    .. versionadded:: 2015.8.0

    :param name:
        Filesystem path to the file to be edited.

    :param content:
        Content of the line. Allowed to be empty if mode=delete.

    :param match:
        Match the target line for an action by
        a fragment of a string or regular expression.

        If neither ``before`` nor ``after`` are provided, and ``match``
        is also ``None``, match becomes the ``content`` value.

    :param mode:
        Defines how to edit a line. One of the following options is
        required:

        - ensure
            If line does not exist, it will be added.
        - replace
            If line already exists, it will be replaced.
        - delete
            Delete the line, once found.
        - insert
            Insert a line.

        .. note::

            If ``mode=insert`` is used, at least one of the following
            options must also be defined: ``location``, ``before``, or
            ``after``. If ``location`` is used, it takes precedence
            over the other two options.

    :param location:
        Defines where to place content in the line. Note this option is only
        used when ``mode=insert`` is specified. If a location is passed in, it
        takes precedence over both the ``before`` and ``after`` kwargs. Valid
        locations are:

        - start
            Place the content at the beginning of the file.
        - end
            Place the content at the end of the file.

    :param before:
        Regular expression or an exact case-sensitive fragment of the string.
        This option is only used when either the ``ensure`` or ``insert`` mode
        is defined.

    :param after:
        Regular expression or an exact case-sensitive fragment of the string.
        This option is only used when either the ``ensure`` or ``insert`` mode
        is defined.

    :param show_changes:
        Output a unified diff of the old file and the new file.
        If ``False`` return a boolean if any changes were made.
        Default is ``True``

        .. note::
            Using this option will store two copies of the file in-memory
            (the original version and the edited version) in order to generate the diff.

    :param backup:
        Create a backup of the original file with the extension:
        "Year-Month-Day-Hour-Minutes-Seconds".

    :param quiet:
        Do not raise any exceptions. E.g. ignore the fact that the file that is
        tried to be edited does not exist and nothing really happened.

    :param indent:
        Keep indentation with the previous line. This option is not considered when
        the ``delete`` mode is specified.

    :param create:
        Create an empty file if doesn't exists.

        .. versionadded:: 2016.11.0

    :param user:
        The user to own the file, this defaults to the user salt is running as
        on the minion.

        .. versionadded:: 2016.11.0

    :param group:
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion On Windows, this is ignored.

        .. versionadded:: 2016.11.0

    :param file_mode:
        The permissions to set on this file, aka 644, 0775, 4664. Not supported
        on Windows.

        .. versionadded:: 2016.11.0

    If an equal sign (``=``) appears in an argument to a Salt command, it is
    interpreted as a keyword argument in the format of ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: yaml

       update_config:
         file.line:
           - name: /etc/myconfig.conf
           - mode: ensure
           - content: my key = my value
           - before: somekey.*?

    '''
    name = os.path.expanduser(name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.line')

    managed(
        name,
        create=create,
        user=user,
        group=group,
        mode=file_mode,
        replace=False)

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    # We've set the content to be empty in the function params but we want to make sure
    # it gets passed when needed. Feature #37092
    mode = mode and mode.lower() or mode
    if mode is None:
        return _error(ret, 'Mode was not defined. How to process the file?')

    modeswithemptycontent = ['delete']
    if mode not in modeswithemptycontent and content is None:
        return _error(ret, 'Content can only be empty if mode is {0}'.format(modeswithemptycontent))
    del modeswithemptycontent

    changes = __salt__['file.line'](
        name, content, match=match, mode=mode, location=location,
        before=before, after=after, show_changes=show_changes,
        backup=backup, quiet=quiet, indent=indent)
    if changes:
        ret['changes']['diff'] = changes
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Changes would be made'
        else:
            ret['result'] = True
            ret['comment'] = 'Changes were made'
    else:
        ret['result'] = True
        ret['comment'] = 'No changes needed to be made'

    return ret


def replace(name,
            pattern,
            repl,
            count=0,
            flags=8,
            bufsize=1,
            append_if_not_found=False,
            prepend_if_not_found=False,
            not_found_content=None,
            backup='.bak',
            show_changes=True,
            ignore_if_missing=False,
            backslash_literal=False):
    r'''
    Maintain an edit in a file.

    .. versionadded:: 0.17.0

    name
        Filesystem path to the file to be edited. If a symlink is specified, it
        will be resolved to its target.

    pattern
        A regular expression, to be matched using Python's
        :py:func:`re.search`.

        .. note::

            If you need to match a literal string that contains regex special
            characters, you may want to use salt's custom Jinja filter,
            ``regex_escape``.

            .. code-block:: jinja

                {{ 'http://example.com?foo=bar%20baz' | regex_escape }}

    repl
        The replacement text

    count
        Maximum number of pattern occurrences to be replaced.  Defaults to 0.
        If count is a positive integer n, no more than n occurrences will be
        replaced, otherwise all occurrences will be replaced.

    flags
        A list of flags defined in the ``re`` module documentation from the
        Python standard library. Each list item should be a string that will
        correlate to the human-friendly flag name. E.g., ``['IGNORECASE',
        'MULTILINE']``.  Optionally, ``flags`` may be an int, with a value
        corresponding to the XOR (``|``) of all the desired flags. Defaults to
        ``8`` (which equates to ``['MULTILINE']``).

        .. note::

            ``file.replace`` reads the entire file as a string to support
            multiline regex patterns. Therefore, when using anchors such as
            ``^`` or ``$`` in the pattern, those anchors may be relative to
            the line OR relative to the file. The default for ``file.replace``
            is to treat anchors as relative to the line, which is implemented
            by setting the default value of ``flags`` to ``['MULTILINE']``.
            When overriding the default value for ``flags``, if
            ``'MULTILINE'`` is not present then anchors will be relative to
            the file. If the desired behavior is for anchors to be relative to
            the line, then simply add ``'MULTILINE'`` to the list of flags.

    bufsize
        How much of the file to buffer into memory at once. The default value
        ``1`` processes one line at a time. The special value ``file`` may be
        specified which will read the entire file into memory before
        processing.

    append_if_not_found : False
        If set to ``True``, and pattern is not found, then the content will be
        appended to the file.

        .. versionadded:: 2014.7.0

    prepend_if_not_found : False
        If set to ``True`` and pattern is not found, then the content will be
        prepended to the file.

        .. versionadded:: 2014.7.0

    not_found_content
        Content to use for append/prepend if not found. If ``None`` (default),
        uses ``repl``. Useful when ``repl`` uses references to group in
        pattern.

        .. versionadded:: 2014.7.0

    backup
        The file extension to use for a backup of the file before editing. Set
        to ``False`` to skip making a backup.

    show_changes : True
        Output a unified diff of the old file and the new file. If ``False``
        return a boolean if any changes were made. Returns a boolean or a
        string.

        .. note:
            Using this option will store two copies of the file in memory (the
            original version and the edited version) in order to generate the
            diff. This may not normally be a concern, but could impact
            performance if used with large files.

    ignore_if_missing : False
        .. versionadded:: 2016.3.4

        Controls what to do if the file is missing. If set to ``False``, the
        state will display an error raised by the execution module. If set to
        ``True``, the state will simply report no changes.

    backslash_literal : False
        .. versionadded:: 2016.11.7

        Interpret backslashes as literal backslashes for the repl and not
        escape characters.  This will help when using append/prepend so that
        the backslashes are not interpreted for the repl on the second run of
        the state.

    For complex regex patterns, it can be useful to avoid the need for complex
    quoting and escape sequences by making use of YAML's multiline string
    syntax.

    .. code-block:: yaml

        complex_search_and_replace:
          file.replace:
            # <...snip...>
            - pattern: |
                CentOS \(2.6.32[^\\n]+\\n\s+root[^\\n]+\\n\)+

    .. note::

       When using YAML multiline string syntax in ``pattern:``, make sure to
       also use that syntax in the ``repl:`` part, or you might loose line
       feeds.

    When regex capture groups are used in ``pattern:``, their captured value is
    available for reuse in the ``repl:`` part as a backreference (ex. ``\1``).

    .. code-block:: yaml

        add_login_group_to_winbind_ssh_access_list:
          file.replace:
            - name: '/etc/security/pam_winbind.conf'
            - pattern: '^(require_membership_of = )(.*)$'
            - repl: '\1\2,append-new-group-to-line'

    .. note::

       The ``file.replace`` state uses Python's ``re`` module.
       For more advanced options, see https://docs.python.org/2/library/re.html
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.replace')

    check_res, check_msg = _check_file(name)
    if not check_res:
        if ignore_if_missing and 'file not found' in check_msg:
            ret['comment'] = 'No changes needed to be made'
            return ret
        else:
            return _error(ret, check_msg)

    changes = __salt__['file.replace'](name,
                                       pattern,
                                       repl,
                                       count=count,
                                       flags=flags,
                                       bufsize=bufsize,
                                       append_if_not_found=append_if_not_found,
                                       prepend_if_not_found=prepend_if_not_found,
                                       not_found_content=not_found_content,
                                       backup=backup,
                                       dry_run=__opts__['test'],
                                       show_changes=show_changes,
                                       ignore_if_missing=ignore_if_missing,
                                       backslash_literal=backslash_literal)

    if changes:
        ret['changes']['diff'] = changes
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Changes would have been made'
        else:
            ret['result'] = True
            ret['comment'] = 'Changes were made'
    else:
        ret['result'] = True
        ret['comment'] = 'No changes needed to be made'

    return ret


def blockreplace(
        name,
        marker_start='#-- start managed zone --',
        marker_end='#-- end managed zone --',
        source=None,
        source_hash=None,
        template='jinja',
        sources=None,
        source_hashes=None,
        defaults=None,
        context=None,
        content='',
        append_if_not_found=False,
        prepend_if_not_found=False,
        backup='.bak',
        show_changes=True,
        append_newline=None):
    '''
    Maintain an edit in a file in a zone delimited by two line markers

    .. versionadded:: 2014.1.0
    .. versionchanged:: 2017.7.5,2018.3.1
        ``append_newline`` argument added. Additionally, to improve
        idempotence, if the string represented by ``marker_end`` is found in
        the middle of the line, the content preceding the marker will be
        removed when the block is replaced. This allows one to remove
        ``append_newline: False`` from the SLS and have the block properly
        replaced if the end of the content block is immediately followed by the
        ``marker_end`` (i.e. no newline before the marker).

    A block of content delimited by comments can help you manage several lines
    entries without worrying about old entries removal. This can help you
    maintaining an un-managed file containing manual edits.

    .. note::
        This function will store two copies of the file in-memory (the original
        version and the edited version) in order to detect changes and only
        edit the targeted file if necessary.

        Additionally, you can use :py:func:`file.accumulated
        <salt.states.file.accumulated>` and target this state. All accumulated
        data dictionaries' content will be added in the content block.

    name
        Filesystem path to the file to be edited

    marker_start
        The line content identifying a line as the start of the content block.
        Note that the whole line containing this marker will be considered, so
        whitespace or extra content before or after the marker is included in
        final output

    marker_end
        The line content identifying the end of the content block. As of
        versions 2017.7.5 and 2018.3.1, everything up to the text matching the
        marker will be replaced, so it's important to ensure that your marker
        includes the beginning of the text you wish to replace.

    content
        The content to be used between the two lines identified by
        ``marker_start`` and ``marker_end``

    source
        The source file to download to the minion, this source file can be
        hosted on either the salt master server, or on an HTTP or FTP server.
        Both HTTPS and HTTP are supported as well as downloading directly
        from Amazon S3 compatible URLs with both pre-configured and automatic
        IAM credentials. (see s3.get state documentation)
        File retrieval from Openstack Swift object storage is supported via
        swift://container/object_path URLs, see swift.get documentation.
        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs. If source is left blank or None
        (use ~ in YAML), the file will be created as an empty file and
        the content will not be managed. This is also the case when a file
        already exists and the source is undefined; the contents of the file
        will not be changed or managed.

        If the file is hosted on a HTTP or FTP server then the source_hash
        argument is also required.

        A list of sources can also be passed in to provide a default source and
        a set of fallbacks. The first source in the list that is found to exist
        will be used and subsequent entries in the list will be ignored.

        .. code-block:: yaml

            file_override_example:
              file.blockreplace:
                - name: /etc/example.conf
                - source:
                  - salt://file_that_does_not_exist
                  - salt://file_that_exists

    source_hash
        This can be one of the following:
            1. a source hash string
            2. the URI of a file that contains source hash strings

        The function accepts the first encountered long unbroken alphanumeric
        string of correct length as a valid hash, in order from most secure to
        least secure:

        .. code-block:: text

            Type    Length
            ======  ======
            sha512     128
            sha384      96
            sha256      64
            sha224      56
            sha1        40
            md5         32

        See the ``source_hash`` parameter description for :mod:`file.managed
        <salt.states.file.managed>` function for more details and examples.

    template : jinja
        Templating engine to be used to render the downloaded file. The
        following engines are supported:

        - :mod:`cheetah <salt.renderers.cheetah>`
        - :mod:`genshi <salt.renderers.genshi>`
        - :mod:`jinja <salt.renderers.jinja>`
        - :mod:`mako <salt.renderers.mako>`
        - :mod:`py <salt.renderers.py>`
        - :mod:`wempy <salt.renderers.wempy>`

    context
        Overrides default context variables passed to the template

    defaults
        Default context passed to the template

    append_if_not_found : False
        If markers are not found and this option is set to ``True``, the
        content block will be appended to the file.

    prepend_if_not_found : False
        If markers are not found and this option is set to ``True``, the
        content block will be prepended to the file.

    backup
        The file extension to use for a backup of the file if any edit is made.
        Set this to ``False`` to skip making a backup.

    dry_run : False
        If ``True``, do not make any edits to the file and simply return the
        changes that *would* be made.

    show_changes : True
        Controls how changes are presented. If ``True``, the ``Changes``
        section of the state return will contain a unified diff of the changes
        made. If False, then it will contain a boolean (``True`` if any changes
        were made, otherwise ``False``).

    append_newline
        Controls whether or not a newline is appended to the content block. If
        the value of this argument is ``True`` then a newline will be added to
        the content block. If it is ``False``, then a newline will *not* be
        added to the content block. If it is unspecified, then a newline will
        only be added to the content block if it does not already end in a
        newline.

        .. versionadded:: 2017.7.5,2018.3.1

    Example of usage with an accumulator and with a variable:

    .. code-block:: jinja

        {% set myvar = 42 %}
        hosts-config-block-{{ myvar }}:
          file.blockreplace:
            - name: /etc/hosts
            - marker_start: "# START managed zone {{ myvar }} -DO-NOT-EDIT-"
            - marker_end: "# END managed zone {{ myvar }} --"
            - content: 'First line of content'
            - append_if_not_found: True
            - backup: '.bak'
            - show_changes: True

        hosts-config-block-{{ myvar }}-accumulated1:
          file.accumulated:
            - filename: /etc/hosts
            - name: my-accumulator-{{ myvar }}
            - text: "text 2"
            - require_in:
              - file: hosts-config-block-{{ myvar }}

        hosts-config-block-{{ myvar }}-accumulated2:
          file.accumulated:
            - filename: /etc/hosts
            - name: my-accumulator-{{ myvar }}
            - text: |
                 text 3
                 text 4
            - require_in:
              - file: hosts-config-block-{{ myvar }}

    will generate and maintain a block of content in ``/etc/hosts``:

    .. code-block:: text

        # START managed zone 42 -DO-NOT-EDIT-
        First line of content
        text 2
        text 3
        text 4
        # END managed zone 42 --
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.blockreplace')

    if sources is None:
        sources = []
    if source_hashes is None:
        source_hashes = []

    (ok_, err, sl_) = _unify_sources_and_hashes(source=source,
                                                source_hash=source_hash,
                                                sources=sources,
                                                source_hashes=source_hashes)
    if not ok_:
        return _error(ret, err)

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    accum_data, accum_deps = _load_accumulators()
    if name in accum_data:
        accumulator = accum_data[name]
        # if we have multiple accumulators for a file, only apply the one
        # required at a time
        deps = accum_deps.get(name, [])
        filtered = [a for a in deps if
                    __low__['__id__'] in deps[a] and a in accumulator]
        if not filtered:
            filtered = [a for a in accumulator]
        for acc in filtered:
            acc_content = accumulator[acc]
            for line in acc_content:
                if content == '':
                    content = line
                else:
                    content += "\n" + line

    if sl_:
        tmpret = _get_template_texts(source_list=sl_,
                                     template=template,
                                     defaults=defaults,
                                     context=context)
        if not tmpret['result']:
            return tmpret
        text = tmpret['data']

        for index, item in enumerate(text):
            content += six.text_type(item)

    try:
        changes = __salt__['file.blockreplace'](
            name,
            marker_start,
            marker_end,
            content=content,
            append_if_not_found=append_if_not_found,
            prepend_if_not_found=prepend_if_not_found,
            backup=backup,
            dry_run=__opts__['test'],
            show_changes=show_changes,
            append_newline=append_newline)
    except Exception as exc:
        log.exception('Encountered error managing block')
        ret['comment'] = (
            'Encountered error managing block: {0}. '
            'See the log for details.'.format(exc)
        )
        return ret

    if changes:
        ret['changes']['diff'] = changes
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Changes would be made'
        else:
            ret['result'] = True
            ret['comment'] = 'Changes were made'
    else:
        ret['result'] = True
        ret['comment'] = 'No changes needed to be made'

    return ret


def comment(name, regex, char='#', backup='.bak'):
    '''
    Comment out specified lines in a file.

    name
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be commented;
        this pattern will be wrapped in parenthesis and will move any
        preceding/trailing ``^`` or ``$`` characters outside the parenthesis
        (e.g., the pattern ``^foo$`` will be rewritten as ``^(foo)$``)
        Note that you _need_ the leading ^, otherwise each time you run
        highstate, another comment char will be inserted.
    char : ``#``
        The character to be inserted at the beginning of a line in order to
        comment it out
    backup : ``.bak``
        The file will be backed up before edit with this file extension

        .. warning::

            This backup will be overwritten each time ``sed`` / ``comment`` /
            ``uncomment`` is called. Meaning the backup will only be useful
            after the first invocation.

        Set to False/None to not keep a backup.

    Usage:

    .. code-block:: yaml

        /etc/fstab:
          file.comment:
            - regex: ^bind 127.0.0.1

    .. versionadded:: 0.9.5
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.comment')

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    # remove (?i)-like flags, ^ and $
    unanchor_regex = re.sub(r'^(\(\?[iLmsux]\))?\^?(.*?)\$?$', r'\2', regex)

    comment_regex = char + unanchor_regex

    # Check if the line is already commented
    if __salt__['file.search'](name, comment_regex, multiline=True):
        commented = True
    else:
        commented = False

    # Make sure the pattern appears in the file before continuing
    if commented or not __salt__['file.search'](name, regex, multiline=True):
        if __salt__['file.search'](name, unanchor_regex, multiline=True):
            ret['comment'] = 'Pattern already commented'
            ret['result'] = True
            return ret
        else:
            return _error(ret, '{0}: Pattern not found'.format(unanchor_regex))

    if __opts__['test']:
        ret['changes'][name] = 'updated'
        ret['comment'] = 'File {0} is set to be updated'.format(name)
        ret['result'] = None
        return ret
    with salt.utils.files.fopen(name, 'rb') as fp_:
        slines = fp_.read()
        if six.PY3:
            slines = slines.decode(__salt_system_encoding__)
        slines = slines.splitlines(True)

    # Perform the edit
    __salt__['file.comment_line'](name, regex, char, True, backup)

    with salt.utils.files.fopen(name, 'rb') as fp_:
        nlines = fp_.read()
        if six.PY3:
            nlines = nlines.decode(__salt_system_encoding__)
        nlines = nlines.splitlines(True)

    # Check the result
    ret['result'] = __salt__['file.search'](name, unanchor_regex, multiline=True)

    if slines != nlines:
        if not __utils__['files.is_text'](name):
            ret['changes']['diff'] = 'Replace binary file'
        else:
            # Changes happened, add them
            ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
            )

    if ret['result']:
        ret['comment'] = 'Commented lines successfully'
    else:
        ret['comment'] = 'Expected commented lines not found'

    return ret


def uncomment(name, regex, char='#', backup='.bak'):
    '''
    Uncomment specified commented lines in a file

    name
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be uncommented.
        This regex should not include the comment character. A leading ``^``
        character will be stripped for convenience (for easily switching
        between comment() and uncomment()).  The regex will be searched for
        from the beginning of the line, ignoring leading spaces (we prepend
        '^[ \\t]*')
    char : ``#``
        The character to remove in order to uncomment a line
    backup : ``.bak``
        The file will be backed up before edit with this file extension;

        .. warning::

            This backup will be overwritten each time ``sed`` / ``comment`` /
            ``uncomment`` is called. Meaning the backup will only be useful
            after the first invocation.

        Set to False/None to not keep a backup.

    Usage:

    .. code-block:: yaml

        /etc/adduser.conf:
          file.uncomment:
            - regex: EXTRA_GROUPS

    .. versionadded:: 0.9.5
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.uncomment')

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    # Make sure the pattern appears in the file
    if __salt__['file.search'](
            name,
            '^[ \t]*{0}'.format(regex.lstrip('^')),
            multiline=True):
        ret['comment'] = 'Pattern already uncommented'
        ret['result'] = True
        return ret
    elif __salt__['file.search'](
            name,
            '{0}[ \t]*{1}'.format(char, regex.lstrip('^')),
            multiline=True):
        # Line exists and is commented
        pass
    else:
        return _error(ret, '{0}: Pattern not found'.format(regex))

    if __opts__['test']:
        ret['changes'][name] = 'updated'
        ret['comment'] = 'File {0} is set to be updated'.format(name)
        ret['result'] = None
        return ret

    with salt.utils.files.fopen(name, 'rb') as fp_:
        slines = salt.utils.data.decode(fp_.readlines())

    # Perform the edit
    __salt__['file.comment_line'](name, regex, char, False, backup)

    with salt.utils.files.fopen(name, 'rb') as fp_:
        nlines = salt.utils.data.decode(fp_.readlines())

    # Check the result
    ret['result'] = __salt__['file.search'](
        name,
        '^[ \t]*{0}'.format(regex.lstrip('^')),
        multiline=True
    )

    if slines != nlines:
        if not __utils__['files.is_text'](name):
            ret['changes']['diff'] = 'Replace binary file'
        else:
            # Changes happened, add them
            ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
            )

    if ret['result']:
        ret['comment'] = 'Uncommented lines successfully'
    else:
        ret['comment'] = 'Expected uncommented lines not found'

    return ret


def append(name,
           text=None,
           makedirs=False,
           source=None,
           source_hash=None,
           template='jinja',
           sources=None,
           source_hashes=None,
           defaults=None,
           context=None,
           ignore_whitespace=True):
    '''
    Ensure that some text appears at the end of a file.

    The text will not be appended if it already exists in the file.
    A single string of text or a list of strings may be appended.

    name
        The location of the file to append to.

    text
        The text to be appended, which can be a single string or a list
        of strings.

    makedirs
        If the file is located in a path without a parent directory,
        then the state will fail. If makedirs is set to True, then
        the parent directories will be created to facilitate the
        creation of the named file. Defaults to False.

    source
        A single source file to append. This source file can be hosted on either
        the salt master server, or on an HTTP or FTP server. Both HTTPS and
        HTTP are supported as well as downloading directly from Amazon S3
        compatible URLs with both pre-configured and automatic IAM credentials
        (see s3.get state documentation). File retrieval from Openstack Swift
        object storage is supported via swift://container/object_path URLs
        (see swift.get documentation).

        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs.

        If the file is hosted on an HTTP or FTP server, the source_hash argument
        is also required.

    source_hash
        This can be one of the following:
            1. a source hash string
            2. the URI of a file that contains source hash strings

        The function accepts the first encountered long unbroken alphanumeric
        string of correct length as a valid hash, in order from most secure to
        least secure:

        .. code-block:: text

            Type    Length
            ======  ======
            sha512     128
            sha384      96
            sha256      64
            sha224      56
            sha1        40
            md5         32

        See the ``source_hash`` parameter description for :mod:`file.managed
        <salt.states.file.managed>` function for more details and examples.

    template
        The named templating engine will be used to render the appended-to file.
        Defaults to ``jinja``. The following templates are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    sources
        A list of source files to append. If the files are hosted on an HTTP or
        FTP server, the source_hashes argument is also required.

    source_hashes
        A list of source_hashes corresponding to the sources list specified in
        the sources argument.

    defaults
        Default context passed to the template.

    context
        Overrides default context variables passed to the template.

    ignore_whitespace
        .. versionadded:: 2015.8.4

        Spaces and Tabs in text are ignored by default, when searching for the
        appending content, one space or multiple tabs are the same for salt.
        Set this option to ``False`` if you want to change this behavior.

    Multi-line example:

    .. code-block:: yaml

        /etc/motd:
          file.append:
            - text: |
                Thou hadst better eat salt with the Philosophers of Greece,
                than sugar with the Courtiers of Italy.
                - Benjamin Franklin

    Multiple lines of text:

    .. code-block:: yaml

        /etc/motd:
          file.append:
            - text:
              - Trust no one unless you have eaten much salt with him.
              - "Salt is born of the purest of parents: the sun and the sea."

    Gather text from multiple template files:

    .. code-block:: yaml

        /etc/motd:
          file:
            - append
            - template: jinja
            - sources:
              - salt://motd/devops-messages.tmpl
              - salt://motd/hr-messages.tmpl
              - salt://motd/general-messages.tmpl

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not name:
        return _error(ret, 'Must provide name to file.append')

    name = os.path.expanduser(name)

    if sources is None:
        sources = []

    if source_hashes is None:
        source_hashes = []

    # Add sources and source_hashes with template support
    # NOTE: FIX 'text' and any 'source' are mutually exclusive as 'text'
    #       is re-assigned in the original code.
    (ok_, err, sl_) = _unify_sources_and_hashes(source=source,
                                                source_hash=source_hash,
                                                sources=sources,
                                                source_hashes=source_hashes)
    if not ok_:
        return _error(ret, err)

    if makedirs is True:
        dirname = os.path.dirname(name)
        if __opts__['test']:
            ret['comment'] = 'Directory {0} is set to be updated'.format(dirname)
            ret['result'] = None
        else:
            if not __salt__['file.directory_exists'](dirname):
                try:
                    _makedirs(name=name)
                except CommandExecutionError as exc:
                    return _error(ret, 'Drive {0} is not mapped'.format(exc.message))

                check_res, check_msg, check_changes = _check_directory_win(dirname) \
                    if salt.utils.platform.is_windows() \
                    else _check_directory(dirname)

                if not check_res:
                    ret['changes'] = check_changes
                    return _error(ret, check_msg)

    check_res, check_msg = _check_file(name)
    if not check_res:
        # Try to create the file
        touch_ret = touch(name, makedirs=makedirs)
        if __opts__['test']:
            return touch_ret
        retry_res, retry_msg = _check_file(name)
        if not retry_res:
            return _error(ret, check_msg)

    # Follow the original logic and re-assign 'text' if using source(s)...
    if sl_:
        tmpret = _get_template_texts(source_list=sl_,
                                     template=template,
                                     defaults=defaults,
                                     context=context)
        if not tmpret['result']:
            return tmpret
        text = tmpret['data']

    text = _validate_str_list(text)

    with salt.utils.files.fopen(name, 'rb') as fp_:
        slines = fp_.read()
        if six.PY3:
            slines = slines.decode(__salt_system_encoding__)
        slines = slines.splitlines()

    append_lines = []
    try:
        for chunk in text:
            if ignore_whitespace:
                if __salt__['file.search'](
                        name,
                        salt.utils.stringutils.build_whitespace_split_regex(chunk),
                        multiline=True):
                    continue
            elif __salt__['file.search'](
                    name,
                    chunk,
                    multiline=True):
                continue

            for line_item in chunk.splitlines():
                append_lines.append('{0}'.format(line_item))

    except TypeError:
        return _error(ret, 'No text found to append. Nothing appended')

    if __opts__['test']:
        ret['comment'] = 'File {0} is set to be updated'.format(name)
        ret['result'] = None
        nlines = list(slines)
        nlines.extend(append_lines)
        if slines != nlines:
            if not __utils__['files.is_text'](name):
                ret['changes']['diff'] = 'Replace binary file'
            else:
                # Changes happened, add them
                ret['changes']['diff'] = (
                    '\n'.join(difflib.unified_diff(slines, nlines))
                )
        else:
            ret['comment'] = 'File {0} is in correct state'.format(name)
            ret['result'] = True
        return ret

    if append_lines:
        __salt__['file.append'](name, args=append_lines)
        ret['comment'] = 'Appended {0} lines'.format(len(append_lines))
    else:
        ret['comment'] = 'File {0} is in correct state'.format(name)

    with salt.utils.files.fopen(name, 'rb') as fp_:
        nlines = fp_.read()
        if six.PY3:
            nlines = nlines.decode(__salt_system_encoding__)
        nlines = nlines.splitlines()

    if slines != nlines:
        if not __utils__['files.is_text'](name):
            ret['changes']['diff'] = 'Replace binary file'
        else:
            # Changes happened, add them
            ret['changes']['diff'] = (
                '\n'.join(difflib.unified_diff(slines, nlines)))

    ret['result'] = True

    return ret


def prepend(name,
            text=None,
            makedirs=False,
            source=None,
            source_hash=None,
            template='jinja',
            sources=None,
            source_hashes=None,
            defaults=None,
            context=None,
            header=None):
    '''
    Ensure that some text appears at the beginning of a file

    The text will not be prepended again if it already exists in the file. You
    may specify a single line of text or a list of lines to append.

    name
        The location of the file to append to.

    text
        The text to be appended, which can be a single string or a list
        of strings.

    makedirs
        If the file is located in a path without a parent directory,
        then the state will fail. If makedirs is set to True, then
        the parent directories will be created to facilitate the
        creation of the named file. Defaults to False.

    source
        A single source file to append. This source file can be hosted on either
        the salt master server, or on an HTTP or FTP server. Both HTTPS and
        HTTP are supported as well as downloading directly from Amazon S3
        compatible URLs with both pre-configured and automatic IAM credentials
        (see s3.get state documentation). File retrieval from Openstack Swift
        object storage is supported via swift://container/object_path URLs
        (see swift.get documentation).

        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs.

        If the file is hosted on an HTTP or FTP server, the source_hash argument
        is also required.

    source_hash
        This can be one of the following:
            1. a source hash string
            2. the URI of a file that contains source hash strings

        The function accepts the first encountered long unbroken alphanumeric
        string of correct length as a valid hash, in order from most secure to
        least secure:

        .. code-block:: text

            Type    Length
            ======  ======
            sha512     128
            sha384      96
            sha256      64
            sha224      56
            sha1        40
            md5         32

        See the ``source_hash`` parameter description for :mod:`file.managed
        <salt.states.file.managed>` function for more details and examples.

    template
        The named templating engine will be used to render the appended-to file.
        Defaults to ``jinja``. The following templates are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    sources
        A list of source files to append. If the files are hosted on an HTTP or
        FTP server, the source_hashes argument is also required.

    source_hashes
        A list of source_hashes corresponding to the sources list specified in
        the sources argument.

    defaults
        Default context passed to the template.

    context
        Overrides default context variables passed to the template.

    ignore_whitespace
        .. versionadded:: 2015.8.4

        Spaces and Tabs in text are ignored by default, when searching for the
        appending content, one space or multiple tabs are the same for salt.
        Set this option to ``False`` if you want to change this behavior.

    Multi-line example:

    .. code-block:: yaml

        /etc/motd:
          file.prepend:
            - text: |
                Thou hadst better eat salt with the Philosophers of Greece,
                than sugar with the Courtiers of Italy.
                - Benjamin Franklin

    Multiple lines of text:

    .. code-block:: yaml

        /etc/motd:
          file.prepend:
            - text:
              - Trust no one unless you have eaten much salt with him.
              - "Salt is born of the purest of parents: the sun and the sea."

    Optionally, require the text to appear exactly as specified
    (order and position). Combine with multi-line or multiple lines of input.

    .. code-block:: yaml

        /etc/motd:
          file.prepend:
            - header: True
            - text:
              - This will be the very first line in the file.
              - The 2nd line, regardless of duplicates elsewhere in the file.
              - These will be written anew if they do not appear verbatim.

    Gather text from multiple template files:

    .. code-block:: yaml

        /etc/motd:
          file:
            - prepend
            - template: jinja
            - sources:
              - salt://motd/devops-messages.tmpl
              - salt://motd/hr-messages.tmpl
              - salt://motd/general-messages.tmpl

    .. versionadded:: 2014.7.0
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.prepend')

    if sources is None:
        sources = []

    if source_hashes is None:
        source_hashes = []

    # Add sources and source_hashes with template support
    # NOTE: FIX 'text' and any 'source' are mutually exclusive as 'text'
    #       is re-assigned in the original code.
    (ok_, err, sl_) = _unify_sources_and_hashes(source=source,
                                                source_hash=source_hash,
                                                sources=sources,
                                                source_hashes=source_hashes)
    if not ok_:
        return _error(ret, err)

    if makedirs is True:
        dirname = os.path.dirname(name)
        if not __salt__['file.directory_exists'](dirname):
            try:
                _makedirs(name=name)
            except CommandExecutionError as exc:
                return _error(ret, 'Drive {0} is not mapped'.format(exc.message))

            check_res, check_msg, check_changes = _check_directory_win(dirname) \
                if salt.utils.platform.is_windows() \
                else _check_directory(dirname)

            if not check_res:
                ret['changes'] = check_changes
                return _error(ret, check_msg)

    check_res, check_msg = _check_file(name)
    if not check_res:
        # Try to create the file
        touch_ret = touch(name, makedirs=makedirs)
        if __opts__['test']:
            return touch_ret
        retry_res, retry_msg = _check_file(name)
        if not retry_res:
            return _error(ret, check_msg)

    # Follow the original logic and re-assign 'text' if using source(s)...
    if sl_:
        tmpret = _get_template_texts(source_list=sl_,
                                     template=template,
                                     defaults=defaults,
                                     context=context)
        if not tmpret['result']:
            return tmpret
        text = tmpret['data']

    text = _validate_str_list(text)

    with salt.utils.files.fopen(name, 'rb') as fp_:
        slines = fp_.read()
        if six.PY3:
            slines = slines.decode(__salt_system_encoding__)
        slines = slines.splitlines(True)

    count = 0
    test_lines = []

    preface = []
    for chunk in text:

        # if header kwarg is unset of False, use regex search
        if not header:
            if __salt__['file.search'](
                    name,
                    salt.utils.stringutils.build_whitespace_split_regex(chunk),
                    multiline=True):
                continue

        lines = chunk.splitlines()

        for line in lines:
            if __opts__['test']:
                ret['comment'] = 'File {0} is set to be updated'.format(name)
                ret['result'] = None
                test_lines.append('{0}\n'.format(line))
            else:
                preface.append(line)
            count += 1

    if __opts__['test']:
        nlines = test_lines + slines
        if slines != nlines:
            if not __utils__['files.is_text'](name):
                ret['changes']['diff'] = 'Replace binary file'
            else:
                # Changes happened, add them
                ret['changes']['diff'] = (
                    ''.join(difflib.unified_diff(slines, nlines))
                )
            ret['result'] = None
        else:
            ret['comment'] = 'File {0} is in correct state'.format(name)
            ret['result'] = True
        return ret

    # if header kwarg is True, use verbatim compare
    if header:
        with salt.utils.files.fopen(name, 'rb') as fp_:
            # read as many lines of target file as length of user input
            contents = fp_.read()
            if six.PY3:
                contents = contents.decode(__salt_system_encoding__)
            contents = contents.splitlines(True)
            target_head = contents[0:len(preface)]
            target_lines = []
            # strip newline chars from list entries
            for chunk in target_head:
                target_lines += chunk.splitlines()
            # compare current top lines in target file with user input
            # and write user input if they differ
            if target_lines != preface:
                __salt__['file.prepend'](name, *preface)
            else:
                # clear changed lines counter if target file not modified
                count = 0
    else:
        __salt__['file.prepend'](name, *preface)

    with salt.utils.files.fopen(name, 'rb') as fp_:
        nlines = fp_.read()
        if six.PY3:
            nlines = nlines.decode(__salt_system_encoding__)
        nlines = nlines.splitlines(True)

    if slines != nlines:
        if not __utils__['files.is_text'](name):
            ret['changes']['diff'] = 'Replace binary file'
        else:
            # Changes happened, add them
            ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
            )

    if count:
        ret['comment'] = 'Prepended {0} lines'.format(count)
    else:
        ret['comment'] = 'File {0} is in correct state'.format(name)
    ret['result'] = True
    return ret


def patch(name,
          source=None,
          source_hash=None,
          source_hash_name=None,
          skip_verify=False,
          template=None,
          context=None,
          defaults=None,
          options='',
          reject_file=None,
          strip=None,
          saltenv=None,
          **kwargs):
    '''
    Ensure that a patch has been applied to the specified file or directory

    .. versionchanged:: 2019.2.0
        The ``hash`` and ``dry_run_first`` options are now ignored, as the
        logic which determines whether or not the patch has already been
        applied no longer requires them. Additionally, this state now supports
        patch files that modify more than one file. To use these sort of
        patches, specify a directory (and, if necessary, the ``strip`` option)
        instead of a file.

    .. note::
        A suitable ``patch`` executable must be available on the minion. Also,
        keep in mind that the pre-check this state does to determine whether or
        not changes need to be made will create a temp file and send all patch
        output to that file. This means that, in the event that the patch would
        not have applied cleanly, the comment included in the state results will
        reference a temp file that will no longer exist once the state finishes
        running.

    name
        The file or directory to which the patch should be applied

    source
        The patch file to apply

        .. versionchanged:: 2019.2.0
            The source can now be from any file source supported by Salt
            (``salt://``, ``http://``, ``https://``, ``ftp://``, etc.).
            Templating is also now supported.

    source_hash
        Works the same way as in :py:func:`file.managed
        <salt.states.file.managed>`.

        .. versionadded:: 2019.2.0

    source_hash_name
        Works the same way as in :py:func:`file.managed
        <salt.states.file.managed>`

        .. versionadded:: 2019.2.0

    skip_verify
        Works the same way as in :py:func:`file.managed
        <salt.states.file.managed>`

        .. versionadded:: 2019.2.0

    template
        Works the same way as in :py:func:`file.managed
        <salt.states.file.managed>`

        .. versionadded:: 2019.2.0

    context
        Works the same way as in :py:func:`file.managed
        <salt.states.file.managed>`

        .. versionadded:: 2019.2.0

    defaults
        Works the same way as in :py:func:`file.managed
        <salt.states.file.managed>`

        .. versionadded:: 2019.2.0

    options
        Extra options to pass to patch. This should not be necessary in most
        cases.

        .. note::
            For best results, short opts should be separate from one another.
            The ``-N`` and ``-r``, and ``-o`` options are used internally by
            this state and cannot be used here. Additionally, instead of using
            ``-pN`` or ``--strip=N``, use the ``strip`` option documented
            below.

    reject_file
        If specified, any rejected hunks will be written to this file. If not
        specified, then they will be written to a temp file which will be
        deleted when the state finishes running.

        .. important::
            The parent directory must exist. Also, this will overwrite the file
            if it is already present.

        .. versionadded:: 2019.2.0

    strip
        Number of directories to strip from paths in the patch file. For
        example, using the below SLS would instruct Salt to use ``-p1`` when
        applying the patch:

        .. code-block:: yaml

            /etc/myfile.conf:
              file.patch:
                - source: salt://myfile.patch
                - strip: 1

        .. versionadded:: 2019.2.0
            In previous versions, ``-p1`` would need to be passed as part of
            the ``options`` value.

    saltenv
        Specify the environment from which to retrieve the patch file indicated
        by the ``source`` parameter. If not provided, this defaults to the
        environment from which the state is being executed.

        .. note::
            Ignored when the patch file is from a non-``salt://`` source.

    **Usage:**

    .. code-block:: yaml

        # Equivalent to ``patch --forward /opt/myfile.txt myfile.patch``
        /opt/myfile.txt:
          file.patch:
            - source: salt://myfile.patch
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if not salt.utils.path.which('patch'):
        ret['comment'] = 'patch executable not found on minion'
        return ret

    # is_dir should be defined if we proceed past the if/else block below, but
    # just in case, avoid a NameError.
    is_dir = False

    if not name:
        ret['comment'] = 'A file/directory to be patched is required'
        return ret
    else:
        try:
            name = os.path.expanduser(name)
        except Exception:
            ret['comment'] = 'Invalid path \'{0}\''.format(name)
            return ret
        else:
            if not os.path.isabs(name):
                ret['comment'] = '{0} is not an absolute path'.format(name)
                return ret
            elif not os.path.exists(name):
                ret['comment'] = '{0} does not exist'.format(name)
                return ret
            else:
                is_dir = os.path.isdir(name)

    for deprecated_arg in ('hash', 'dry_run_first'):
        if deprecated_arg in kwargs:
            ret.setdefault('warnings', []).append(
                'The \'{0}\' argument is no longer used and has been '
                'ignored.'.format(deprecated_arg)
            )

    if reject_file is not None:
        try:
            reject_file_parent = os.path.dirname(reject_file)
        except Exception:
            ret['comment'] = 'Invalid path \'{0}\' for reject_file'.format(
                reject_file
            )
            return ret
        else:
            if not os.path.isabs(reject_file_parent):
                ret['comment'] = '\'{0}\' is not an absolute path'.format(
                    reject_file
                )
                return ret
            elif not os.path.isdir(reject_file_parent):
                ret['comment'] = (
                    'Parent directory for reject_file \'{0}\' either does '
                    'not exist, or is not a directory'.format(reject_file)
                )
                return ret

    sanitized_options = []
    options = salt.utils.args.shlex_split(options)
    index = 0
    max_index = len(options) - 1
    # Not using enumerate here because we may need to consume more than one
    # option if --strip is used.
    blacklisted_options = []
    while index <= max_index:
        option = options[index]
        if not isinstance(option, six.string_types):
            option = six.text_type(option)

        for item in ('-N', '--forward', '-r', '--reject-file', '-o', '--output'):
            if option.startswith(item):
                blacklisted = option
                break
        else:
            blacklisted = None

        if blacklisted is not None:
            blacklisted_options.append(blacklisted)

        if option.startswith('-p'):
            try:
                strip = int(option[2:])
            except Exception:
                ret['comment'] = (
                    'Invalid format for \'-p\' CLI option. Consider using '
                    'the \'strip\' option for this state.'
                )
                return ret
        elif option.startswith('--strip'):
            if '=' in option:
                # Assume --strip=N
                try:
                    strip = int(option.rsplit('=', 1)[-1])
                except Exception:
                    ret['comment'] = (
                        'Invalid format for \'-strip\' CLI option. Consider '
                        'using the \'strip\' option for this state.'
                    )
                    return ret
            else:
                # Assume --strip N and grab the next option in the list
                try:
                    strip = int(options[index + 1])
                except Exception:
                    ret['comment'] = (
                        'Invalid format for \'-strip\' CLI option. Consider '
                        'using the \'strip\' option for this state.'
                    )
                    return ret
                else:
                    # We need to increment again because we grabbed the next
                    # option in the list.
                    index += 1
        else:
            sanitized_options.append(option)

        # Increment the index
        index += 1

    if blacklisted_options:
        ret['comment'] = (
            'The following CLI options are not allowed: {0}'.format(
                ', '.join(blacklisted_options)
            )
        )
        return ret

    options = sanitized_options

    try:
        source_match = __salt__['file.source_list'](source,
                                                    source_hash,
                                                    __env__)[0]
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        return ret
    else:
        # Passing the saltenv to file.managed to pull down the patch file is
        # not supported, because the saltenv is already being passed via the
        # state compiler and this would result in two values for that argument
        # (and a traceback). Therefore, we will add the saltenv to the source
        # URL to ensure we pull the file from the correct environment.
        if saltenv is not None:
            source_match_url, source_match_saltenv = \
                salt.utils.url.parse(source_match)
            if source_match_url.startswith('salt://'):
                if source_match_saltenv is not None \
                        and source_match_saltenv != saltenv:
                    ret.setdefault('warnings', []).append(
                        'Ignoring \'saltenv\' option in favor of saltenv '
                        'included in the source URL.'
                    )
                else:
                    source_match += '?saltenv={0}'.format(saltenv)

    cleanup = []

    try:
        patch_file = salt.utils.files.mkstemp()
        cleanup.append(patch_file)

        try:
            orig_test = __opts__['test']
            __opts__['test'] = False
            sys.modules[__salt__['test.ping'].__module__].__opts__['test'] = False
            result = managed(patch_file,
                             source=source_match,
                             source_hash=source_hash,
                             source_hash_name=source_hash_name,
                             skip_verify=skip_verify,
                             template=template,
                             context=context,
                             defaults=defaults)
        except Exception as exc:
            msg = 'Failed to cache patch file {0}: {1}'.format(
                salt.utils.url.redact_http_basic_auth(source_match),
                exc
            )
            log.exception(msg)
            ret['comment'] = msg
            return ret
        else:
            log.debug('file.managed: %s', result)
        finally:
            __opts__['test'] = orig_test
            sys.modules[__salt__['test.ping'].__module__].__opts__['test'] = orig_test

        if not result['result']:
            log.debug(
                'failed to download %s',
                salt.utils.url.redact_http_basic_auth(source_match)
            )
            return result

        def _patch(patch_file, options=None, dry_run=False):
            patch_opts = copy.copy(sanitized_options)
            if options is not None:
                patch_opts.extend(options)
            return __salt__['file.patch'](
                name,
                patch_file,
                options=patch_opts,
                dry_run=dry_run)

        if reject_file is not None:
            patch_rejects = reject_file
        else:
            # No rejects file specified, create a temp file
            patch_rejects = salt.utils.files.mkstemp()
            cleanup.append(patch_rejects)

        patch_output = salt.utils.files.mkstemp()
        cleanup.append(patch_output)

        # Older patch releases can only write patch output to regular files,
        # meaning that /dev/null can't be relied on. Also, if we ever want this
        # to work on Windows with patch.exe, /dev/null is a non-starter.
        # Therefore, redirect all patch output to a temp file, which we will
        # then remove.
        patch_opts = ['-N', '-r', patch_rejects, '-o', patch_output]
        if is_dir and strip is not None:
            patch_opts.append('-p{0}'.format(strip))

        pre_check = _patch(patch_file, patch_opts)
        if pre_check['retcode'] != 0:
            # Try to reverse-apply hunks from rejects file using a dry-run.
            # If this returns a retcode of 0, we know that the patch was
            # already applied. Rejects are written from the base of the
            # directory, so the strip option doesn't apply here.
            reverse_pass = _patch(patch_rejects, ['-R', '-f'], dry_run=True)
            already_applied = reverse_pass['retcode'] == 0

            if already_applied:
                ret['comment'] = 'Patch was already applied'
                ret['result'] = True
                return ret
            else:
                ret['comment'] = (
                    'Patch would not apply cleanly, no changes made. Results '
                    'of dry-run are below.'
                )
                if reject_file is None:
                    ret['comment'] += (
                        ' Run state again using the reject_file option to '
                        'save rejects to a persistent file.'
                    )
                opts = copy.copy(__opts__)
                opts['color'] = False
                ret['comment'] += '\n\n' + salt.output.out_format(
                    pre_check,
                    'nested',
                    opts,
                    nested_indent=14)
                return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The patch would be applied'
            ret['changes'] = pre_check
            return ret

        # If we've made it here, the patch should apply cleanly
        patch_opts = []
        if is_dir and strip is not None:
            patch_opts.append('-p{0}'.format(strip))
        ret['changes'] = _patch(patch_file, patch_opts)

        if ret['changes']['retcode'] == 0:
            ret['comment'] = 'Patch successfully applied'
            ret['result'] = True
        else:
            ret['comment'] = 'Failed to apply patch'

        return ret

    finally:
        # Clean up any temp files
        for path in cleanup:
            try:
                os.remove(path)
            except OSError as exc:
                if exc.errno != os.errno.ENOENT:
                    log.error(
                        'file.patch: Failed to remove temp file %s: %s',
                        path, exc
                    )


def touch(name, atime=None, mtime=None, makedirs=False):
    '''
    Replicate the 'nix "touch" command to create a new empty
    file or update the atime and mtime of an existing file.

    Note that if you just want to create a file and don't care about atime or
    mtime, you should use ``file.managed`` instead, as it is more
    feature-complete.  (Just leave out the ``source``/``template``/``contents``
    arguments, and it will just create the file and/or check its permissions,
    without messing with contents)

    name
        name of the file

    atime
        atime of the file

    mtime
        mtime of the file

    makedirs
        whether we should create the parent directory/directories in order to
        touch the file

    Usage:

    .. code-block:: yaml

        /var/log/httpd/logrotate.empty:
          file.touch

    .. versionadded:: 0.9.5
    '''
    name = os.path.expanduser(name)

    ret = {
        'name': name,
        'changes': {},
    }
    if not name:
        return _error(ret, 'Must provide name to file.touch')
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name)
        )

    if __opts__['test']:
        ret.update(_check_touch(name, atime, mtime))
        return ret

    if makedirs:
        try:
            _makedirs(name=name)
        except CommandExecutionError as exc:
            return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
    if not os.path.isdir(os.path.dirname(name)):
        return _error(
            ret, 'Directory not present to touch file {0}'.format(name)
        )

    extant = os.path.exists(name)

    ret['result'] = __salt__['file.touch'](name, atime, mtime)
    if not extant and ret['result']:
        ret['comment'] = 'Created empty file {0}'.format(name)
        ret['changes']['new'] = name
    elif extant and ret['result']:
        ret['comment'] = 'Updated times on {0} {1}'.format(
            'directory' if os.path.isdir(name) else 'file', name
        )
        ret['changes']['touched'] = name

    return ret


def copy_(name,
          source,
          force=False,
          makedirs=False,
          preserve=False,
          user=None,
          group=None,
          mode=None,
          subdir=False,
          **kwargs):
    '''
    If the file defined by the ``source`` option exists on the minion, copy it
    to the named path. The file will not be overwritten if it already exists,
    unless the ``force`` option is set to ``True``.

    .. note::
        This state only copies files from one location on a minion to another
        location on the same minion. For copying files from the master, use a
        :py:func:`file.managed <salt.states.file.managed>` state.

    name
        The location of the file to copy to

    source
        The location of the file to copy to the location specified with name

    force
        If the target location is present then the file will not be moved,
        specify "force: True" to overwrite the target file

    makedirs
        If the target subdirectories don't exist create them

    preserve
        .. versionadded:: 2015.5.0

        Set ``preserve: True`` to preserve user/group ownership and mode
        after copying. Default is ``False``. If ``preserve`` is set to ``True``,
        then user/group/mode attributes will be ignored.

    user
        .. versionadded:: 2015.5.0

        The user to own the copied file, this defaults to the user salt is
        running as on the minion. If ``preserve`` is set to ``True``, then
        this will be ignored

    group
        .. versionadded:: 2015.5.0

        The group to own the copied file, this defaults to the group salt is
        running as on the minion. If ``preserve`` is set to ``True`` or on
        Windows this will be ignored

    mode
        .. versionadded:: 2015.5.0

        The permissions to set on the copied file, aka 644, '0775', '4664'.
        If ``preserve`` is set to ``True``, then this will be ignored.
        Not supported on Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    subdir
        .. versionadded:: 2015.5.0

        If the name is a directory then place the file inside the named
        directory

    .. note::
        The copy function accepts paths that are local to the Salt minion.
        This function does not support salt://, http://, or the other
        additional file paths that are supported by :mod:`states.file.managed
        <salt.states.file.managed>` and :mod:`states.file.recurse
        <salt.states.file.recurse>`.

    '''
    name = os.path.expanduser(name)
    source = os.path.expanduser(source)

    ret = {
        'name': name,
        'changes': {},
        'comment': 'Copied "{0}" to "{1}"'.format(source, name),
        'result': True}
    if not name:
        return _error(ret, 'Must provide name to file.copy')

    changed = True
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if not os.path.exists(source):
        return _error(ret, 'Source file "{0}" is not present'.format(source))

    if preserve:
        user = __salt__['file.get_user'](source)
        group = __salt__['file.get_group'](source)
        mode = __salt__['file.get_mode'](source)
    else:
        user = _test_owner(kwargs, user=user)
        if user is None:
            user = __opts__['user']

        if salt.utils.platform.is_windows():
            if group is not None:
                log.warning(
                    'The group argument for {0} has been ignored as this is '
                    'a Windows system.'.format(name)
                )
            group = user

        if group is None:
            group = __salt__['file.gid_to_group'](
                __salt__['user.info'](user).get('gid', 0)
            )

        u_check = _check_user(user, group)
        if u_check:
            # The specified user or group do not exist
            return _error(ret, u_check)

        if mode is None:
            mode = __salt__['file.get_mode'](source)

    if os.path.isdir(name) and subdir:
        # If the target is a dir, and overwrite_dir is False, copy into the dir
        name = os.path.join(name, os.path.basename(source))

    if os.path.lexists(source) and os.path.lexists(name):
        # if this is a file which did not change, do not update
        if force and os.path.isfile(name):
            hash1 = salt.utils.hashutils.get_hash(name)
            hash2 = salt.utils.hashutils.get_hash(source)
            if hash1 == hash2:
                changed = True
                ret['comment'] = ' '.join([ret['comment'], '- files are identical but force flag is set'])
        if not force:
            changed = False
        elif not __opts__['test'] and changed:
            # Remove the destination to prevent problems later
            try:
                __salt__['file.remove'](name)
            except (IOError, OSError):
                return _error(
                    ret,
                    'Failed to delete "{0}" in preparation for '
                    'forced move'.format(name)
                )

    if __opts__['test']:
        if changed:
            ret['comment'] = 'File "{0}" is set to be copied to "{1}"'.format(
                source,
                name
            )
            ret['result'] = None
        else:
            ret['comment'] = ('The target file "{0}" exists and will not be '
                              'overwritten'.format(name))
            ret['result'] = True
        return ret

    if not changed:
        ret['comment'] = ('The target file "{0}" exists and will not be '
                          'overwritten'.format(name))
        ret['result'] = True
        return ret

    # Run makedirs
    dname = os.path.dirname(name)
    if not os.path.isdir(dname):
        if makedirs:
            try:
                _makedirs(name=name, user=user, group=group, dir_mode=mode)
            except CommandExecutionError as exc:
                return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
        else:
            return _error(
                ret,
                'The target directory {0} is not present'.format(dname))
    # All tests pass, move the file into place
    try:
        if os.path.isdir(source):
            shutil.copytree(source, name, symlinks=True)
            for root, dirs, files in salt.utils.path.os_walk(name):
                for dir_ in dirs:
                    __salt__['file.lchown'](os.path.join(root, dir_), user, group)
                for file_ in files:
                    __salt__['file.lchown'](os.path.join(root, file_), user, group)
        else:
            shutil.copy(source, name)
        ret['changes'] = {name: source}
        # Preserve really means just keep the behavior of the cp command. If
        # the filesystem we're copying to is squashed or doesn't support chown
        # then we shouldn't be checking anything.
        if not preserve:
            if salt.utils.platform.is_windows():
                # TODO: Add the other win_* parameters to this function
                ret = __salt__['file.check_perms'](
                    path=name,
                    ret=ret,
                    owner=user)
            else:
                __salt__['file.check_perms'](name, ret, user, group, mode)
    except (IOError, OSError):
        return _error(
            ret, 'Failed to copy "{0}" to "{1}"'.format(source, name))
    return ret


def rename(name, source, force=False, makedirs=False):
    '''
    If the source file exists on the system, rename it to the named file. The
    named file will not be overwritten if it already exists unless the force
    option is set to True.

    name
        The location of the file to rename to

    source
        The location of the file to move to the location specified with name

    force
        If the target location is present then the file will not be moved,
        specify "force: True" to overwrite the target file

    makedirs
        If the target subdirectories don't exist create them

    '''
    name = os.path.expanduser(name)
    source = os.path.expanduser(source)

    ret = {
        'name': name,
        'changes': {},
        'comment': '',
        'result': True}
    if not name:
        return _error(ret, 'Must provide name to file.rename')

    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if not os.path.lexists(source):
        ret['comment'] = ('Source file "{0}" has already been moved out of '
                          'place').format(source)
        return ret

    if os.path.lexists(source) and os.path.lexists(name):
        if not force:
            ret['comment'] = ('The target file "{0}" exists and will not be '
                              'overwritten'.format(name))
            return ret
        elif not __opts__['test']:
            # Remove the destination to prevent problems later
            try:
                __salt__['file.remove'](name)
            except (IOError, OSError):
                return _error(
                    ret,
                    'Failed to delete "{0}" in preparation for '
                    'forced move'.format(name)
                )

    if __opts__['test']:
        ret['comment'] = 'File "{0}" is set to be moved to "{1}"'.format(
            source,
            name
        )
        ret['result'] = None
        return ret

    # Run makedirs
    dname = os.path.dirname(name)
    if not os.path.isdir(dname):
        if makedirs:
            try:
                _makedirs(name=name)
            except CommandExecutionError as exc:
                return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
        else:
            return _error(
                ret,
                'The target directory {0} is not present'.format(dname))
    # All tests pass, move the file into place
    try:
        if os.path.islink(source):
            linkto = os.readlink(source)
            os.symlink(linkto, name)
            os.unlink(source)
        else:
            shutil.move(source, name)
    except (IOError, OSError):
        return _error(
            ret, 'Failed to move "{0}" to "{1}"'.format(source, name))

    ret['comment'] = 'Moved "{0}" to "{1}"'.format(source, name)
    ret['changes'] = {name: source}
    return ret


def accumulated(name, filename, text, **kwargs):
    '''
    Prepare accumulator which can be used in template in file.managed state.
    Accumulator dictionary becomes available in template. It can also be used
    in file.blockreplace.

    name
        Accumulator name

    filename
        Filename which would receive this accumulator (see file.managed state
        documentation about ``name``)

    text
        String or list for adding in accumulator

    require_in / watch_in
        One of them required for sure we fill up accumulator before we manage
        the file. Probably the same as filename

    Example:

    Given the following:

    .. code-block:: yaml

        animals_doing_things:
          file.accumulated:
            - filename: /tmp/animal_file.txt
            - text: ' jumps over the lazy dog.'
            - require_in:
              - file: animal_file

        animal_file:
          file.managed:
            - name: /tmp/animal_file.txt
            - source: salt://animal_file.txt
            - template: jinja

    One might write a template for ``animal_file.txt`` like the following:

    .. code-block:: jinja

        The quick brown fox{% for animal in accumulator['animals_doing_things'] %}{{ animal }}{% endfor %}

    Collectively, the above states and template file will produce:

    .. code-block:: text

        The quick brown fox jumps over the lazy dog.

    Multiple accumulators can be "chained" together.

    .. note::
        The 'accumulator' data structure is a Python dictionary.
        Do not expect any loop over the keys in a deterministic order!
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }
    if not name:
        return _error(ret, 'Must provide name to file.accumulated')
    if text is None:
        ret['result'] = False
        ret['comment'] = 'No text supplied for accumulator'
        return ret
    require_in = __low__.get('require_in', [])
    watch_in = __low__.get('watch_in', [])
    deps = require_in + watch_in
    if not [x for x in deps if 'file' in x]:
        ret['result'] = False
        ret['comment'] = 'Orphaned accumulator {0} in {1}:{2}'.format(
            name,
            __low__['__sls__'],
            __low__['__id__']
        )
        return ret
    if isinstance(text, six.string_types):
        text = (text,)
    elif isinstance(text, dict):
        text = (text,)
    accum_data, accum_deps = _load_accumulators()
    if filename not in accum_data:
        accum_data[filename] = {}
    if filename not in accum_deps:
        accum_deps[filename] = {}
    if name not in accum_deps[filename]:
        accum_deps[filename][name] = []
    for accumulator in deps:
        accum_deps[filename][name].extend(six.itervalues(accumulator))
    if name not in accum_data[filename]:
        accum_data[filename][name] = []
    for chunk in text:
        if chunk not in accum_data[filename][name]:
            accum_data[filename][name].append(chunk)
            ret['comment'] = ('Accumulator {0} for file {1} '
                              'was charged by text'.format(name, filename))
    _persist_accummulators(accum_data, accum_deps)
    return ret


def serialize(name,
              dataset=None,
              dataset_pillar=None,
              user=None,
              group=None,
              mode=None,
              backup='',
              makedirs=False,
              show_changes=True,
              create=True,
              merge_if_exists=False,
              encoding=None,
              encoding_errors='strict',
              serializer_opts=None,
              deserializer_opts=None,
              **kwargs):
    '''
    Serializes dataset and store it into managed file. Useful for sharing
    simple configuration files.

    name
        The location of the file to create

    dataset
        The dataset that will be serialized

    dataset_pillar
        Operates like ``dataset``, but draws from a value stored in pillar,
        using the pillar path syntax used in :mod:`pillar.get
        <salt.modules.pillar.get>`. This is useful when the pillar value
        contains newlines, as referencing a pillar variable using a jinja/mako
        template can result in YAML formatting issues due to the newlines
        causing indentation mismatches.

        .. versionadded:: 2015.8.0

    formatter
        Write the data as this format. See the list of :py:mod:`serializer
        modules <salt.serializers>` for supported output formats.

    encoding
        If specified, then the specified encoding will be used. Otherwise, the
        file will be encoded using the system locale (usually UTF-8). See
        https://docs.python.org/3/library/codecs.html#standard-encodings for
        the list of available encodings.

        .. versionadded:: 2017.7.0

    encoding_errors : 'strict'
        Error encoding scheme. Default is ```'strict'```.
        See https://docs.python.org/2/library/codecs.html#codec-base-classes
        for the list of available schemes.

        .. versionadded:: 2017.7.0

    user
        The user to own the directory, this defaults to the user salt is
        running as on the minion

    group
        The group ownership set for the directory, this defaults to the group
        salt is running as on the minion

    mode
        The permissions to set on this file, e.g. ``644``, ``0775``, or
        ``4664``.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

        .. note::
            This option is **not** supported on Windows.

    backup
        Overrides the default backup mode for this specific file.

    makedirs
        Create parent directories for destination file.

        .. versionadded:: 2014.1.3

    show_changes
        Output a unified diff of the old file and the new file. If ``False``
        return a boolean if any changes were made.

    create
        Default is True, if create is set to False then the file will only be
        managed if the file already exists on the system.

    merge_if_exists
        Default is False, if merge_if_exists is True then the existing file will
        be parsed and the dataset passed in will be merged with the existing
        content

        .. versionadded:: 2014.7.0

    serializer_opts
        Pass through options to serializer. For example:

        .. code-block:: yaml

           /etc/dummy/package.yaml
             file.serialize:
               - formatter: yaml
               - serializer_opts:
                 - explicit_start: True
                 - default_flow_style: True
                 - indent: 4

        The valid opts are the additional opts (i.e. not the data being
        serialized) for the function used to serialize the data. Documentation
        for the these functions can be found in the list below:

        - For **yaml**: `yaml.dump()`_
        - For **json**: `json.dumps()`_
        - For **python**: `pprint.pformat()`_

        .. _`yaml.dump()`: https://pyyaml.org/wiki/PyYAMLDocumentation
        .. _`json.dumps()`: https://docs.python.org/2/library/json.html#json.dumps
        .. _`pprint.pformat()`: https://docs.python.org/2/library/pprint.html#pprint.pformat

    deserializer_opts
        Like ``serializer_opts`` above, but only used when merging with an
        existing file (i.e. when ``merge_if_exists`` is set to ``True``).

        The options specified here will be passed to the deserializer to load
        the existing data, before merging with the specified data and
        re-serializing.

        .. code-block:: yaml

           /etc/dummy/package.yaml
             file.serialize:
               - formatter: yaml
               - serializer_opts:
                 - explicit_start: True
                 - default_flow_style: True
                 - indent: 4
               - deserializer_opts:
                 - encoding: latin-1
               - merge_if_exists: True

        The valid opts are the additional opts (i.e. not the data being
        deserialized) for the function used to deserialize the data.
        Documentation for the these functions can be found in the list below:

        - For **yaml**: `yaml.load()`_
        - For **json**: `json.loads()`_

        .. _`yaml.load()`: https://pyyaml.org/wiki/PyYAMLDocumentation
        .. _`json.loads()`: https://docs.python.org/2/library/json.html#json.loads

        However, note that not all arguments are supported. For example, when
        deserializing JSON, arguments like ``parse_float`` and ``parse_int``
        which accept a callable object cannot be handled in an SLS file.

        .. versionadded:: 2019.2.0

    For example, this state:

    .. code-block:: yaml

        /etc/dummy/package.json:
          file.serialize:
            - dataset:
                name: naive
                description: A package using naive versioning
                author: A confused individual <iam@confused.com>
                dependencies:
                  express: '>= 1.2.0'
                  optimist: '>= 0.1.0'
                engine: node 0.4.1
            - formatter: json

    will manage the file ``/etc/dummy/package.json``:

    .. code-block:: json

        {
          "author": "A confused individual <iam@confused.com>",
          "dependencies": {
            "express": ">= 1.2.0",
            "optimist": ">= 0.1.0"
          },
          "description": "A package using naive versioning",
          "engine": "node 0.4.1",
          "name": "naive"
        }
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    name = os.path.expanduser(name)

    # Set some defaults
    serializer_options = {
        'yaml.serialize': {
            'default_flow_style': False,
        },
        'json.serialize': {
            'indent': 2,
            'separators': (',', ': '),
            'sort_keys': True,
        }
    }
    deserializer_options = {
        'yaml.deserialize': {},
        'json.deserialize': {},
    }
    if encoding:
        serializer_options['yaml.serialize'].update({'allow_unicode': True})
        serializer_options['json.serialize'].update({'ensure_ascii': False})

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if not name:
        return _error(ret, 'Must provide name to file.serialize')

    if not create:
        if not os.path.isfile(name):
            # Don't create a file that is not already present
            ret['comment'] = ('File {0} is not present and is not set for '
                              'creation').format(name)
            return ret

    formatter = kwargs.pop('formatter', 'yaml').lower()

    if len([x for x in (dataset, dataset_pillar) if x]) > 1:
        return _error(
            ret, 'Only one of \'dataset\' and \'dataset_pillar\' is permitted')

    if dataset_pillar:
        dataset = __salt__['pillar.get'](dataset_pillar)

    if dataset is None:
        return _error(
            ret, 'Neither \'dataset\' nor \'dataset_pillar\' was defined')

    if salt.utils.platform.is_windows():
        if group is not None:
            log.warning(
                'The group argument for %s has been ignored as this '
                'is a Windows system.', name
            )
        group = user

    serializer_name = '{0}.serialize'.format(formatter)
    deserializer_name = '{0}.deserialize'.format(formatter)

    if serializer_name not in __serializers__:
        return {'changes': {},
                'comment': '{0} format is not supported'.format(
                    formatter.capitalize()),
                'name': name,
                'result': False
                }

    if serializer_opts:
        serializer_options.setdefault(serializer_name, {}).update(
            salt.utils.data.repack_dictlist(serializer_opts)
        )

    if deserializer_opts:
        deserializer_options.setdefault(deserializer_name, {}).update(
            salt.utils.data.repack_dictlist(deserializer_opts)
        )

    if merge_if_exists:
        if os.path.isfile(name):
            if deserializer_name not in __serializers__:
                return {
                    'changes': {},
                    'comment': 'merge_if_exists is not supported for the {0} '
                               'formatter'.format(formatter),
                    'name': name,
                    'result': False
                }

            with salt.utils.files.fopen(name, 'r') as fhr:
                try:
                    existing_data = __serializers__[deserializer_name](
                        fhr,
                        **deserializer_options.get(deserializer_name, {})
                    )
                except (TypeError, DeserializationError) as exc:
                    ret['result'] = False
                    ret['comment'] = \
                        'Failed to deserialize existing data: {0}'.format(exc)
                    return False

            if existing_data is not None:
                merged_data = salt.utils.dictupdate.merge_recurse(existing_data, dataset)
                if existing_data == merged_data:
                    ret['result'] = True
                    ret['comment'] = 'The file {0} is in the correct state'.format(name)
                    return ret
                dataset = merged_data
    else:
        if deserializer_opts:
            ret.setdefault('warnings', []).append(
                'The \'deserializer_opts\' option is ignored unless '
                'merge_if_exists is set to True.'
            )

    contents = __serializers__[serializer_name](
        dataset,
        **serializer_options.get(serializer_name, {})
    )

    contents += '\n'

    # Make sure that any leading zeros stripped by YAML loader are added back
    mode = salt.utils.files.normalize_mode(mode)

    if __opts__['test']:
        ret['changes'] = __salt__['file.check_managed_changes'](
            name=name,
            source=None,
            source_hash={},
            source_hash_name=None,
            user=user,
            group=group,
            mode=mode,
            attrs=None,
            template=None,
            context=None,
            defaults=None,
            saltenv=__env__,
            contents=contents,
            skip_verify=False,
            **kwargs
        )

        if ret['changes']:
            ret['result'] = None
            ret['comment'] = 'Dataset will be serialized and stored into {0}'.format(
                name)

            if not show_changes:
                ret['changes']['diff'] = '<show_changes=False>'
        else:
            ret['result'] = True
            ret['comment'] = 'The file {0} is in the correct state'.format(name)
        return ret

    return __salt__['file.manage_file'](name=name,
                                        sfn='',
                                        ret=ret,
                                        source=None,
                                        source_sum={},
                                        user=user,
                                        group=group,
                                        mode=mode,
                                        attrs=None,
                                        saltenv=__env__,
                                        backup=backup,
                                        makedirs=makedirs,
                                        template=None,
                                        show_changes=show_changes,
                                        encoding=encoding,
                                        encoding_errors=encoding_errors,
                                        contents=contents)


def mknod(name, ntype, major=0, minor=0, user=None, group=None, mode='0600'):
    '''
    Create a special file similar to the 'nix mknod command. The supported
    device types are ``p`` (fifo pipe), ``c`` (character device), and ``b``
    (block device). Provide the major and minor numbers when specifying a
    character device or block device. A fifo pipe does not require this
    information. The command will create the necessary dirs if needed. If a
    file of the same name not of the same type/major/minor exists, it will not
    be overwritten or unlinked (deleted). This is logically in place as a
    safety measure because you can really shoot yourself in the foot here and
    it is the behavior of 'nix ``mknod``. It is also important to note that not
    just anyone can create special devices. Usually this is only done as root.
    If the state is executed as none other than root on a minion, you may
    receive a permission error.

    name
        name of the file

    ntype
        node type 'p' (fifo pipe), 'c' (character device), or 'b'
        (block device)

    major
        major number of the device
        does not apply to a fifo pipe

    minor
        minor number of the device
        does not apply to a fifo pipe

    user
        owning user of the device/pipe

    group
        owning group of the device/pipe

    mode
        permissions on the device/pipe

    Usage:

    .. code-block:: yaml

        /dev/chr:
          file.mknod:
            - ntype: c
            - major: 180
            - minor: 31
            - user: root
            - group: root
            - mode: 660

        /dev/blk:
          file.mknod:
            - ntype: b
            - major: 8
            - minor: 999
            - user: root
            - group: root
            - mode: 660

        /dev/fifo:
          file.mknod:
            - ntype: p
            - user: root
            - group: root
            - mode: 660

    .. versionadded:: 0.17.0
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    if not name:
        return _error(ret, 'Must provide name to file.mknod')

    if ntype == 'c':
        # Check for file existence
        if __salt__['file.file_exists'](name):
            ret['comment'] = (
                'File {0} exists and is not a character device. Refusing '
                'to continue'.format(name)
            )

        # Check if it is a character device
        elif not __salt__['file.is_chrdev'](name):
            if __opts__['test']:
                ret['comment'] = \
                    'Character device {0} is set to be created'.format(name)
                ret['result'] = None
            else:
                ret = __salt__['file.mknod'](name,
                                             ntype,
                                             major,
                                             minor,
                                             user,
                                             group,
                                             mode)

        # Check the major/minor
        else:
            devmaj, devmin = __salt__['file.get_devmm'](name)
            if (major, minor) != (devmaj, devmin):
                ret['comment'] = (
                    'Character device {0} exists and has a different '
                    'major/minor {1}/{2}. Refusing to continue'
                        .format(name, devmaj, devmin)
                )
            # Check the perms
            else:
                ret = __salt__['file.check_perms'](name,
                                                   None,
                                                   user,
                                                   group,
                                                   mode)[0]
                if not ret['changes']:
                    ret['comment'] = (
                        'Character device {0} is in the correct state'.format(
                            name
                        )
                    )

    elif ntype == 'b':
        # Check for file existence
        if __salt__['file.file_exists'](name):
            ret['comment'] = (
                'File {0} exists and is not a block device. Refusing to '
                'continue'.format(name)
            )

        # Check if it is a block device
        elif not __salt__['file.is_blkdev'](name):
            if __opts__['test']:
                ret['comment'] = 'Block device {0} is set to be created'.format(name)
                ret['result'] = None
            else:
                ret = __salt__['file.mknod'](name,
                                             ntype,
                                             major,
                                             minor,
                                             user,
                                             group,
                                             mode)

        # Check the major/minor
        else:
            devmaj, devmin = __salt__['file.get_devmm'](name)
            if (major, minor) != (devmaj, devmin):
                ret['comment'] = (
                    'Block device {0} exists and has a different major/minor '
                    '{1}/{2}. Refusing to continue'.format(
                        name, devmaj, devmin
                    )
                )
            # Check the perms
            else:
                ret = __salt__['file.check_perms'](name,
                                                   None,
                                                   user,
                                                   group,
                                                   mode)[0]
                if not ret['changes']:
                    ret['comment'] = (
                        'Block device {0} is in the correct state'.format(name)
                    )

    elif ntype == 'p':
        # Check for file existence
        if __salt__['file.file_exists'](name):
            ret['comment'] = (
                'File {0} exists and is not a fifo pipe. Refusing to '
                'continue'.format(name)
            )

        # Check if it is a fifo
        elif not __salt__['file.is_fifo'](name):
            if __opts__['test']:
                ret['comment'] = 'Fifo pipe {0} is set to be created'.format(
                    name
                )
                ret['result'] = None
            else:
                ret = __salt__['file.mknod'](name,
                                             ntype,
                                             major,
                                             minor,
                                             user,
                                             group,
                                             mode)

        # Check the perms
        else:
            ret = __salt__['file.check_perms'](name,
                                               None,
                                               user,
                                               group,
                                               mode)[0]
            if not ret['changes']:
                ret['comment'] = (
                    'Fifo pipe {0} is in the correct state'.format(name)
                )

    else:
        ret['comment'] = (
            'Node type unavailable: \'{0}\'. Available node types are '
            'character (\'c\'), block (\'b\'), and pipe (\'p\')'.format(ntype)
        )

    return ret


def mod_run_check_cmd(cmd, filename, **check_cmd_opts):
    '''
    Execute the check_cmd logic.

    Return a result dict if ``check_cmd`` succeeds (check_cmd == 0)
    otherwise return True
    '''

    log.debug('running our check_cmd')
    _cmd = '{0} {1}'.format(cmd, filename)
    cret = __salt__['cmd.run_all'](_cmd, **check_cmd_opts)
    if cret['retcode'] != 0:
        ret = {'comment': 'check_cmd execution failed',
               'skip_watch': True,
               'result': False}

        if cret.get('stdout'):
            ret['comment'] += '\n' + cret['stdout']
        if cret.get('stderr'):
            ret['comment'] += '\n' + cret['stderr']

        return ret

    # No reason to stop, return True
    return True


def decode(name,
        encoded_data=None,
        contents_pillar=None,
        encoding_type='base64',
        checksum='md5'):
    '''
    Decode an encoded file and write it to disk

    .. versionadded:: 2016.3.0

    name
        Path of the file to be written.
    encoded_data
        The encoded file. Either this option or ``contents_pillar`` must be
        specified.
    contents_pillar
        A Pillar path to the encoded file. Uses the same path syntax as
        :py:func:`pillar.get <salt.modules.pillar.get>`. The
        :py:func:`hashutil.base64_encodefile
        <salt.modules.hashutil.base64_encodefile>` function can load encoded
        content into Pillar. Either this option or ``encoded_data`` must be
        specified.
    encoding_type : ``base64``
        The type of encoding.
    checksum : ``md5``
        The hashing algorithm to use to generate checksums. Wraps the
        :py:func:`hashutil.digest <salt.modules.hashutil.digest>` execution
        function.

    Usage:

    .. code-block:: yaml

        write_base64_encoded_string_to_a_file:
          file.decode:
            - name: /tmp/new_file
            - encoding_type: base64
            - contents_pillar: mypillar:thefile

        # or

        write_base64_encoded_string_to_a_file:
          file.decode:
            - name: /tmp/new_file
            - encoding_type: base64
            - encoded_data: |
                Z2V0IHNhbHRlZAo=

    Be careful with multi-line strings that the YAML indentation is correct.
    E.g.,

    .. code-block:: jinja

        write_base64_encoded_string_to_a_file:
          file.decode:
            - name: /tmp/new_file
            - encoding_type: base64
            - encoded_data: |
                {{ salt.pillar.get('path:to:data') | indent(8) }}
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if not (encoded_data or contents_pillar):
        raise CommandExecutionError("Specify either the 'encoded_data' or "
            "'contents_pillar' argument.")
    elif encoded_data and contents_pillar:
        raise CommandExecutionError("Specify only one 'encoded_data' or "
            "'contents_pillar' argument.")
    elif encoded_data:
        content = encoded_data
    elif contents_pillar:
        content = __salt__['pillar.get'](contents_pillar, False)
        if content is False:
            raise CommandExecutionError('Pillar data not found.')
    else:
        raise CommandExecutionError('No contents given.')

    dest_exists = __salt__['file.file_exists'](name)
    if dest_exists:
        instr = __salt__['hashutil.base64_decodestring'](content)
        insum = __salt__['hashutil.digest'](instr, checksum)
        del instr  # no need to keep in-memory after we have the hash
        outsum = __salt__['hashutil.digest_file'](name, checksum)

        if insum != outsum:
            ret['changes'] = {
                'old': outsum,
                'new': insum,
            }

        if not ret['changes']:
            ret['comment'] = 'File is in the correct state.'
            ret['result'] = True

            return ret

    if __opts__['test'] is True:
        ret['comment'] = 'File is set to be updated.'
        ret['result'] = None
        return ret

    ret['result'] = __salt__['hashutil.base64_decodefile'](content, name)
    ret['comment'] = 'File was updated.'

    if not ret['changes']:
        ret['changes'] = {
            'old': None,
            'new': __salt__['hashutil.digest_file'](name, checksum),
        }

    return ret


def shortcut(
        name,
        target,
        arguments=None,
        working_dir=None,
        description=None,
        icon_location=None,
        force=False,
        backupname=None,
        makedirs=False,
        user=None,
        **kwargs):
    '''
    Create a Windows shortcut

    If the file already exists and is a shortcut pointing to any location other
    than the specified target, the shortcut will be replaced. If it is
    a regular file or directory then the state will return False. If the
    regular file or directory is desired to be replaced with a shortcut pass
    force: True, if it is to be renamed, pass a backupname.

    name
        The location of the shortcut to create. Must end with either
        ".lnk" or ".url"

    target
        The location that the shortcut points to

    arguments
        Any arguments to pass in the shortcut

    working_dir
        Working directory in which to execute target

    description
        Description to set on shortcut

    icon_location
        Location of shortcut's icon

    force
        If the name of the shortcut exists and is not a file and
        force is set to False, the state will fail. If force is set to
        True, the link or directory in the way of the shortcut file
        will be deleted to make room for the shortcut, unless
        backupname is set, when it will be renamed

    backupname
        If the name of the shortcut exists and is not a file, it will be
        renamed to the backupname. If the backupname already
        exists and force is False, the state will fail. Otherwise, the
        backupname will be removed first.

    makedirs
        If the location of the shortcut does not already have a parent
        directory then the state will fail, setting makedirs to True will
        allow Salt to create the parent directory. Setting this to True will
        also create the parent for backupname if necessary.

    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.
    '''
    user = _test_owner(kwargs, user=user)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not salt.utils.platform.is_windows():
        return _error(ret, 'Shortcuts are only supported on Windows')
    if not name:
        return _error(ret, 'Must provide name to file.shortcut')
    if not name.endswith('.lnk') and not name.endswith('.url'):
        return _error(ret, 'Name must end with either ".lnk" or ".url"')

    # Normalize paths; do this after error checks to avoid invalid input
    # getting expanded, e.g. '' turning into '.'
    name = os.path.realpath(os.path.expanduser(name))
    if name.endswith('.lnk'):
        target = os.path.realpath(os.path.expanduser(target))
    if working_dir:
        working_dir = os.path.realpath(os.path.expanduser(working_dir))
    if icon_location:
        icon_location = os.path.realpath(os.path.expanduser(icon_location))

    if user is None:
        user = __opts__['user']

    # Make sure the user exists in Windows
    # Salt default is 'root'
    if not __salt__['user.info'](user):
        # User not found, use the account salt is running under
        # If username not found, use System
        user = __salt__['user.current']()
        if not user:
            user = 'SYSTEM'

    preflight_errors = []
    uid = __salt__['file.user_to_uid'](user)

    if uid == '':
        preflight_errors.append('User {0} does not exist'.format(user))

    if not os.path.isabs(name):
        preflight_errors.append(
            'Specified file {0} is not an absolute path'.format(name)
        )

    if preflight_errors:
        msg = '. '.join(preflight_errors)
        if len(preflight_errors) > 1:
            msg += '.'
        return _error(ret, msg)

    presult, pcomment, pchanges = _shortcut_check(name,
                                                  target,
                                                  arguments,
                                                  working_dir,
                                                  description,
                                                  icon_location,
                                                  force,
                                                  user)
    if __opts__['test']:
        ret['result'] = presult
        ret['comment'] = pcomment
        ret['changes'] = pchanges
        return ret

    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            try:
                _makedirs(name=name, user=user)
            except CommandExecutionError as exc:
                return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
        else:
            return _error(
                ret,
                'Directory "{0}" for shortcut is not present'.format(
                    os.path.dirname(name)
                )
            )

    if os.path.isdir(name) or os.path.islink(name):
        # It is not a shortcut, but a dir or symlink
        if backupname is not None:
            # Make a backup first
            if os.path.lexists(backupname):
                if not force:
                    return _error(ret, ((
                                            'File exists where the backup target {0} should go'
                                        ).format(backupname)))
                else:
                    __salt__['file.remove'](backupname)
                    time.sleep(1)  # wait for asynchronous deletion
            if not os.path.isdir(os.path.dirname(backupname)):
                if makedirs:
                    try:
                        _makedirs(name=backupname)
                    except CommandExecutionError as exc:
                        return _error(ret, 'Drive {0} is not mapped'.format(exc.message))
                else:
                    return _error(ret, (
                                            'Directory does not exist for'
                                            ' backup at "{0}"'
                                        ).format(os.path.dirname(backupname)))
            os.rename(name, backupname)
            time.sleep(1)  # wait for asynchronous rename
        elif force:
            # Remove whatever is in the way
            __salt__['file.remove'](name)
            ret['changes']['forced'] = 'Shortcut was forcibly replaced'
            time.sleep(1)  # wait for asynchronous deletion
        else:
            # Otherwise throw an error
            return _error(ret, ((
                                    'Directory or symlink exists where the'
                                    ' shortcut "{0}" should be'
                                ).format(name)))

    # This will just load the shortcut if it already exists
    # It won't create the file until calling scut.Save()
    with salt.utils.winapi.Com():
        shell = win32com.client.Dispatch("WScript.Shell")
    scut = shell.CreateShortcut(name)

    # The shortcut target will automatically be created with its
    # canonical capitalization; no way to override it, so ignore case
    state_checks = [scut.TargetPath.lower() == target.lower()]
    if arguments is not None:
        state_checks.append(scut.Arguments == arguments)
    if working_dir is not None:
        state_checks.append(
            scut.WorkingDirectory.lower() == working_dir.lower()
        )
    if description is not None:
        state_checks.append(scut.Description == description)
    if icon_location is not None:
        state_checks.append(scut.IconLocation.lower() == icon_location.lower())

    if __salt__['file.file_exists'](name):
        # The shortcut exists, verify that it matches the desired state
        if not all(state_checks):
            # The target is wrong, delete it
            os.remove(name)
        else:
            if _check_shortcut_ownership(name, user):
                # The shortcut looks good!
                ret['comment'] = ('Shortcut {0} is present and owned by '
                                  '{1}'.format(name, user))
            else:
                if _set_shortcut_ownership(name, user):
                    ret['comment'] = ('Set ownership of shortcut {0} to '
                                      '{1}'.format(name, user))
                    ret['changes']['ownership'] = '{0}'.format(user)
                else:
                    ret['result'] = False
                    ret['comment'] += (
                        'Failed to set ownership of shortcut {0} to '
                        '{1}'.format(name, user)
                    )
            return ret

    if not os.path.exists(name):
        # The shortcut is not present, make it
        try:
            scut.TargetPath = target
            if arguments is not None:
                scut.Arguments = arguments
            if working_dir is not None:
                scut.WorkingDirectory = working_dir
            if description is not None:
                scut.Description = description
            if icon_location is not None:
                scut.IconLocation = icon_location
            scut.Save()
        except (AttributeError, pywintypes.com_error) as exc:
            ret['result'] = False
            ret['comment'] = ('Unable to create new shortcut {0} -> '
                              '{1}: {2}'.format(name, target, exc))
            return ret
        else:
            ret['comment'] = ('Created new shortcut {0} -> '
                              '{1}'.format(name, target))
            ret['changes']['new'] = name

        if not _check_shortcut_ownership(name, user):
            if not _set_shortcut_ownership(name, user):
                ret['result'] = False
                ret['comment'] += (', but was unable to set ownership to '
                                   '{0}'.format(user))
    return ret


def cached(name,
           source_hash='',
           source_hash_name=None,
           skip_verify=False,
           saltenv='base'):
    '''
    .. versionadded:: 2017.7.3

    Ensures that a file is saved to the minion's cache. This state is primarily
    invoked by other states to ensure that we do not re-download a source file
    if we do not need to.

    name
        The URL of the file to be cached. To cache a file from an environment
        other than ``base``, either use the ``saltenv`` argument or include the
        saltenv in the URL (e.g. ``salt://path/to/file.conf?saltenv=dev``).

        .. note::
            A list of URLs is not supported, this must be a single URL. If a
            local file is passed here, then the state will obviously not try to
            download anything, but it will compare a hash if one is specified.

    source_hash
        See the documentation for this same argument in the
        :py:func:`file.managed <salt.states.file.managed>` state.

        .. note::
            For remote files not originating from the ``salt://`` fileserver,
            such as http(s) or ftp servers, this state will not re-download the
            file if the locally-cached copy matches this hash. This is done to
            prevent unnecessary downloading on repeated runs of this state. To
            update the cached copy of a file, it is necessary to update this
            hash.

    source_hash_name
        See the documentation for this same argument in the
        :py:func:`file.managed <salt.states.file.managed>` state.

    skip_verify
        See the documentation for this same argument in the
        :py:func:`file.managed <salt.states.file.managed>` state.

        .. note::
            Setting this to ``True`` will result in a copy of the file being
            downloaded from a remote (http(s), ftp, etc.) source each time the
            state is run.

    saltenv
        Used to specify the environment from which to download a file from the
        Salt fileserver (i.e. those with ``salt://`` URL).


    This state will in most cases not be useful in SLS files, but it is useful
    when writing a state or remote-execution module that needs to make sure
    that a file at a given URL has been downloaded to the cachedir. One example
    of this is in the :py:func:`archive.extracted <salt.states.file.extracted>`
    state:

    .. code-block:: python

        result = __states__['file.cached'](source_match,
                                           source_hash=source_hash,
                                           source_hash_name=source_hash_name,
                                           skip_verify=skip_verify,
                                           saltenv=__env__)

    This will return a dictionary containing the state's return data, including
    a ``result`` key which will state whether or not the state was successful.
    Note that this will not catch exceptions, so it is best used within a
    try/except.

    Once this state has been run from within another state or remote-execution
    module, the actual location of the cached file can be obtained using
    :py:func:`cp.is_cached <salt.modules.cp.is_cached>`:

    .. code-block:: python

        cached = __salt__['cp.is_cached'](source_match, saltenv=__env__)

    This function will return the cached path of the file, or an empty string
    if the file is not present in the minion cache.
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': False}

    try:
        parsed = _urlparse(name)
    except Exception:
        ret['comment'] = 'Only URLs or local file paths are valid input'
        return ret

    # This if statement will keep the state from proceeding if a remote source
    # is specified and no source_hash is presented (unless we're skipping hash
    # verification).
    if not skip_verify \
            and not source_hash \
            and parsed.scheme in salt.utils.files.REMOTE_PROTOS:
        ret['comment'] = (
            'Unable to verify upstream hash of source file {0}, please set '
            'source_hash or set skip_verify to True'.format(
                salt.utils.url.redact_http_basic_auth(name))
        )
        return ret

    if source_hash:
        # Get the hash and hash type from the input. This takes care of parsing
        # the hash out of a file containing checksums, if that is how the
        # source_hash was specified.
        try:
            source_sum = __salt__['file.get_source_sum'](
                source=name,
                source_hash=source_hash,
                source_hash_name=source_hash_name,
                saltenv=saltenv)
        except CommandExecutionError as exc:
            ret['comment'] = exc.strerror
            return ret
        else:
            if not source_sum:
                # We shouldn't get here, problems in retrieving the hash in
                # file.get_source_sum should result in a CommandExecutionError
                # being raised, which we catch above. Nevertheless, we should
                # provide useful information in the event that
                # file.get_source_sum regresses.
                ret['comment'] = (
                    'Failed to get source hash from {0}. This may be a bug. '
                    'If this error persists, please report it and set '
                    'skip_verify to True to work around it.'.format(source_hash)
                )
                return ret
    else:
        source_sum = {}

    if parsed.scheme in salt.utils.files.LOCAL_PROTOS:
        # Source is a local file path
        full_path = os.path.realpath(os.path.expanduser(parsed.path))
        if os.path.exists(full_path):
            if not skip_verify and source_sum:
                # Enforce the hash
                local_hash = __salt__['file.get_hash'](
                    full_path,
                    source_sum.get('hash_type', __opts__['hash_type']))
                if local_hash == source_sum['hsum']:
                    ret['result'] = True
                    ret['comment'] = (
                        'File {0} is present on the minion and has hash '
                        '{1}'.format(full_path, local_hash)
                    )
                else:
                    ret['comment'] = (
                        'File {0} is present on the minion, but the hash ({1}) '
                        'does not match the specified hash ({2})'.format(
                            full_path, local_hash, source_sum['hsum']
                        )
                    )
                return ret
            else:
                ret['result'] = True
                ret['comment'] = 'File {0} is present on the minion'.format(
                    full_path
                )
                return ret
        else:
            ret['comment'] = 'File {0} is not present on the minion'.format(
                full_path
            )
            return ret

    local_copy = __salt__['cp.is_cached'](name, saltenv=saltenv)

    if local_copy:
        # File is already cached
        pre_hash = __salt__['file.get_hash'](
            local_copy,
            source_sum.get('hash_type', __opts__['hash_type']))

        if not skip_verify and source_sum:
            # Get the local copy's hash to compare with the hash that was
            # specified via source_hash. If it matches, we can exit early from
            # the state without going any further, because the file is cached
            # with the correct hash.
            if pre_hash == source_sum['hsum']:
                ret['result'] = True
                ret['comment'] = (
                    'File is already cached to {0} with hash {1}'.format(
                        local_copy, pre_hash
                    )
                )
    else:
        pre_hash = None

    def _try_cache(path, checksum):
        '''
        This helper is not needed anymore in develop as the fileclient in the
        develop branch now has means of skipping a download if the existing
        hash matches one passed to cp.cache_file. Remove this helper and the
        code that invokes it, once we have merged forward into develop.
        '''
        if not path or not checksum:
            return True
        form = salt.utils.files.HASHES_REVMAP.get(len(checksum))
        if form is None:
            # Shouldn't happen, an invalid checksum length should be caught
            # before we get here. But in the event this gets through, don't let
            # it cause any trouble, and just return True.
            return True
        try:
            return salt.utils.hashutils.get_hash(path, form=form) != checksum
        except (IOError, OSError, ValueError):
            # Again, shouldn't happen, but don't let invalid input/permissions
            # in the call to get_hash blow this up.
            return True

    # Cache the file. Note that this will not actually download the file if
    # either of the following is true:
    #   1. source is a salt:// URL and the fileserver determines that the hash
    #      of the minion's copy matches that of the fileserver.
    #   2. File is remote (http(s), ftp, etc.) and the specified source_hash
    #      matches the cached copy.
    # Remote, non salt:// sources _will_ download if a copy of the file was
    # not already present in the minion cache.
    if _try_cache(local_copy, source_sum.get('hsum')):
        # The _try_cache helper is obsolete in the develop branch. Once merged
        # forward, remove the helper as well as this if statement, and dedent
        # the below block.
        try:
            local_copy = __salt__['cp.cache_file'](
                name,
                saltenv=saltenv,
                source_hash=source_sum.get('hsum'))
        except Exception as exc:
            ret['comment'] = salt.utils.url.redact_http_basic_auth(exc.__str__())
            return ret

    if not local_copy:
        ret['comment'] = (
            'Failed to cache {0}, check minion log for more '
            'information'.format(
                salt.utils.url.redact_http_basic_auth(name))
        )
        return ret

    post_hash = __salt__['file.get_hash'](
        local_copy,
        source_sum.get('hash_type', __opts__['hash_type']))

    if pre_hash != post_hash:
        ret['changes']['hash'] = {'old': pre_hash, 'new': post_hash}

    # Check the hash, if we're enforcing one. Note that this will be the first
    # hash check if the file was not previously cached, and the 2nd hash check
    # if it was cached and the
    if not skip_verify and source_sum:
        if post_hash == source_sum['hsum']:
            ret['result'] = True
            ret['comment'] = (
                'File is already cached to {0} with hash {1}'.format(
                    local_copy, post_hash
                )
            )
        else:
            ret['comment'] = (
                'File is cached to {0}, but the hash ({1}) does not match '
                'the specified hash ({2})'.format(
                    local_copy, post_hash, source_sum['hsum']
                )
            )
        return ret

    # We're not enforcing a hash, and we already know that the file was
    # successfully cached, so we know the state was successful.
    ret['result'] = True
    ret['comment'] = 'File is cached to {0}'.format(local_copy)
    return ret


def not_cached(name, saltenv='base'):
    '''
    .. versionadded:: 2017.7.3

    Ensures that a file is saved to the minion's cache. This state is primarily
    invoked by other states to ensure that we do not re-download a source file
    if we do not need to.

    name
        The URL of the file to be cached. To cache a file from an environment
        other than ``base``, either use the ``saltenv`` argument or include the
        saltenv in the URL (e.g. ``salt://path/to/file.conf?saltenv=dev``).

        .. note::
            A list of URLs is not supported, this must be a single URL. If a
            local file is passed here, the state will take no action.

    saltenv
        Used to specify the environment from which to download a file from the
        Salt fileserver (i.e. those with ``salt://`` URL).
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': False}

    try:
        parsed = _urlparse(name)
    except Exception:
        ret['comment'] = 'Only URLs or local file paths are valid input'
        return ret
    else:
        if parsed.scheme in salt.utils.files.LOCAL_PROTOS:
            full_path = os.path.realpath(os.path.expanduser(parsed.path))
            ret['result'] = True
            ret['comment'] = (
                'File {0} is a local path, no action taken'.format(
                    full_path
                )
            )
            return ret

    local_copy = __salt__['cp.is_cached'](name, saltenv=saltenv)

    if local_copy:
        try:
            os.remove(local_copy)
        except Exception as exc:
            ret['comment'] = 'Failed to delete {0}: {1}'.format(
                local_copy, exc.__str__()
            )
        else:
            ret['result'] = True
            ret['changes']['deleted'] = True
            ret['comment'] = '{0} was deleted'.format(local_copy)
    else:
        ret['result'] = True
        ret['comment'] = '{0} is not cached'.format(name)
    return ret

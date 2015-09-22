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

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file.managed:
        - source: salt://apache/http.conf
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - defaults:
            custom_var: "default value"
            other_var: 123
    {% if grains['os'] == 'Ubuntu' %}
        - context:
            custom_var: "override"
    {% endif %}

It is also possible to use the :mod:`py renderer <salt.renderers.py>` as a
templating option. The template would be a python script which would need to
contain a function called ``run()``, which returns a string. The returned
string will be the contents of the managed file. For example:

.. code-block:: python

    def run():
        lines = ('foo', 'bar', 'baz')
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

.. code-block:: yaml

    /etc/foo.conf:
      file.managed:
        - source:
          - salt://foo.conf.{{ grains['fqdn'] }}
          - salt://foo.conf.fallback
        - user: foo
        - group: users
        - mode: 644
        - backup: minion

.. note::

    Salt supports backing up managed files via the backup option. For more
    details on this functionality please review the
    :doc:`backup_mode documentation </ref/states/backup_mode>`.

The ``source`` parameter can also specify a file in another Salt environment.
In this example ``foo.conf`` in the ``dev`` environment will be used instead.

.. code-block:: yaml

    /etc/foo.conf:
      file.managed:
        - source:
          - salt://foo.conf?saltenv=dev
        - user: foo
        - group: users
        - mode: '0644'

.. warning::

        When using a mode that includes a leading zero you must wrap the
        value in single quotes. If the value is not wrapped in quotes it
        will be read by YAML as an integer and evaluated as an octal.

Special files can be managed via the ``mknod`` function. This function will
create and enforce the permissions on a special file. The function supports the
creation of character devices, block devices, and fifo pipes. The function will
create the directory structure up to the special file if it is needed on the
minion. The function will not overwrite or operate on (change major/minor
numbers) existing special files with the exception of user, group, and
permissions. In most cases the creation of some special files require root
permisisons on the minion. This would require that the minion to be run as the
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

.. code-block:: yaml

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
'''
from __future__ import absolute_import

# Import python libs
import difflib
import itertools
import json
import logging
import os
import pprint
import shutil
import traceback
import yaml
from collections import Iterable, Mapping

# Import salt libs
import salt.payload
import salt.utils
import salt.utils.templates
from salt.exceptions import CommandExecutionError
from salt.utils.serializers import yaml as yaml_serializer
from salt.utils.serializers import json as json_serializer
import salt.ext.six as six
from salt.ext.six import string_types
from salt.ext.six.moves import zip_longest

log = logging.getLogger(__name__)

COMMENT_REGEX = r'^([[:space:]]*){0}[[:space:]]?'


def _get_accumulator_filepath():
    '''
    Return accumulator data path.
    '''
    return os.path.join(salt.utils.get_accumulator_dir(__opts__['cachedir']),
                        __instance_id__)


def _load_accumulators():
    def _deserialize(path):
        serial = salt.payload.Serial(__opts__)
        ret = {'accumulators': {}, 'accumulators_deps': {}}
        try:
            with open(path, 'rb') as f:
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
        with open(_get_accumulator_filepath(), 'w+b') as f:
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
            for root, dirs, files in os.walk(name):
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
                if low['name'] == comp['file']:
                    fn = low['name']
                    if os.path.isdir(comp['file']):
                        if _is_child(comp['file'], name):
                            if walk_d:
                                walk_ret = set()
                                _process_by_walk_d(fn, walk_ret)
                                keep.update(walk_ret)
                            else:
                                keep.update(_process(fn))
                    else:
                        keep.add(fn)
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


def _clean_dir(root, keep, exclude_pat):
    '''
    Clean out all of the files and directories in a directory (root) while
    preserving the files in a list (keep) and part of exclude_pat
    '''
    removed = set()
    real_keep = set()
    real_keep.add(root)
    if isinstance(keep, list):
        for fn_ in keep:
            if not os.path.isabs(fn_):
                continue
            real_keep.add(fn_)
            while True:
                fn_ = os.path.dirname(fn_)
                real_keep.add(fn_)
                if fn_ in ['/', ''.join([os.path.splitdrive(fn_)[0], '\\'])]:
                    break

    def _delete_not_kept(nfn):
        if nfn not in real_keep:
            # -- check if this is a part of exclude_pat(only). No need to
            # check include_pat
            if not salt.utils.check_include_exclude(
                    os.path.relpath(nfn, root), None, exclude_pat):
                return
            removed.add(nfn)
            if not __opts__['test']:
                try:
                    os.remove(nfn)
                except OSError:
                    shutil.rmtree(nfn)

    for roots, dirs, files in os.walk(root):
        for name in itertools.chain(dirs, files):
            _delete_not_kept(os.path.join(roots, name))
    return list(removed)


def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


def _get_recurse_dest(prefix, fn_, source, env):
    '''
    Return the destination path to copy the file path, fn_(as returned by
    a call to __salt__['cp.cache_dir']), to.
    '''
    local_roots = []
    if __opts__['file_client'] == 'local':
        local_roots = __opts__['file_roots'][env]
        local_roots.sort(key=len, reverse=True)

    srcpath = source[7:]  # the path after "salt://"

    # in solo mode (i.e., file_client=='local'), fn_ is a path below
    # a file root; in remote mode, fn_ is a path below the cache_dir.
    for root in local_roots:
        rootlen = len(root)
        # if root is the longest prefix path of fn_
        if root == fn_[:rootlen]:
            cachedir = os.path.join(root, srcpath)
            break
    else:
        cachedir = os.path.join(
            __opts__['cachedir'], 'files', env, srcpath)

    return os.path.join(prefix, os.path.relpath(fn_, cachedir))


def _check_directory(name,
                     user,
                     group,
                     recurse,
                     mode,
                     clean,
                     require,
                     exclude_pat):
    '''
    Check what changes need to be made on a directory
    '''
    changes = {}
    if recurse or clean:
        walk_l = list(os.walk(name))  # walk path only once and store the result
        # root: (dirs, files) structure, compatible for python2.6
        walk_d = {}
        for i in walk_l:
            walk_d[i[0]] = (i[1], i[2])

    if recurse:
        if not set(['user', 'group', 'mode']) >= set(recurse):
            return False, 'Types for "recurse" limited to "user", ' \
                          '"group" and "mode"'
        if 'user' not in recurse:
            user = None
        if 'group' not in recurse:
            group = None
        if 'mode' not in recurse:
            mode = None
        for root, dirs, files in walk_l:
            for fname in files:
                fchange = {}
                path = os.path.join(root, fname)
                stats = __salt__['file.stats'](
                    path, None, follow_symlinks=False
                )
                if user is not None and user != stats.get('user'):
                    fchange['user'] = user
                if group is not None and group != stats.get('group'):
                    fchange['group'] = group
                if fchange:
                    changes[path] = fchange
            for name_ in dirs:
                path = os.path.join(root, name_)
                fchange = _check_dir_meta(path, user, group, mode)
                if fchange:
                    changes[path] = fchange
    else:
        fchange = _check_dir_meta(name, user, group, mode)
        if fchange:
            changes[name] = fchange
    if clean:
        keep = _gen_keep_files(name, require, walk_d)

        def _check_changes(fname):
            path = os.path.join(root, fname)
            if path in keep:
                return {}
            else:
                if not salt.utils.check_include_exclude(
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
            for key, val in changes[fn_].items():
                comments.append('{0}: {1} - {2}\n'.format(fn_, key, val))
        return None, ''.join(comments)
    return True, 'The directory {0} is in the correct state'.format(name)


def _check_dir_meta(name,
                    user,
                    group,
                    mode):
    '''
    Check the changes in directory metadata
    '''
    stats = __salt__['file.stats'](name, follow_symlinks=False)
    changes = {}
    if not stats:
        changes['directory'] = 'new'
        return changes
    if user is not None and user != stats['user']:
        changes['user'] = user
    if group is not None and group != stats['group']:
        changes['group'] = group
    # Normalize the dir mode
    smode = __salt__['config.manage_mode'](stats['mode'])
    mode = __salt__['config.manage_mode'](mode)
    if mode is not None and mode != smode:
        changes['mode'] = mode
    return changes


def _check_touch(name, atime, mtime):
    '''
    Check to see if a file needs to be updated or created
    '''
    if not os.path.exists(name):
        return None, 'File {0} is set to be created'.format(name)
    stats = __salt__['file.stats'](name, follow_symlinks=False)
    if atime is not None:
        if str(atime) != str(stats['atime']):
            return None, 'Times set to be updated on file {0}'.format(name)
    if mtime is not None:
        if str(mtime) != str(stats['mtime']):
            return None, 'Times set to be updated on file {0}'.format(name)
    return True, 'File {0} exists and has the correct times'.format(name)


def _get_symlink_ownership(path):
    return (
        __salt__['file.get_user'](path, follow_symlinks=False),
        __salt__['file.get_group'](path, follow_symlinks=False)
    )


def _check_symlink_ownership(path, user, group):
    '''
    Check if the symlink ownership matches the specified user and group
    '''
    cur_user, cur_group = _get_symlink_ownership(path)
    return (cur_user == user) and (cur_group == group)


def _set_symlink_ownership(path, user, group):
    '''
    Set the ownership of a symlink and return a boolean indicating
    success/failure
    '''
    try:
        __salt__['file.lchown'](path, user, group)
    except OSError:
        pass
    return _check_symlink_ownership(path, user, group)


def _symlink_check(name, target, force, user, group):
    '''
    Check the symlink function
    '''
    if not os.path.exists(name) and not __salt__['file.is_link'](name):
        return None, 'Symlink {0} to {1} is set for creation'.format(
            name, target
        )
    if __salt__['file.is_link'](name):
        if __salt__['file.readlink'](name) != target:
            return None, 'Link {0} target is set to be changed to {1}'.format(
                name, target
            )
        else:
            result = True
            msg = 'The symlink {0} is present'.format(name)
            if not _check_symlink_ownership(name, user, group):
                result = None
                msg += (
                    ', but the ownership of the symlink would be changed '
                    'from {2}:{3} to {0}:{1}'
                ).format(user, group, *_get_symlink_ownership(name))
            return result, msg
    else:
        if force:
            return None, ('The file or directory {0} is set for removal to '
                          'make way for a new symlink targeting {1}'
                          .format(name, target))
        return False, ('File or directory exists where the symlink {0} '
                       'should be. Did you mean to use force?'.format(name))


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
            with salt.utils.fopen(rndrd_templ_fn, 'rb') as fp_:
                tmplines = fp_.readlines()
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


def _validate_str_list(arg):
    '''
    ensure ``arg`` is a list of strings
    '''
    if isinstance(arg, string_types):
        return [arg]
    elif isinstance(arg, Iterable) and not isinstance(arg, Mapping):
        return [str(item) for item in arg]
    else:
        return [str(arg)]


def symlink(
        name,
        target,
        force=False,
        backupname=None,
        makedirs=False,
        user=None,
        group=None,
        mode=None,
        **kwargs):
    '''
    Create a symlink

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
        on Windows
    '''
    name = os.path.expanduser(name)

    # Make sure that leading zeros stripped by YAML loader are added back
    mode = __salt__['config.manage_mode'](mode)

    user = _test_owner(kwargs, user=user)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.symlink')

    if user is None:
        user = __opts__['user']

    if salt.utils.is_windows():

        # Make sure the user exists in Windows
        # Salt default is 'root'
        if not __salt__['user.info'](user):
            # User not found, use the account salt is running under
            # If username not found, use System
            user = __salt__['user.current']()
            if not user:
                user = 'SYSTEM'

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

    if preflight_errors:
        msg = '. '.join(preflight_errors)
        if len(preflight_errors) > 1:
            msg += '.'
        return _error(ret, msg)

    if __opts__['test']:
        ret['result'], ret['comment'] = _symlink_check(name, target, force,
                                                       user, group)
        return ret

    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            __salt__['file.makedirs'](
                name,
                user=user,
                group=group,
                mode=mode)
        else:
            return _error(
                ret,
                'Directory {0} for symlink is not present'.format(
                    os.path.dirname(name)
                )
            )
    if __salt__['file.is_link'](name):
        # The link exists, verify that it matches the target
        if __salt__['file.readlink'](name) != target:
            # The target is wrong, delete the link
            os.remove(name)
        else:
            if _check_symlink_ownership(name, user, group):
                # The link looks good!
                ret['comment'] = ('Symlink {0} is present and owned by '
                                  '{1}:{2}'.format(name, user, group))
            else:
                if _set_symlink_ownership(name, user, group):
                    ret['comment'] = ('Set ownership of symlink {0} to '
                                      '{1}:{2}'.format(name, user, group))
                    ret['changes']['ownership'] = '{0}:{1}'.format(user, group)
                else:
                    ret['result'] = False
                    ret['comment'] += (
                        'Failed to set ownership of symlink {0} to '
                        '{1}:{2}'.format(name, user, group)
                    )
            return ret

    elif os.path.isfile(name) or os.path.isdir(name):
        # It is not a link, but a file or dir
        if backupname is not None:
            # Make a backup first
            if os.path.lexists(backupname):
                if not force:
                    return _error(ret, ((
                                            'File exists where the backup target {0} should go'
                                        ).format(backupname)))
                elif os.path.isfile(backupname):
                    os.remove(backupname)
                elif os.path.isdir(backupname):
                    shutil.rmtree(backupname)
                else:
                    return _error(ret, ((
                                            'Something exists where the backup target {0}'
                                            'should go'
                                        ).format(backupname)))
            os.rename(name, backupname)
        elif force:
            # Remove whatever is in the way
            if os.path.isfile(name):
                os.remove(name)
                ret['changes']['forced'] = 'Symlink was forcibly replaced'
            else:
                shutil.rmtree(name)
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

        if not _check_symlink_ownership(name, user, group):
            if not _set_symlink_ownership(name, user, group):
                ret['result'] = False
                ret['comment'] += (', but was unable to set ownership to '
                                   '{0}:{1}'.format(user, group))
    return ret


def absent(name):
    '''
    Make sure that the named file or directory is absent. If it exists, it will
    be deleted. This will work to reverse any of the functions in the file
    state module.

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
            ret['comment'] = 'File {0} is set for removal'.format(name)
            return ret
        try:
            __salt__['file.remove'](name)
            ret['comment'] = 'Removed file {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except CommandExecutionError as exc:
            return _error(ret, '{0}'.format(exc))

    elif os.path.isdir(name):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Directory {0} is set for removal'.format(name)
            return ret
        try:
            shutil.rmtree(name)
            ret['comment'] = 'Removed directory {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except (OSError, IOError):
            return _error(ret, 'Failed to remove directory {0}'.format(name))

    ret['comment'] = 'File {0} is not present'.format(name)
    return ret


def exists(name):
    '''
    Verify that the named file or directory is present or exists.
    Ensures pre-requisites outside of Salt's purview
    (e.g., keytabs, private keys, etc.) have been previously satisfied before
    deployment.

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


def missing(name):
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
            user=None,
            group=None,
            mode=None,
            template=None,
            makedirs=False,
            dir_mode=None,
            context=None,
            replace=True,
            defaults=None,
            env=None,
            backup='',
            show_diff=True,
            create=True,
            contents=None,
            contents_pillar=None,
            contents_grains=None,
            contents_newline=True,
            follow_symlinks=True,
            check_cmd=None,
            **kwargs):
    '''
    Manage a given file, this function allows for a file to be downloaded from
    the salt master and potentially run through a templating system.

    name
        The location of the file to manage

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
        the content will not be managed

        If the file is hosted on a HTTP or FTP server then the source_hash
        argument is also required

        A list of sources can also be passed in to provide a default source and
        a set of fallbacks. The first source in the list that is found to exist
        will be used and subsequent entries in the list will be ignored.

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

            The following is an example of the supported source_hash format:

            .. code-block:: text

                /etc/rc.conf ef6e82e4006dee563d98ada2a2a80a27
                sha254c8525aee419eb649f0233be91c151178b30f0dff8ebbdcc8de71b1d5c8bcc06a  /etc/resolv.conf
                ead48423703509d37c4a90e6a0d53e143b6fc268

            Debian file type ``*.dsc`` files are also supported.

        **Inserting the Source Hash in the sls Data**
            Examples:

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


    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

    group
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion On Windows, this is ignored

    mode
        The permissions to set on this file, aka 644, 0775, 4664. Not supported
        on Windows

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file, currently jinja, mako, and wempy
        are supported

    makedirs
        If the file is located in a path without a parent directory, then
        the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.

    dir_mode
        If directories are to be created, passing this option specifies the
        permissions for those directories. If this is not set, directories
        will be assigned permissions from the 'mode' argument.

    replace
        If this file should be replaced.  If false, this command will
        not overwrite file contents but will enforce permissions if the file
        exists already.  Default is True.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    backup
        Overrides the default backup mode for this specific file.

    show_diff
        If set to False, the diff will not be shown.

    create
        Default is True, if create is set to False then the file will only be
        managed if the file already exists on the system.

    contents
        Default is None.  If specified, will use the given string as the
        contents of the file.  Should not be used in conjunction with a source
        file of any kind.  Ignores hashes and does not use a templating engine.

    contents_pillar
        .. versionadded:: 0.17.0

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
            pipe character, and the mutliline string is indented two more
            spaces.

    contents_grains
        .. versionadded:: 2014.7.0

        Same as contents_pillar, but with grains

    contents_newline
        .. versionadded:: 2014.7.0

        When using contents, contents_pillar, or contents_grains, this option
        ensures the file will have a newline at the end.
        When loading some data this newline is better left off. Setting
        contents_newline to False will omit this final newline.

    follow_symlinks : True
        .. versionadded:: 2014.7.0

        If the desired path is a symlink follow it and make changes to the
        file to which the symlink points.

    check_cmd
        .. versionadded:: 2014.7.0

        The specified command will be run with the managed file as an argument.
        If the command exits with a nonzero exit code, the command will not be
        run.
    '''
    name = os.path.expanduser(name)

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # If no source is specified, set replace to False, as there is nothing
    # to replace the file with.
    src_defined = source or contents or contents_pillar or contents_grains
    if not src_defined and replace:
        replace = False
        log.warning(
            'Neither \'source\' nor \'contents\' nor \'contents_pillar\' nor \'contents_grains\' '
            'was defined, yet \'replace\' was set to \'True\'. As there is '
            'no source to replace the file with, \'replace\' has been set '
            'to \'False\' to avoid reading the file unnecessarily'
        )

    if len([_f for _f in [contents, contents_pillar, contents_grains] if _f]) > 1:
        return _error(
            ret, 'Only one of contents, contents_pillar, and contents_grains is permitted')

    if contents_pillar:
        contents = __salt__['pillar.get'](contents_pillar)
    if contents_grains:
        contents = __salt__['grains.get'](contents_grains)

    # ensure contents is a string
    if contents:
        validated_contents = _validate_str_list(contents)
        if not validated_contents:
            return _error(ret, '"contents" is not a string or list of strings')
        if isinstance(validated_contents, list):
            contents = os.linesep.join(validated_contents)
        if contents_newline:
            # Make sure file ends in newline
            if contents and not contents.endswith(os.linesep):
                contents += os.linesep

    # Make sure that leading zeros stripped by YAML loader are added back
    mode = __salt__['config.manage_mode'](mode)

    if not name:
        return _error(ret, 'Must provide name to file.exists')
    user = _test_owner(kwargs, user=user)
    if salt.utils.is_windows():
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this '
                'is a Windows system.'.format(name)
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

    if isinstance(env, string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Boron', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

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
        # Check and set the permissions if necessary
        ret, _ = __salt__['file.check_perms'](name, ret, user, group, mode,
                                              follow_symlinks)
        if __opts__['test']:
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
            ret['changes'] = __salt__['file.check_managed_changes'](
                name,
                source,
                source_hash,
                user,
                group,
                mode,
                template,
                context,
                defaults,
                __env__,
                contents,
                **kwargs
            )

            if ret['changes']:
                ret['result'] = None
                ret['comment'] = 'The file {0} is set to be changed'.format(name)
                if not show_diff:
                    ret['changes']['diff'] = '<show_diff=False>'
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
            user,
            group,
            mode,
            __env__,
            context,
            defaults,
            **kwargs
        )
    except Exception as exc:
        ret['changes'] = {}
        log.debug(traceback.format_exc())
        return _error(ret, 'Unable to manage file: {0}'.format(exc))

    if check_cmd:
        tmp_filename = salt.utils.mkstemp()

        # if exists copy existing file to tmp to compare
        if __salt__['file.file_exists'](name):
            try:
                __salt__['file.copy'](name, tmp_filename)
            except Exception as exc:
                return _error(ret, 'Unable to copy file {0} to {1}: {2}'.format(name, tmp_filename, exc))

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
                __env__,
                backup,
                makedirs,
                template,
                show_diff,
                contents,
                dir_mode,
                follow_symlinks)
        except Exception as exc:
            ret['changes'] = {}
            log.debug(traceback.format_exc())
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
                __env__,
                backup,
                makedirs,
                template,
                show_diff,
                contents,
                dir_mode,
                follow_symlinks)
        except Exception as exc:
            ret['changes'] = {}
            log.debug(traceback.format_exc())
            return _error(ret, 'Unable to manage file: {0}'.format(exc))


def directory(name,
              user=None,
              group=None,
              recurse=None,
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
              **kwargs):
    '''
    Ensure that a named directory is present and has the right perms

    name
        The location to create or manage a directory

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
                    - ignore_files

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

    dir_mode / mode
        The permissions mode to set any directories created. Not supported on
        Windows

    file_mode
        The permissions mode to set any files created if 'mode' is run in
        'recurse'. This defaults to dir_mode. Not supported on Windows

    makedirs
        If the directory is located in a path without a parent directory, then
        the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.

    clean
        Make sure that only files that are set up by salt and required by this
        function are kept. If this option is set then everything in this
        directory will be deleted unless it is required.

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
    '''
    name = os.path.expanduser(name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.directory')
    # Remove trailing slash, if present
    if name[-1] == '/':
        name = name[:-1]

    user = _test_owner(kwargs, user=user)
    if salt.utils.is_windows():
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this is '
                'a Windows system.'.format(name)
            )
        group = user

    if 'mode' in kwargs and not dir_mode:
        dir_mode = kwargs.get('mode', [])

    if not file_mode:
        file_mode = dir_mode

    # Make sure that leading zeros stripped by YAML loader are added back
    dir_mode = __salt__['config.manage_mode'](dir_mode)
    file_mode = __salt__['config.manage_mode'](file_mode)

    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))
    if os.path.isfile(name) or (not allow_symlink and os.path.islink(name)):
        if backupname is not None:
            # Make a backup first
            if os.path.lexists(backupname):
                if not force:
                    return _error(ret, ((
                                            'File exists where the backup target {0} should go'
                                        ).format(backupname)))
                elif os.path.isfile(backupname):
                    os.remove(backupname)
                elif os.path.islink(backupname):
                    os.remove(backupname)
                elif os.path.isdir(backupname):
                    shutil.rmtree(backupname)
                else:
                    return _error(ret, ((
                                            'Something exists where the backup target {0}'
                                            'should go'
                                        ).format(backupname)))
            os.rename(name, backupname)
        elif force:
            # Remove whatever is in the way
            if os.path.isfile(name):
                os.remove(name)
                ret['changes']['forced'] = 'File was forcibly replaced'
            elif os.path.islink(name):
                os.remove(name)
                ret['changes']['forced'] = 'Symlink was forcibly replaced'
            else:
                shutil.rmtree(name)
        else:
            if os.path.isfile(name):
                return _error(
                    ret,
                    'Specified location {0} exists and is a file'.format(name))
            elif os.path.islink(name):
                return _error(
                    ret,
                    'Specified location {0} exists and is a symlink'.format(name))

    if __opts__['test']:
        ret['result'], ret['comment'] = _check_directory(
            name,
            user,
            group,
            recurse or [],
            dir_mode,
            clean,
            require,
            exclude_pat)
        return ret

    if not os.path.isdir(name):
        # The dir does not exist, make it
        if not os.path.isdir(os.path.dirname(name)):
            # The parent directory does not exist, create them
            if makedirs:
                # Make sure the drive is mapped before trying to create the
                # path in windows
                if salt.utils.is_windows():
                    drive, path = os.path.splitdrive(name)
                    if not os.path.isdir(drive):
                        return _error(
                            ret, 'Drive {0} is not mapped'.format(drive))
                # Everything's good, create the path
                __salt__['file.makedirs'](
                    name, user=user, group=group, mode=dir_mode
                )
            else:
                return _error(
                    ret, 'No directory to create {0} in'.format(name))

        __salt__['file.mkdir'](
            name, user=user, group=group, mode=dir_mode
        )
        ret['changes'][name] = 'New Dir'

    if not os.path.isdir(name):
        return _error(ret, 'Failed to create directory {0}'.format(name))

    # Check permissions
    ret, perms = __salt__['file.check_perms'](name,
                                              ret,
                                              user,
                                              group,
                                              dir_mode,
                                              follow_symlinks)

    if recurse or clean:
        walk_l = list(os.walk(name))  # walk path only once and store the result
        # root: (dirs, files) structure, compatible for python2.6
        walk_d = {}
        for i in walk_l:
            walk_d[i[0]] = (i[1], i[2])

    if recurse:
        if not isinstance(recurse, list):
            ret['result'] = False
            ret['comment'] = '"recurse" must be formed as a list of strings'
        elif not set(['user', 'group', 'mode', 'ignore_files',
                      'ignore_dirs']) >= set(recurse):
            ret['result'] = False
            ret['comment'] = 'Types for "recurse" limited to "user", ' \
                             '"group", "mode", "ignore_files, and "ignore_dirs"'
        else:
            if 'ignore_files' in recurse and 'ignore_dirs' in recurse:
                ret['result'] = False
                ret['comment'] = 'Can not specify "recurse" options "ignore_files" ' \
                                 'and "ignore_dirs" at the same time.'
                return ret

            if 'user' in recurse:
                if user:
                    uid = __salt__['file.user_to_uid'](user)
                    # file.user_to_uid returns '' if user does not exist. Above
                    # check for user is not fatal, so we need to be sure user
                    # exists.
                    if isinstance(uid, string_types):
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
            if 'group' in recurse:
                if group:
                    gid = __salt__['file.group_to_gid'](group)
                    # As above with user, we need to make sure group exists.
                    if isinstance(gid, string_types):
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

            if 'mode' not in recurse:
                file_mode = None
                dir_mode = None

            if 'ignore_files' in recurse:
                ignore_files = True
            else:
                ignore_files = False

            if 'ignore_dirs' in recurse:
                ignore_dirs = True
            else:
                ignore_dirs = False

            for root, dirs, files in walk_l:
                if not ignore_files:
                    for fn_ in files:
                        full = os.path.join(root, fn_)
                        ret, perms = __salt__['file.check_perms'](
                            full,
                            ret,
                            user,
                            group,
                            file_mode,
                            follow_symlinks)
                if not ignore_dirs:
                    for dir_ in dirs:
                        full = os.path.join(root, dir_)
                        ret, perms = __salt__['file.check_perms'](
                            full,
                            ret,
                            user,
                            group,
                            dir_mode,
                            follow_symlinks)

    if clean:
        keep = _gen_keep_files(name, require, walk_d)
        log.debug('List of kept files when use file.directory with clean: %s',
                  keep)
        removed = _clean_dir(name, list(keep), exclude_pat)
        if removed:
            ret['changes']['removed'] = removed
            ret['comment'] = 'Files cleaned from directory {0}'.format(name)

    if not ret['comment']:
        ret['comment'] = 'Directory {0} updated'.format(name)

    if __opts__['test']:
        ret['comment'] = 'Directory {0} not updated'.format(name)
    elif not ret['changes'] and ret['result']:
        ret['comment'] = 'Directory {0} is in the correct state'.format(name)
    return ret


def recurse(name,
            source,
            clean=False,
            require=None,
            user=None,
            group=None,
            dir_mode=None,
            file_mode=None,
            sym_mode=None,
            template=None,
            context=None,
            defaults=None,
            env=None,
            include_empty=False,
            backup='',
            include_pat=None,
            exclude_pat=None,
            maxdepth=None,
            keep_symlinks=False,
            force_symlinks=False,
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
        The permissions mode to set on any directories created. Not supported on
        Windows

    file_mode
        The permissions mode to set on any files created. Not supported on
        Windows

    sym_mode
        The permissions mode to set on any symlink created. Not supported on
        Windows

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file. Supported templates are:
        `jinja`, `mako` and `wempy`.

    .. note::

        The template option is required when recursively applying templates.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    include_empty
        Set this to True if empty directories should also be created
        (default is False)

    include_pat
        When copying, include only this pattern from the source. Default
        is glob match; if prefixed with 'E@', then regexp match.
        Example:

        .. code-block:: yaml

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

        .. code-block:: yaml

          - exclude_pat: APPDATA*               :: glob matches APPDATA.01,
                                                   APPDATA.02,.. for exclusion
          - exclude_pat: E@(APPDATA)|(TEMPDATA) :: regexp matches APPDATA
                                                   or TEMPDATA for exclusion

    maxdepth
        When copying, only copy paths which are of depth `maxdepth` from the
        source path.
        Example:

        .. code-block:: yaml

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
    '''
    name = os.path.expanduser(name)

    user = _test_owner(kwargs, user=user)
    if salt.utils.is_windows():
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

    # Make sure that leading zeros stripped by YAML loader are added back
    dir_mode = __salt__['config.manage_mode'](dir_mode)
    file_mode = __salt__['config.manage_mode'](file_mode)

    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if isinstance(env, string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Boron', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

    # expand source into source_list
    source_list = _validate_str_list(source)

    for idx, val in enumerate(source_list):
        source_list[idx] = val.rstrip('/')

    for precheck in source_list:
        if not precheck.startswith('salt://'):
            return _error(ret, ('Invalid source {0!r} '
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
    source_rel = source.partition('://')[2]
    master_dirs = __salt__['cp.list_master_dirs'](__env__)
    if source_rel not in master_dirs \
            and not any((x for x in master_dirs
                         if x.startswith(source_rel + '/'))):
        ret['result'] = False
        ret['comment'] = (
            'The directory {0!r} does not exist on the salt fileserver '
            'in saltenv {1!r}'.format(source, __env__)
        )
        return ret

    # Verify the target directory
    if not os.path.isdir(name):
        if os.path.exists(name):
            # it is not a dir, but it exists - fail out
            return _error(
                ret, 'The path {0} exists and is not a directory'.format(name))
        if not __opts__['test']:
            __salt__['file.makedirs_perms'](
                name, user, group, int(str(dir_mode), 8) if dir_mode else None)

    def add_comment(path, comment):
        comments = ret['comment'].setdefault(path, [])
        if isinstance(comment, string_types):
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

    def manage_file(path, source):
        source = u'{0}|{1}'.format(source[:7], source[7:])
        if clean and os.path.exists(path) and os.path.isdir(path):
            _ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
            if __opts__['test']:
                _ret['comment'] = 'Replacing directory {0} with a ' \
                                  'file'.format(path)
                _ret['result'] = None
                merge_ret(path, _ret)
                return
            else:
                shutil.rmtree(path)
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
            user=user,
            group=group,
            mode=file_mode,
            template=template,
            makedirs=True,
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
                os.remove(path)
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

    # Process symlinks and return the updated filenames list
    def process_symlinks(filenames, symlinks):
        for lname, ltarget in symlinks.items():
            if not salt.utils.check_include_exclude(
                    os.path.relpath(lname, srcpath), include_pat, exclude_pat):
                continue
            srelpath = os.path.relpath(lname, srcpath)
            # Check for max depth
            if maxdepth is not None:
                srelpieces = srelpath.split('/')
                if not srelpieces[-1]:
                    srelpieces = srelpieces[:-1]
                if len(srelpieces) > maxdepth + 1:
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
            # Add the path to the keep set in case clean is set to True
            keep.add(os.path.join(name, srelpath))
        vdir.update(keep)
        return filenames

    keep = set()
    vdir = set()
    srcpath = source[7:]
    if not srcpath.endswith('/'):
        # we're searching for things that start with this *directory*.
        # use '/' since #master only runs on POSIX
        srcpath = srcpath + '/'
    fns_ = __salt__['cp.list_master'](__env__, srcpath)
    # If we are instructed to keep symlinks, then process them.
    if keep_symlinks:
        # Make this global so that emptydirs can use it if needed.
        symlinks = __salt__['cp.list_master_symlinks'](__env__, srcpath)
        fns_ = process_symlinks(fns_, symlinks)
    for fn_ in fns_:
        if not fn_.strip():
            continue

        # fn_ here is the absolute (from file_roots) source path of
        # the file to copy from; it is either a normal file or an
        # empty dir(if include_empty==true).

        relname = os.path.relpath(fn_, srcpath)
        if relname.startswith('..'):
            continue

        # Check for maxdepth of the relative path
        if maxdepth is not None:
            # Since paths are all master, just use POSIX separator
            relpieces = relname.split('/')
            # Handle empty directories (include_empty==true) by removing the
            # the last piece if it is an empty string
            if not relpieces[-1]:
                relpieces = relpieces[:-1]
            if len(relpieces) > maxdepth + 1:
                continue

        # - Check if it is to be excluded. Match only part of the path
        # relative to the target directory
        if not salt.utils.check_include_exclude(
                relname, include_pat, exclude_pat):
            continue
        dest = os.path.join(name, relname)
        dirname = os.path.dirname(dest)
        keep.add(dest)

        if dirname not in vdir:
            # verify the directory perms if they are set
            manage_directory(dirname)
            vdir.add(dirname)

        src = u'salt://{0}'.format(fn_)
        manage_file(dest, src)

    if include_empty:
        mdirs = __salt__['cp.list_master_dirs'](__env__, srcpath)
        for mdir in mdirs:
            if not salt.utils.check_include_exclude(
                    os.path.relpath(mdir, srcpath), include_pat, exclude_pat):
                continue
            mdest = os.path.join(name, os.path.relpath(mdir, srcpath))
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

            manage_directory(mdest)
            keep.add(mdest)

    keep = list(keep)
    if clean:
        # TODO: Use directory(clean=True) instead
        keep += _gen_keep_files(name, require)
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
    ret['comment'] = '\n'.join(u'\n#### {0} ####\n{1}'.format(
        k, v if isinstance(v, string_types) else '\n'.join(v)
    ) for (k, v) in six.iteritems(ret['comment'])).strip()

    if not ret['comment']:
        ret['comment'] = 'Recursively updated {0}'.format(name)

    if not ret['changes'] and ret['result']:
        ret['comment'] = 'The directory {0} is in the correct state'.format(
            name
        )

    return ret


def replace(name,
            pattern,
            repl,
            count=0,
            flags=0,
            bufsize=1,
            append_if_not_found=False,
            prepend_if_not_found=False,
            not_found_content=None,
            backup='.bak',
            show_changes=True):
    r'''
    Maintain an edit in a file.

    .. versionadded:: 0.17.0

    name
        Filesystem path to the file to be edited.

    pattern
        Python's `regular expression search <https://docs.python.org/2/library/re.html>`_.

    repl
        The replacement text.

    count
        Maximum number of pattern occurrences to be replaced.  Defaults to 0.
        If count is a positive integer n, no more than n occurrences will be
        replaced, otherwise all occurrences will be replaced.

    flags
        A list of flags defined in the :ref:`re module documentation <contents-of-module-re>`.
        Each list item should be a string that will correlate to the human-friendly flag name.
        E.g., ``['IGNORECASE', 'MULTILINE']``. Note: multiline searches must specify ``file``
        as the ``bufsize`` argument below. Defaults to 0 and can be a list or an int.

    bufsize
        How much of the file to buffer into memory at once. The default value ``1`` processes
        one line at a time. The special value ``file`` may be specified which will read the
        entire file into memory before processing. Note: multiline searches must specify ``file``
        buffering. Can be an int or a str.

    append_if_not_found
        If pattern is not found and set to ``True`` then, the content will be appended to the file.

        .. versionadded:: 2014.7.0

    prepend_if_not_found
        If pattern is not found and set to ``True`` then, the content will be prepended to the file.

        .. versionadded:: 2014.7.0

    not_found_content
        Content to use for append/prepend if not found. If ``None`` (default), uses ``repl``. Useful
        when ``repl``  uses references to group in pattern.

        .. versionadded:: 2014.7.0

    backup
        The file extension to use for a backup of the file before editing. Set to ``False`` to skip
        making a backup.

    show_changes
        Output a unified diff of the old file and the new file. If ``False`` return a boolean if any
        changes were made. Returns a boolean or a string.

        .. note:
            Using this option will store two copies of the file in-memory (the original version and
            the edited version) in order to generate the diff.

    For complex regex patterns it can be useful to avoid the need for complex quoting and escape
    sequences by making use of YAML's multiline string syntax.

    .. code-block:: yaml

        complex_search_and_replace:
          file.replace:
            # <...snip...>
            - pattern: |
                CentOS \(2.6.32[^\n]+\n\s+root[^\n]+\n\)+

    .. note::

       When using YAML multiline string syntax in ``pattern:``, make sure to
       also use that syntax in the ``repl:`` part, or you might loose line
       feeds.
    '''
    name = os.path.expanduser(name)

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.replace')

    check_res, check_msg = _check_file(name)
    if not check_res:
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
                                       show_changes=show_changes)

    if changes:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Changes would have been made:\ndiff:\n{0}'.format(changes)
        else:
            ret['result'] = True
            ret['comment'] = 'Changes were made'
            ret['changes'] = {'diff': changes}
    else:
        ret['result'] = True
        ret['comment'] = 'No changes needed to be made'

    return ret


def blockreplace(
        name,
        marker_start='#-- start managed zone --',
        marker_end='#-- end managed zone --',
        content='',
        append_if_not_found=False,
        prepend_if_not_found=False,
        backup='.bak',
        show_changes=True):
    '''
    Maintain an edit in a file in a zone delimited by two line markers

    .. versionadded:: 2014.1.0

    A block of content delimited by comments can help you manage several lines
    entries without worrying about old entries removal. This can help you
    maintaining an un-managed file containing manual edits.
    Note: this function will store two copies of the file in-memory
    (the original version and the edited version) in order to detect changes
    and only edit the targeted file if necessary.

    name
        Filesystem path to the file to be edited

    marker_start
        The line content identifying a line as the start of the content block.
        Note that the whole line containing this marker will be considered, so
        whitespace or extra content before or after the marker is included in
        final output

    marker_end
        The line content identifying a line as the end of the content block.
        Note that the whole line containing this marker will be considered, so
        whitespace or extra content before or after the marker is included in
        final output. Note: you can use file.accumulated and target this state.
        All accumulated data dictionaries content will be added as new lines in
        the content

    content
        The content to be used between the two lines identified by
        ``marker_start`` and ``marker_end``

    append_if_not_found
        If markers are not found and set to True then the markers and content
        will be appended to the file. Default is ``False``

    prepend_if_not_found
        If markers are not found and set to True then the markers and content
        will be prepended to the file. Default is ``False``

    backup
        The file extension to use for a backup of the file if any edit is made.
        Set this to ``False`` to skip making a backup.

    dry_run
        Don't make any edits to the file

    show_changes
        Output a unified diff of the old file and the new file. If ``False``
        return a boolean if any changes were made

    Example of usage with an accumulator and with a variable:

    .. code-block:: yaml

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

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.blockreplace')

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

    changes = __salt__['file.blockreplace'](
        name,
        marker_start,
        marker_end,
        content=content,
        append_if_not_found=append_if_not_found,
        prepend_if_not_found=prepend_if_not_found,
        backup=backup,
        dry_run=__opts__['test'],
        show_changes=show_changes
    )

    if changes:
        ret['changes'] = {'diff': changes}
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

    unanchor_regex = regex.lstrip('^').rstrip('$')

    # Make sure the pattern appears in the file before continuing
    if not __salt__['file.search'](name, regex):
        if __salt__['file.search'](name, unanchor_regex):
            ret['comment'] = 'Pattern already commented'
            ret['result'] = True
            return ret
        else:
            return _error(ret, '{0}: Pattern not found'.format(unanchor_regex))

    if __opts__['test']:
        ret['comment'] = 'File {0} is set to be updated'.format(name)
        ret['result'] = None
        return ret
    with salt.utils.fopen(name, 'rb') as fp_:
        slines = fp_.readlines()

    # Perform the edit
    __salt__['file.comment_line'](name, regex, char, True, backup)

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    # Check the result
    ret['result'] = __salt__['file.search'](name, unanchor_regex)

    if slines != nlines:
        if not salt.utils.istextfile(name):
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
            name, '^[ \t]*{0}'.format(regex.lstrip('^'))):
        ret['comment'] = 'Pattern already uncommented'
        ret['result'] = True
        return ret
    elif __salt__['file.search'](
            name, '{0}[ \t]*{1}'.format(char, regex.lstrip('^'))):
        # Line exists and is commented
        pass
    else:
        return _error(ret, '{0}: Pattern not found'.format(regex))

    if __opts__['test']:
        ret['comment'] = 'File {0} is set to be updated'.format(name)
        ret['result'] = None
        return ret

    with salt.utils.fopen(name, 'rb') as fp_:
        slines = fp_.readlines()

    # Perform the edit
    __salt__['file.comment_line'](name, regex, char, False, backup)

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    # Check the result
    ret['result'] = __salt__['file.search'](
        name, '^[ \t]*{0}'.format(regex.lstrip('^'))
    )

    if slines != nlines:
        if not salt.utils.istextfile(name):
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
           context=None):
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

        The file can contain several checksums for several files. Each line
        must contain both the file name and the hash.  If no file name is
        matched, the first hash encountered will be used, otherwise the most
        secure hash with the correct source file name will be used.

        Debian file type ``*.dsc`` is supported.

        Examples:

        .. code-block:: text

            /etc/rc.conf ef6e82e4006dee563d98ada2a2a80a27
            sha254c8525aee419eb649f0233be91c151178b30f0dff8ebbdcc8de71b1d5c8bcc06a  /etc/resolv.conf
            ead48423703509d37c4a90e6a0d53e143b6fc268

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

    template : ``jinja``
        The named templating engine will be used to render the appended-to
        file. Defaults to jinja.

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
    name = os.path.expanduser(name)

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.append')

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
            __salt__['file.makedirs'](name)
            check_res, check_msg = _check_directory(
                dirname, None, None, False, None, False, False, None
            )
            if not check_res:
                return _error(ret, check_msg)

        # Make sure that we have a file
        __salt__['file.touch'](name)

    check_res, check_msg = _check_file(name)
    if not check_res:
        touch(name, makedirs=makedirs)
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

    with salt.utils.fopen(name, 'rb') as fp_:
        slines = fp_.readlines()

    count = 0
    test_lines = []

    try:
        for chunk in text:

            if __salt__['file.contains_regex_multiline'](
                    name, salt.utils.build_whitespace_split_regex(chunk)):
                continue

            lines = chunk.splitlines()

            for line in lines:
                if __opts__['test']:
                    ret['comment'] = 'File {0} is set to be updated'.format(name)
                    ret['result'] = None
                    test_lines.append('{0}\n'.format(line))
                else:
                    __salt__['file.append'](name, line)
                count += 1
    except TypeError:
        return _error(ret, 'No text found to append. Nothing appended')

    if __opts__['test']:
        nlines = slines + test_lines
        ret['result'] = None
        if slines != nlines:
            if not salt.utils.istextfile(name):
                ret['changes']['diff'] = 'Replace binary file'
            else:
                # Changes happened, add them
                ret['changes']['diff'] = (
                    ''.join(difflib.unified_diff(slines, nlines))
                )
        else:
            ret['comment'] = 'File {0} is in correct state'.format(name)
            ret['result'] = True
        return ret

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    if slines != nlines:
        if not salt.utils.istextfile(name):
            ret['changes']['diff'] = 'Replace binary file'
        else:
            # Changes happened, add them
            ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
            )

    if count:
        ret['comment'] = 'Appended {0} lines'.format(count)
    else:
        ret['comment'] = 'File {0} is in correct state'.format(name)
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
            context=None):
    '''
    Ensure that some text appears at the beginning of a file

    The text will not be prepended again if it already exists in the file. You
    may specify a single line of text or a list of lines to append.

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

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
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
            __salt__['file.makedirs'](name)
            check_res, check_msg = _check_directory(
                dirname, None, None, False, None, False, False, None
            )
            if not check_res:
                return _error(ret, check_msg)

        # Make sure that we have a file
        __salt__['file.touch'](name)

    check_res, check_msg = _check_file(name)
    if not check_res:
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

    with salt.utils.fopen(name, 'rb') as fp_:
        slines = fp_.readlines()

    count = 0
    test_lines = []

    preface = []
    for chunk in text:

        if __salt__['file.contains_regex_multiline'](
                name, salt.utils.build_whitespace_split_regex(chunk)):
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
            if not salt.utils.istextfile(name):
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

    __salt__['file.prepend'](name, *preface)

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    if slines != nlines:
        if not salt.utils.istextfile(name):
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
          hash=None,
          options='',
          dry_run_first=True,
          env=None,
          **kwargs):
    '''
    Apply a patch to a file.

    .. note::

        A suitable ``patch`` executable must be available on the minion when
        using this state function.

    name
        The file to with the patch will be applied.

    source
        The source patch to download to the minion, this source file must be
        hosted on the salt master server. If the file is located in the
        directory named spam, and is called eggs, the source string is
        salt://spam/eggs. A source is required.

    hash
        Hash of the patched file. If the hash of the target file matches this
        value then the patch is assumed to have been applied. The hash string
        is the hash algorithm followed by the hash of the file:
        md5=e138491e9d5b97023cea823fe17bac22

    options
        Extra options to pass to patch.

    dry_run_first : ``True``
        Run patch with ``--dry-run`` first to check if it will apply cleanly.

    env
        Specify the environment from which to retrieve the patch file indicated
        by the ``source`` parameter. If not provided, this defaults to the
        environment from which the state is being executed.

    Usage:

    .. code-block:: yaml

        # Equivalent to ``patch --forward /opt/file.txt file.patch``
        /opt/file.txt:
          file.patch:
            - source: salt://file.patch
            - hash: md5=e138491e9d5b97023cea823fe17bac22
    '''
    name = os.path.expanduser(name)

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.patch')
    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)
    if not source:
        return _error(ret, 'Source is required')
    if hash is None:
        return _error(ret, 'Hash is required')

    if __salt__['file.check_hash'](name, hash):
        ret.update(result=True, comment='Patch is already applied')
        return ret

    if isinstance(env, string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Boron', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

    # get cached file or copy it to cache
    cached_source_path = __salt__['cp.cache_file'](source, __env__)
    if not cached_source_path:
        ret['comment'] = ('Unable to cache {0} from saltenv {1!r}'
                          .format(source, __env__))
        return ret

    log.debug(
        'State patch.applied cached source {0} -> {1}'.format(
            source, cached_source_path
        )
    )

    if dry_run_first or __opts__['test']:
        ret['changes'] = __salt__['file.patch'](
            name, cached_source_path, options=options, dry_run=True
        )
        if __opts__['test']:
            ret['comment'] = 'File {0} will be patched'.format(name)
            ret['result'] = None
            return ret
        if ret['changes']['retcode']:
            return ret

    ret['changes'] = __salt__['file.patch'](
        name, cached_source_path, options=options
    )
    ret['result'] = not ret['changes']['retcode']
    if ret['result'] and not __salt__['file.check_hash'](name, hash):
        ret.update(
            result=False,
            comment='File {0} hash mismatch after patch was applied'.format(
                name
            )
        )
    return ret


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
        ret['result'], ret['comment'] = _check_touch(name, atime, mtime)
        return ret

    if makedirs:
        __salt__['file.makedirs'](name)
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


def copy(
        name,
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
    If the source file exists on the system, copy it to the named file. The
    named file will not be overwritten if it already exists unless the force
    option is set to True.

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
        after copying. Default is ``False``. If ``preseve`` is set to ``True``,
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
        Not supported on Windows

    subdir
        .. versionadded:: 2015.5.0

        If the name is a directory then place the file inside the named
        directory
    '''
    name = os.path.expanduser(name)
    source = os.path.expanduser(source)

    ret = {
        'name': name,
        'changes': {},
        'comment': 'Copied "{0}" to "{1}"'.format(source, name),
        'result': True}
    if not name:
        return _error(ret, 'Must provide name to file.comment')

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

        if salt.utils.is_windows():
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
            hash1 = salt.utils.get_hash(name)
            hash2 = salt.utils.get_hash(source)
            if hash1 == hash2:
                changed = False
        if not force:
            changed = False
        elif not __opts__['test'] and changed:
            # Remove the destination to prevent problems later
            try:
                if os.path.islink(name):
                    os.unlink(name)
                elif os.path.isfile(name):
                    os.remove(name)
                else:
                    shutil.rmtree(name)
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
            __salt__['file.makedirs'](name)
        else:
            return _error(
                ret,
                'The target directory {0} is not present'.format(dname))
    # All tests pass, move the file into place
    try:
        shutil.copy(source, name)
        ret['changes'] = {name: source}
        # Preserve really means just keep the behavior of the cp command. If
        # the filesystem we're copying to is squashed or doesn't support chown
        # then we shouldn't be checking anything.
        if not preserve:
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
            ret['result'] = False
            return ret
        elif not __opts__['test']:
            # Remove the destination to prevent problems later
            try:
                if os.path.islink(name):
                    os.unlink(name)
                elif os.path.isfile(name):
                    os.remove(name)
                else:
                    shutil.rmtree(name)
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
            __salt__['file.makedirs'](name)
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
    if isinstance(text, string_types):
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


def _merge_dict(obj, k, v):
    changes = {}
    if k in obj:
        if isinstance(obj[k], list):
            if isinstance(v, list):
                for a in v:
                    if a not in obj[k]:
                        changes[k] = a
                        obj[k].append(a)
            else:
                if obj[k] != v:
                    changes[k] = v
                    obj[k] = v
        elif isinstance(obj[k], dict):
            if isinstance(v, dict):
                for a, b in six.iteritems(v):
                    if isinstance(b, dict) or isinstance(b, list):
                        updates = _merge_dict(obj[k], a, b)
                        for x, y in six.iteritems(updates):
                            changes[k + "." + x] = y
                    else:
                        if obj[k][a] != b:
                            changes[k + "." + a] = b
                            obj[k][a] = b
            else:
                if obj[k] != v:
                    changes[k] = v
                    obj[k] = v
        else:
            if obj[k] != v:
                changes[k] = v
                obj[k] = v
    else:
        changes[k] = v
        obj[k] = v
    return changes


def serialize(name,
              dataset=None,
              dataset_pillar=None,
              user=None,
              group=None,
              mode=None,
              env=None,
              backup='',
              makedirs=False,
              show_diff=True,
              create=True,
              merge_if_exists=False,
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

        .. versionadded:: FIXME

    formatter
        Write the data as this format. Supported output formats:

        * JSON
        * YAML
        * Python (via pprint.pformat)

    user
        The user to own the directory, this defaults to the user salt is
        running as on the minion

    group
        The group ownership set for the directory, this defaults to the group
        salt is running as on the minion

    mode
        The permissions to set on this file, aka 644, 0775, 4664

    backup
        Overrides the default backup mode for this specific file.

    makedirs
        Create parent directories for destination file.

        .. versionadded:: 2014.1.3

    show_diff
        If set to False, the diff will not be shown.

    create
        Default is True, if create is set to False then the file will only be
        managed if the file already exists on the system.

    merge_if_exists
        Default is False, if merge_if_exists is True then the existing file will
        be parsed and the dataset passed in will be merged with the existing
        content

        .. versionadded:: 2014.7.0

    For example, this state:

    .. code-block:: yaml

        /etc/dummy/package.json:
          file.serialize:
            - dataset:
                name: naive
                description: A package using naive versioning
                author: A confused individual <iam@confused.com>
                dependencies:
                    express: >= 1.2.0
                    optimist: >= 0.1.0
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
    name = os.path.expanduser(name)

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if not name:
        return _error(ret, 'Must provide name to file.serialize')

    if isinstance(env, string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Boron', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

    if not create:
        if not os.path.isfile(name):
            # Don't create a file that is not already present
            ret['comment'] = ('File {0} is not present and is not set for '
                              'creation').format(name)
            return ret

    formatter = kwargs.pop('formatter', 'yaml').lower()

    if len([_f for _f in [dataset, dataset_pillar] if _f]) > 1:
        return _error(
            ret, 'Only one of \'dataset\' and \'dataset_pillar\' is permitted')

    if dataset_pillar:
        dataset = __salt__['pillar.get'](dataset_pillar)

    if dataset is None:
        return _error(
            ret, 'Neither \'dataset\' nor \'dataset_pillar\' was defined')

    if merge_if_exists:
        if os.path.isfile(name):
            if formatter == 'yaml':
                with salt.utils.fopen(name, 'r') as fhr:
                    existing_data = yaml.safe_load(fhr)
            elif formatter == 'json':
                with salt.utils.fopen(name, 'r') as fhr:
                    existing_data = json.load(fhr)
            else:
                return {'changes': {},
                        'comment': ('{0} format is not supported for merging'
                                    .format(formatter.capitalize())),
                        'name': name,
                        'result': False}

            if existing_data is not None:
                for k, v in six.iteritems(dataset):
                    if k in existing_data:
                        ret['changes'].update(_merge_dict(existing_data, k, v))
                    else:
                        ret['changes'][k] = v
                        existing_data[k] = v
                dataset = existing_data

    if formatter == 'yaml':
        contents = yaml_serializer.serialize(dataset,
                                             default_flow_style=False)
    elif formatter == 'json':
        contents = json_serializer.serialize(dataset,
                                             indent=2,
                                             separators=(',', ': '),
                                             sort_keys=True)
    elif formatter == 'python':
        # round-trip this through JSON to avoid OrderedDict types
        # there's probably a more performant way to do this...
        # TODO remove json round-trip when all dataset will use
        # utils.serializers
        contents = pprint.pformat(
            json.loads(
                json.dumps(dataset),
                object_hook=salt.utils.decode_dict
            )
        )
    else:
        return {'changes': {},
                'comment': '{0} format is not supported'.format(
                    formatter.capitalize()),
                'name': name,
                'result': False
                }

    if __opts__['test']:
        ret['changes'] = __salt__['file.check_managed_changes'](
            name=name,
            source=None,
            source_hash={},
            user=user,
            group=group,
            mode=mode,
            template=None,
            context=None,
            defaults=None,
            saltenv=__env__,
            contents=contents,
            **kwargs
        )

        if ret['changes']:
            ret['result'] = None
            ret['comment'] = 'Dataset will be serialized and stored into {0}'.format(
                name)
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
                                        saltenv=__env__,
                                        backup=backup,
                                        makedirs=makedirs,
                                        template=None,
                                        show_diff=show_diff,
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
                'File exists and is not a character device {0}. Cowardly '
                'refusing to continue'.format(name)
            )

        # Check if it is a character device
        elif not __salt__['file.is_chrdev'](name):
            if __opts__['test']:
                ret['comment'] = (
                    'Character device {0} is set to be created'
                ).format(name)
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
                    'major/minor {1}/{2}. Cowardly refusing to continue'
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
                'File exists and is not a block device {0}. Cowardly '
                'refusing to continue'.format(name)
            )

        # Check if it is a block device
        elif not __salt__['file.is_blkdev'](name):
            if __opts__['test']:
                ret['comment'] = (
                    'Block device {0} is set to be created'
                ).format(name)
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
                    '{1}/{2}. Cowardly refusing to continue'.format(
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
                'File exists and is not a fifo pipe {0}. Cowardly refusing '
                'to continue'.format(name)
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
            'Node type unavailable: {0!r}. Available node types are '
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
    if __salt__['cmd.retcode'](_cmd, **check_cmd_opts) != 0:
        return {'comment': 'check_cmd execution failed',
                'skip_watch': True,
                'result': False}

    # No reason to stop, return True
    return True

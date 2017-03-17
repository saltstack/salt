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
    :ref:`backup_mode documentation <file-state-backups>`.

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

The ``names`` parameter, which is part of the state compiler, can be used to
expand the contents of a single state declaration into multiple, single state
declarations. Each item in the ``names`` list receives its own individual state
``name`` and is converted into its own low-data structure. This is a convenient
way to manage several files with similar attributes.

There is more documentation about this feature in the
:ref:`Names declaration<names-declaration>` section of the
 :ref:`Highstate docs<states-highstate>`.

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

# Import python libs
from __future__ import absolute_import
import difflib
import itertools
import logging
import os
import shutil
import traceback
from collections import Iterable, Mapping

# Import salt libs
import salt.loader
import salt.payload
import salt.utils
import salt.utils.templates
import salt.utils.url
from salt.utils.locales import sdecode
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import zip_longest

log = logging.getLogger(__name__)

COMMENT_REGEX = r'^([[:space:]]*){0}[[:space:]]?'
__NOT_FOUND = object()


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
            with salt.utils.fopen(path, 'rb') as f:
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
        with salt.utils.fopen(_get_accumulator_filepath(), 'w+b') as f:
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
                # A requirement should match either the ID and the name of
                # another state.
                if low['name'] == comp['file'] or low['__id__'] == comp['file']:
                    fn = low['name']
                    if os.path.isdir(fn):
                        if _is_child(fn, name):
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
                if fn_ in ['/', ''.join([os.path.splitdrive(fn_)[0], '\\\\'])]:
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
                    __salt__['file.remove'](nfn)

    for roots, dirs, files in os.walk(root):
        for name in itertools.chain(dirs, files):
            _delete_not_kept(os.path.join(roots, name))
    return list(removed)


def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


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
        try:
            recurse_set = _get_recurse_set(recurse)
        except (TypeError, ValueError) as exc:
            return False, '{0}'.format(exc), changes
        if 'user' not in recurse_set:
            user = None
        if 'group' not in recurse_set:
            group = None
        if 'mode' not in recurse_set:
            mode = None
        check_files = 'ignore_files' not in recurse_set
        check_dirs = 'ignore_dirs' not in recurse_set
        for root, dirs, files in walk_l:
            if check_files:
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
            if check_dirs:
                for name_ in dirs:
                    path = os.path.join(root, name_)
                    fchange = _check_dir_meta(path, user, group, mode)
                    if fchange:
                        changes[path] = fchange
    # Recurse skips root (we always do dirs, not root), so always check root:
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
            for key, val in six.iteritems(changes[fn_]):
                comments.append('{0}: {1} - {2}\n'.format(fn_, key, val))
        return None, ''.join(comments), changes
    return True, 'The directory {0} is in the correct state'.format(name), changes


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
    if (user is not None
            and user != stats['user']
            and user != stats.get('uid')):
        changes['user'] = user
    if (group is not None
            and group != stats['group']
            and group != stats.get('gid')):
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
    pchanges = {}
    if not os.path.exists(name) and not __salt__['file.is_link'](name):
        pchanges['new'] = name
        return None, 'Symlink {0} to {1} is set for creation'.format(
            name, target
        ), pchanges
    if __salt__['file.is_link'](name):
        if __salt__['file.readlink'](name) != target:
            pchanges['change'] = name
            return None, 'Link {0} target is set to be changed to {1}'.format(
                name, target
            ), pchanges
        else:
            result = True
            msg = 'The symlink {0} is present'.format(name)
            if not _check_symlink_ownership(name, user, group):
                result = None
                pchanges['ownership'] = '{0}:{1}'.format(*_get_symlink_ownership(name))
                msg += (
                    ', but the ownership of the symlink would be changed '
                    'from {2}:{3} to {0}:{1}'
                ).format(user, group, *_get_symlink_ownership(name))
            return result, msg, pchanges
    else:
        if force:
            return None, ('The file or directory {0} is set for removal to '
                          'make way for a new symlink targeting {1}'
                          .format(name, target)), pchanges
        return False, ('File or directory exists where the symlink {0} '
                       'should be. Did you mean to use force?'.format(name)), pchanges


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
    if isinstance(arg, six.string_types):
        ret = [arg]
    elif isinstance(arg, Iterable) and not isinstance(arg, Mapping):
        ret = []
        for item in arg:
            if isinstance(item, six.string_types):
                ret.append(item)
            else:
                ret.append(str(item))
    else:
        ret = [str(arg)]
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

    presult, pcomment, ret['pchanges'] = _symlink_check(name,
                                                        target,
                                                        force,
                                                        user,
                                                        group)
    if __opts__['test']:
        ret['result'] = presult
        ret['comment'] = pcomment
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
        if os.path.normpath(__salt__['file.readlink'](name)) != os.path.normpath(target):
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
                else:
                    __salt__['file.remove'](backupname)
            os.rename(name, backupname)
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
    state module. If a directory is supplied, it will be recursively deleted.

    name
        The path which should be deleted
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'pchanges': {},
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
        ret['pchanges']['removed'] = name
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
        ret['pchanges']['removed'] = name
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Directory {0} is set for removal'.format(name)
            return ret
        try:
            __salt__['file.remove'](name)
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
           'pchanges': {},
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
           'pchanges': {},
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
            show_diff=None,
            show_changes=True,
            create=True,
            contents=None,
            contents_pillar=None,
            contents_grains=None,
            contents_newline=True,
            contents_delimiter=':',
            allow_empty=True,
            follow_symlinks=True,
            check_cmd=None,
            skip_verify=False,
            **kwargs):
    '''
    Manage a given file, this function allows for a file to be downloaded from
    the salt master and potentially run through a templating system.

    name
        The location of the file to manage

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

    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

    group
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion On Windows, this is ignored

    mode
        The permissions to set on this file, aka 644, 0775, 4664. Not supported
        on Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

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
        will be assigned permissions from the 'mode' argument.

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

    show_diff
        DEPRECATED: Please use show_changes.

        If set to ``False``, the diff will not be shown in the return data if
        changes are made.

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
                - source: salt://sudoers/files/sudoers.jinja
                - template: jinja
                - check_cmd: /usr/sbin/visudo -c -f

        **NOTE**: This ``check_cmd`` functions differently than the requisite
        ``check_cmd``.

    skip_verify : False
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``) will be skipped, and the ``source_hash``
        argument will be ignored.

        .. versionadded:: 2016.3.0
    '''
    name = os.path.expanduser(name)

    ret = {'changes': {},
           'pchanges': {},
           'comment': '',
           'name': name,
           'result': True}

    content_sources = (contents, contents_pillar, contents_grains)
    contents_count = len(
        [x for x in content_sources if x is not None]
    )

    if source and contents_count > 0:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'contents\', '
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

    # Use this below to avoid multiple '\0' checks and save some CPU cycles
    if contents_pillar is not None:
        use_contents = __salt__['pillar.get'](contents_pillar, __NOT_FOUND)
        if use_contents is __NOT_FOUND:
            return _error(
                ret,
                'Pillar {0} does not exist'.format(contents_pillar)
            )

    elif contents_grains is not None:
        use_contents = __salt__['grains.get'](contents_grains, __NOT_FOUND)
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

        contents_are_binary = \
            isinstance(use_contents, six.string_types) and '\0' in use_contents
        if contents_are_binary:
            contents = use_contents
        else:
            validated_contents = _validate_str_list(use_contents)
            if not validated_contents:
                return _error(
                    ret,
                    'Contents specified by contents/contents_pillar/'
                    'contents_grains is not a string or list of strings, and '
                    'is not binary data. SLS is likely malformed.'
                )
            contents = os.linesep.join(validated_contents)
            if contents_newline and not contents.endswith(os.linesep):
                contents += os.linesep
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

    if isinstance(env, six.string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Carbon and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Carbon', msg)
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

    if show_diff is not None:
        show_changes = show_diff
        msg = (
            'The \'show_diff\' argument to the file.managed state has been '
            'deprecated, please use \'show_changes\' instead.'
        )
        salt.utils.warn_until('Carbon', msg)

    try:
        if __opts__['test']:
            if 'file.check_managed_changes' in __salt__:
                ret['pchanges'] = __salt__['file.check_managed_changes'](
                    name,
                    source,
                    source_hash,
                    source_hash_name,
                    user,
                    group,
                    mode,
                    template,
                    context,
                    defaults,
                    __env__,
                    contents,
                    skip_verify,
                    **kwargs
                )
            if ret['pchanges']:
                ret['result'] = None
                ret['comment'] = 'The file {0} is set to be changed'.format(name)
                if show_changes and 'diff' in ret['pchanges']:
                    ret['changes']['diff'] = ret['pchanges']['diff']
                if not show_changes:
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
        tmp_filename = salt.utils.mkstemp()

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
                __env__,
                backup,
                makedirs,
                template,
                show_changes,
                contents,
                dir_mode,
                follow_symlinks,
                skip_verify)
        except Exception as exc:
            ret['changes'] = {}
            log.debug(traceback.format_exc())
            if os.path.isfile(tmp_filename):
                os.remove(tmp_filename)
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
                if os.path.isfile(tmp_filename):
                    os.remove(tmp_filename)
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
                show_changes,
                contents,
                dir_mode,
                follow_symlinks,
                skip_verify)
        except Exception as exc:
            ret['changes'] = {}
            log.debug(traceback.format_exc())
            return _error(ret, 'Unable to manage file: {0}'.format(exc))
        finally:
            if tmp_filename and os.path.isfile(tmp_filename):
                os.remove(tmp_filename)


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
                  - ignore_dirs

        .. versionadded:: 2015.5.0

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
           'pchanges': {},
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

    # Check for existing file or symlink
    if os.path.isfile(name) or (not allow_symlink and os.path.islink(name)):
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
                os.remove(name)
                ret['changes']['forced'] = 'File was forcibly replaced'
            elif __salt__['file.is_link'](name):
                __salt__['file.remove'](name)
                ret['changes']['forced'] = 'Symlink was forcibly replaced'
            else:
                __salt__['file.remove'](name)
        else:
            if os.path.isfile(name):
                return _error(
                    ret,
                    'Specified location {0} exists and is a file'.format(name))
            elif os.path.islink(name):
                return _error(
                    ret,
                    'Specified location {0} exists and is a symlink'.format(name))
    presult, pcomment, ret['pchanges'] = _check_directory(
        name,
        user,
        group,
        recurse or [],
        dir_mode,
        clean,
        require,
        exclude_pat)

    if __opts__['test']:
        ret['result'] = presult
        ret['comment'] = pcomment
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

    errors = []
    if recurse or clean:
        walk_l = list(os.walk(name))  # walk path only once and store the result
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
            if user:
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
            if group:
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
                        ret, _ = __salt__['file.check_perms'](
                            full,
                            ret,
                            user,
                            group,
                            file_mode,
                            follow_symlinks)
                    except CommandExecutionError as exc:
                        if not exc.strerror.endswith('does not exist'):
                            errors.append(exc.strerror)
            if check_dirs:
                for dir_ in dirs:
                    full = os.path.join(root, dir_)
                    try:
                        ret, _ = __salt__['file.check_perms'](
                            full,
                            ret,
                            user,
                            group,
                            dir_mode,
                            follow_symlinks)
                    except CommandExecutionError as exc:
                        if not exc.strerror.endswith('does not exist'):
                            errors.append(exc.strerror)

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

    if errors:
        ret['result'] = False
        ret['comment'] += '\n\nThe following errors were encountered:\n'
        for error in errors:
            ret['comment'] += '\n- {0}'.format(error)
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
        Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    file_mode
        The permissions mode to set on any files created. Not supported on
        Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    sym_mode
        The permissions mode to set on any symlink created. Not supported on
        Windows.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

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
    name = os.path.expanduser(sdecode(name))

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
        'pchanges': {},
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

    if isinstance(env, six.string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Carbon and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Carbon', msg)
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
    srcpath, senv = salt.utils.url.parse(source)
    if senv is None:
        senv = __env__
    master_dirs = __salt__['cp.list_master_dirs'](saltenv=senv)
    if srcpath not in master_dirs \
            and not any((x for x in master_dirs
                         if x.startswith(srcpath + '/'))):
        ret['result'] = False
        ret['comment'] = (
            'The directory {0!r} does not exist on the salt fileserver '
            'in saltenv {1!r}'.format(srcpath, senv)
        )
        return ret

    # Verify the target directory
    if not os.path.isdir(name):
        if os.path.exists(name):
            # it is not a dir, but it exists - fail out
            return _error(
                ret, 'The path {0} exists and is not a directory'.format(name))
        if not __opts__['test']:
            __salt__['file.makedirs_perms'](name, user, group, dir_mode)

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

    def manage_file(path, source):
        if clean and os.path.exists(path) and os.path.isdir(path):
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

    # Process symlinks and return the updated filenames list
    def process_symlinks(filenames, symlinks):
        for lname, ltarget in six.iteritems(symlinks):
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
    if not srcpath.endswith('/'):
        # we're searching for things that start with this *directory*.
        # use '/' since #master only runs on POSIX
        srcpath = srcpath + '/'
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

        relname = sdecode(os.path.relpath(fn_, srcpath))
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

        # Check if it is to be excluded. Match only part of the path
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

        src = salt.utils.url.create(fn_, saltenv=senv)
        manage_file(dest, src)

    if include_empty:
        mdirs = __salt__['cp.list_master_dirs'](senv, srcpath)
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
        k, v if isinstance(v, six.string_types) else '\n'.join(v)
    ) for (k, v) in six.iteritems(ret['comment'])).strip()

    if not ret['comment']:
        ret['comment'] = 'Recursively updated {0}'.format(name)

    if not ret['changes'] and ret['result']:
        ret['comment'] = 'The directory {0} is in the correct state'.format(
            name
        )

    return ret


def line(name, content, match=None, mode=None, location=None,
         before=None, after=None, show_changes=True, backup=False,
         quiet=False, indent=True):
    '''
    Line-based editing of a file.

    .. versionadded:: 2015.8.0

    name
        Filesystem path to the file to be edited.

    content
        Content of the line.

    match
        Match the target line for an action by
        a fragment of a string or regular expression.

        If neither ``before`` nor ``after`` are provided, and ``match``
        is also ``None``, match becomes the ``content`` value.

    mode
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

    location
        Defines where to place content in the line. Note this option is only
        used when ``mode=insert`` is specified. If a location is passed in, it
        takes precedence over both the ``before`` and ``after`` kwargs. Valid
        locations are:

        - start
            Place the content at the beginning of the file.
        - end
            Place the content at the end of the file.

    before
        Regular expression or an exact case-sensitive fragment of the string.
        This option is only used when either the ``ensure`` or ``insert`` mode
        is defined.

    after
        Regular expression or an exact case-sensitive fragment of the string.
        This option is only used when either the ``ensure`` or ``insert`` mode
        is defined.

    show_changes
        Output a unified diff of the old file and the new file.
        If ``False`` return a boolean if any changes were made.
        Default is ``True``

        .. note::
            Using this option will store two copies of the file in-memory
            (the original version and the edited version) in order to generate the diff.

    backup
        Create a backup of the original file with the extension:
        "Year-Month-Day-Hour-Minutes-Seconds".

    quiet
        Do not raise any exceptions. E.g. ignore the fact that the file that is
        tried to be edited does not exist and nothing really happened.

    indent
        Keep indentation with the previous line. This option is not considered when
        the ``delete`` mode is specified.

    .. code-block: yaml

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
           'pchanges': {},
           'result': True,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.line')

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    changes = __salt__['file.line'](
        name, content, match=match, mode=mode, location=location,
        before=before, after=after, show_changes=show_changes,
        backup=backup, quiet=quiet, indent=indent)
    if changes:
        ret['pchanges']['diff'] = changes
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Changes would be made:\ndiff:\n{0}'.format(changes)
        else:
            ret['result'] = True
            ret['comment'] = 'Changes were made'
            ret['changes'] = {'diff': changes}
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
            ignore_if_missing=False):
    r'''
    Maintain an edit in a file.

    .. versionadded:: 0.17.0

    name
        Filesystem path to the file to be edited.

    pattern
        A regular expression, to be matched using Python's
        :py:func:`~re.search`.

    repl
        The replacement text

    count
        Maximum number of pattern occurrences to be replaced.  Defaults to 0.
        If count is a positive integer n, no more than n occurrences will be
        replaced, otherwise all occurrences will be replaced.

    flags
        A list of flags defined in the :ref:`re module documentation
        <contents-of-module-re>`. Each list item should be a string that will
        correlate to the human-friendly flag name. E.g., ``['IGNORECASE',
        'MULTILINE']``. Optionally, ``flags`` may be an int, with a value
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

    For complex regex patterns, it can be useful to avoid the need for complex
    quoting and escape sequences by making use of YAML's multiline string
    syntax.

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

    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': True,
           'comment': ''}
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
                                       show_changes=show_changes,
                                       ignore_if_missing=ignore_if_missing)

    if changes:
        ret['pchanges']['diff'] = changes
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

    template
        The named templating engine will be used to render the downloaded file.
        Defaults to ``jinja``. The following templates are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

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

    ret = {'name': name,
           'changes': {},
           'pchanges': {},
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
            content += str(item)

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
        ret['pchanges'] = {'diff': changes}
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Changes would be made'
        else:
            ret['changes'] = {'diff': changes}
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
           'pchanges': {},
           'result': False,
           'comment': ''}
    if not name:
        return _error(ret, 'Must provide name to file.comment')

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    unanchor_regex = regex.lstrip('^').rstrip('$')
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

    ret['pchanges'][name] = 'updated'
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
    ret['result'] = __salt__['file.search'](name, unanchor_regex, multiline=True)

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
           'pchanges': {},
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

    ret['pchanges'][name] = 'updated'
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
        name,
        '^[ \t]*{0}'.format(regex.lstrip('^')),
        multiline=True
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
            'pchanges': {},
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
        if not __salt__['file.directory_exists'](dirname):
            __salt__['file.makedirs'](name)
            check_res, check_msg, ret['pchanges'] = _check_directory(
                dirname, None, None, False, None, False, False, None
            )
            if not check_res:
                return _error(ret, check_msg)

    check_res, check_msg = _check_file(name)
    if not check_res:
        # Try to create the file
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
        slines = fp_.read().splitlines()

    append_lines = []
    try:
        for chunk in text:
            if ignore_whitespace:
                if __salt__['file.search'](
                        name,
                        salt.utils.build_whitespace_split_regex(chunk),
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
            if not salt.utils.istextfile(name):
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

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.read().splitlines()

    if slines != nlines:
        if not salt.utils.istextfile(name):
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

    ret = {'name': name,
           'changes': {},
           'pchanges': {},
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
            __salt__['file.makedirs'](name)
            check_res, check_msg, ret['pchanges'] = _check_directory(
                dirname, None, None, False, None, False, False, None
            )
            if not check_res:
                return _error(ret, check_msg)

    check_res, check_msg = _check_file(name)
    if not check_res:
        # Try to create the file
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

    preface = []
    for chunk in text:

        if __salt__['file.search'](
                name,
                salt.utils.build_whitespace_split_regex(chunk),
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
    Apply a patch to a file or directory.

    .. note::

        A suitable ``patch`` executable must be available on the minion when
        using this state function.

    name
        The file or directory to which the patch will be applied.

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

    if hash and __salt__['file.check_hash'](name, hash):
        ret.update(result=True, comment='Patch is already applied')
        return ret

    if isinstance(env, six.string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Carbon and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Carbon', msg)
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
    if ret['result'] and hash and not __salt__['file.check_hash'](name, hash):
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

        .. versionadded:: 2015.8.0

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
        The permissions to set on this file, aka 644, 0775, 4664.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

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

    default_serializer_opts = {'yaml.serialize': {'default_flow_style': False},
                              'json.serialize': {'indent': 2,
                                       'separators': (',', ': '),
                                       'sort_keys': True}
                              }
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if not name:
        return _error(ret, 'Must provide name to file.serialize')

    if isinstance(env, six.string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Carbon and this '
            'will be the default and expected behavior. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Carbon', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

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

    if salt.utils.is_windows():
        if group is not None:
            log.warning(
                'The group argument for {0} has been ignored as this '
                'is a Windows system.'.format(name)
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

    if merge_if_exists:
        if os.path.isfile(name):
            if '{0}.deserialize'.format(formatter) not in __serializers__:
                return {'changes': {},
                        'comment': ('{0} format is not supported for merging'
                                    .format(formatter.capitalize())),
                        'name': name,
                        'result': False}

            with salt.utils.fopen(name, 'r') as fhr:
                existing_data = __serializers__[deserializer_name](fhr)

            if existing_data is not None:
                merged_data = existing_data.copy()
                merged_data.update(dataset)
                if existing_data == merged_data:
                    ret['result'] = True
                    ret['comment'] = 'The file {0} is in the correct state'.format(name)
                    return ret
                dataset = merged_data
    contents = __serializers__[serializer_name](dataset, **default_serializer_opts.get(serializer_name, {}))

    contents += '\n'

    if __opts__['test']:
        ret['changes'] = __salt__['file.check_managed_changes'](
            name=name,
            source=None,
            source_hash={},
            source_hash_name=None,
            user=user,
            group=group,
            mode=mode,
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

    .. code-block:: yaml

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

'''
Operations on files, directories and symlinks.
==============================================

Salt States can aggressively manipulate files on a system. There are a number
of ways in which files can be managed.

Regular files can be enforced with the ``managed`` function. This function
downloads files from the salt master and places them on the target system.
The downloaded files can be rendered as a jinja, mako, or wempy template
adding a dynamic component to file management. An example of ``file.managed``
which makes use of the jinja templating system would look like this:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file.managed:
        - source: salt://apache/http.conf
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - context:
            custom_var: "override"
        - defaults:
            custom_var: "default value"
            other_var: 123

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

If you need to enforce user and/or group ownership recursively on the
directory's contents, you can do so by adding a ``recurse`` directive:

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

Symlinks can be easily created, the symlink function is very simple and only
takes a few arguments:

.. code-block:: yaml

    /etc/grub.conf:
      file.symlink:
        - target: /boot/grub/grub.conf

Recursive directory management can also be set via the ``recurse``
function. Recursive directory management allows for a directory on the salt
master to be recursively copied down to the minion. This is a great tool for
deploying large code and configuration systems. A recurse state would look
something like this:

.. code-block:: yaml

    /opt/code/flask:
      file.recurse:
        - source: salt://code/flask
'''
# Import Python libs
import os
import shutil
import difflib
import logging
import copy
import re
import fnmatch

# Import Salt libs
import salt.utils
import salt.utils.templates
from salt._compat import string_types

logger = logging.getLogger(__name__)

COMMENT_REGEX = r'^([[:space:]]*){0}[[:space:]]?'

accumulators = {}


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


def _gen_keep_files(name, require):
    '''
    Generate the list of files that need to be kept when a dir based function
    like directory or recurse has a clean.
    '''
    keep = set()
    keep.add(name)
    if isinstance(require, list):
        for comp in require:
            if 'file' in comp:
                keep.add(comp['file'])
                if os.path.isdir(comp['file']):
                    for root, dirs, files in os.walk(comp['file']):
                        for name in files:
                            keep.add(os.path.join(root, name))
                        for name in dirs:
                            keep.add(os.path.join(root, name))
    return list(keep)


def _check_file(name):
    ret = True
    msg = ''

    if not os.path.isabs(name):
        ret = False
        msg = ('Specified file {0} is not an absolute'
               ' path').format(name)
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
                if fn_ == '/':
                    break

    for roots, dirs, files in os.walk(root):
        for name in files:
            nfn = os.path.join(roots, name)
            if not nfn in real_keep:
                #-- check if this is a part of exclude_pat(only). No need to check include_pat
                if not _check_include_exclude(nfn[len(root)+1:], None, exclude_pat):
                    continue
                removed.add(nfn)
                if not __opts__['test']:
                    os.remove(nfn)
        for name in dirs:
            nfn = os.path.join(roots, name)
            if not nfn in real_keep:
                #-- check if this is a part of exclude_pat(only). No need to check include_pat
                if not _check_include_exclude(nfn[len(root)+1:], None, exclude_pat):
                    continue
                removed.add(nfn)
                if not __opts__['test']:
                    shutil.rmtree(nfn)
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
        local_roots.sort(key=lambda p: len(p), reverse=True)

    srcpath = source[7:] # the path after "salt://"

    # in solo mode(ie, file_client=='local'), fn_ is a path below
    # a file root; in remote mode, fn_ is a path below the cache_dir.
    for root in local_roots:
        n = len(root)
        # if root is the longest prefix path of fn_
        if root == fn_[:n]:
            cachedir = os.path.join(root, srcpath)
            break
    else:
        cachedir = os.path.join(
                        __opts__['cachedir'], 'files', env, srcpath)

    return os.path.join(prefix, os.path.relpath(fn_, cachedir))


def _check_directory(
        name,
        user,
        group,
        recurse,
        mode,
        clean,
        require):
    '''
    Check what changes need to be made on a directory
    '''
    changes = {}
    if recurse:
        if not set(['user', 'group']) >= set(recurse):
            return False, 'Types for "recurse" limited to "user" and "group"'
        if not 'user' in recurse:
            user = None
        if not 'group' in recurse:
            group = None
        for root, dirs, files in os.walk(name):
            for fname in files:
                fchange = {}
                path = os.path.join(root, fname)
                stats = __salt__['file.stats'](path, 'md5')
                if not user is None and user != stats['user']:
                    fchange['user'] = user
                if not group is None and group != stats['group']:
                    fchange['group'] = group
                if fchange:
                    changes[path] = fchange
            for name in dirs:
                path = os.path.join(root, name)
                fchange = _check_dir_meta(path, user, group, None)
                if fchange:
                    changes[path] = fchange
    if not os.path.isdir(name):
        changes[name] = {'directory': 'new'}
    if changes:
        comment = 'The following files will be changed:\n'
        for fn_ in changes:
            for key, val in changes[fn_].items():
                comment += '{0}: {1} - {2}\n'.format(fn_, key, val)
        return None, comment
    return True, 'The directory {0} is in the correct state'.format(name)


def _check_dir_meta(
        name,
        user,
        group,
        mode):
    '''
    Check the changes in directory metadata
    '''
    stats = __salt__['file.stats'](name)
    changes = {}
    if not user is None and user != stats['user']:
        changes['user'] = user
    if not group is None and group != stats['group']:
        changes['group'] = group
    # Normalize the dir mode
    smode = __salt__['config.manage_mode'](stats['mode'])
    mode = __salt__['config.manage_mode'](mode)
    if not mode is None and mode != smode:
        changes['mode'] = mode
    if changes:
        comment = 'The following values are set to be changed:\n'
        for key, val in changes.items():
            comment += '{0}: {1}\n'.format(key, val)
        return None, comment
    return True, 'The directory {0} is in the correct state'.format(name)


def _check_touch(name, atime, mtime):
    '''
    Check to see if a file needs to be updated or created
    '''
    if not os.path.exists(name):
        return None, 'File {0} is set to be created'.format(name)
    stats = __salt__['file.stats'](name)
    if not atime is None:
        if str(atime) != str(stats['atime']):
            return None, 'Times set to be updated on file {0}'.format(name)
    if not mtime is None:
        if str(mtime) != str(stats['mtime']):
            return None, 'Times set to be updated on file {0}'.format(name)
    return True, 'File {0} exists and has the correct times'.format(name)


def _symlink_check(name, target, force):
    '''
    Check the symlink function
    '''
    if not os.path.exists(name):
        comment = 'Symlink {0} to {1} is set for creation'.format(name, target)
        return None, comment
    if os.path.islink(name):
        if not os.readlink(name) == target:
            comment = 'Link {0} target is set to be changed to {1}'.format(
                    name, target)
            return None, comment
        else:
            return True, 'The symlink {0} is present'.format(name)
    else:
        if force:
            return None, ('The file or directory {0} is set for removal to '
                          'make way for a new symlink targeting {1}').format(
                                  name, target)
        return False, ('File or directory exists where the symlink {0} '
                       'should be. Did you mean to use force?'.format(name))


def _check_include_exclude(path_str,include_pat=None,exclude_pat=None):
    '''
     Check for glob or regexp patterns for include_pat and exclude_pat in the
     'path_str' string and return True/False conditions as follows.
      - Default: return 'True' if no include_pat or exclude_pat patterns are supplied
      - If only include_pat or exclude_pat is supplied. Return 'True' if string passes
        the include_pat test or failed exclude_pat test respectively
      - If both include_pat and exclude_pat are supplied, return Ture if include_pat
        matches 'AND' exclude_pat does not matches
    '''
    ret = True    #-- default true
    # Before pattern match, check if it is regexp (E@'') or glob(default)
    if include_pat:
        if re.match('E@',include_pat):
            retchk_include = True if re.search(include_pat[2:], path_str) else False
        else:
            retchk_include = True if fnmatch.fnmatch(path_str,include_pat) else False

    if exclude_pat:
        if re.match('E@',exclude_pat):
            retchk_exclude = False if re.search(exclude_pat[2:], path_str) else True
        else:
            retchk_exclude = False if fnmatch.fnmatch(path_str,exclude_pat) else True

    # Now apply include/exclude conditions
    if include_pat and not exclude_pat:
        ret = retchk_include
    elif exclude_pat and not include_pat:
        ret = retchk_exclude
    elif include_pat and exclude_pat:
        ret = retchk_include and retchk_exclude
    else:
        ret = True

    return ret


def symlink(
        name,
        target,
        force=False,
        makedirs=False,
        user=None,
        group=None,
        mode=None):
    '''
    Create a symlink

    name
        The location of the symlink to create

    target
        The location that the symlink points to

    force
        If the location of the symlink exists and is not a symlink then the
        state will fail, set force to True and any file or directory in the way
        of the symlink file will be deleted to make room for the symlink

    makedirs
        If the location of the symlink does not already have a parent directory
        then the state will fail, setting makedirs to True will allow Salt to
        create the parent directory
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if __opts__['test']:
        ret['result'], ret['comment'] = _symlink_check(name, target, force)
        return ret

    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            __salt__['file.makedirs'](
                    name,
                    user=user,
                    group=group,
                    mode=mode)
        else:
            return _error(ret,
                          ('Directory {0} for symlink is not present'
                           ) .format(os.path.dirname(name)))
    if os.path.islink(name):
        # The link exists, verify that it matches the target
        if not os.readlink(name) == target:
            # The target is wrong, delete the link
            os.remove(name)
        else:
            # The link looks good!
            ret['comment'] = 'The symlink {0} is present'.format(name)
            return ret
    elif os.path.isfile(name):
        # Since it is not a link, and is a file, error out
        if force:
            os.remove(name)
        else:
            return _error(ret, ('File exists where the symlink {0} should be'
                              .format(name)))
    elif os.path.isdir(name):
        # It is not a link or a file, it is a dir, error out
        if force:
            shutil.rmtree(name)
        else:
            return _error(ret, 'Directory exists where the symlink {0} '
                              'should be'.format(name))
    if not os.path.exists(name):
        # The link is not present, make it
        os.symlink(target, name)
        ret['comment'] = 'Created new symlink {0}'.format(name)
        ret['changes']['new'] = name
        return ret


def absent(name):
    '''
    Verify that the named file or directory is absent, this will work to
    reverse any of the functions in the file state module.

    name
        The path which should be deleted
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not os.path.isabs(name):
        return _error(ret, ('Specified file {0} is not an absolute'
                          ' path').format(name))
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
        except (OSError, IOError):
            return _error(ret, 'Failed to remove file {0}'.format(name))

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
    Ensures pre-requisites outside of salts per-vue have been previously
    satisified (aka, keytabs, private keys, etc.) before deployment

    name
        Absolute path which must exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not os.path.exists(name):
      return _error(ret, ('Specified path {0} does not exist').format(name))

    ret['comment'] = 'Path {0} exists'.format(name)
    return ret


def managed(name,
        source=None,
        source_hash='',
        user=None,
        group=None,
        mode=None,
        template=None,
        makedirs=False,
        context=None,
        replace=True,
        defaults=None,
        env=None,
        backup='',
        **kwargs):
    '''
    Manage a given file, this function allows for a file to be downloaded from
    the salt master and potentially run through a templating system.

    name
        The location of the file to manage

    source
        The source file to download to the minion, this source file can be
        hosted on either the salt master server, or on an http or ftp server.
        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs. If source is left blank or None, the file
        will be created as an empty file and the content will not be managed

        If the file is hosted on a http or ftp server then the source_hash
        argument is also required

    source_hash:
        This can be either a file which contains a source hash string for
        the source, or a source hash string. The source hash string is the
        hash algorithm followed by the hash of the file:
        md5=e138491e9d5b97023cea823fe17bac22

        The file can contain checksums for several files, in this case every
        line must consist of full name of the file and checksum separated by
        space:

        /etc/rc.conf md5=ef6e82e4006dee563d98ada2a2a80a27
        /etc/resolv.conf sha256=c8525aee419eb649f0233be91c151178b30f0dff8ebbdcc8de71b1d5c8bcc06a

    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

    group
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion

    mode
        The permissions to set on this file, aka 644, 0775, 4664

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file, currently jinja, mako, and wempy
        are supported

    makedirs
        If the file is located in a path without a parent directory, then
        the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.

    replace
        If this file should be replaced.  If false, this command will
        not overwrite file contents but will enforce permissions if the file
        exists already.  Default is true.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    backup
        Overrides the default backup mode for this specific file
    '''
    # Initial set up
    mode = __salt__['config.manage_mode'](mode)
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, ('Specified file {0} is not an absolute'
                  ' path').format(name))
    if env is None:
        env = kwargs.get('__env__', 'base')

    if os.path.isdir(name):
        ret['comment'] = 'Specified target {0} is a directory'.format(name)
        ret['result'] = False
        return ret

    if not replace:
        if os.path.exists(name):
           # Check and set the permissions if necessary
            ret, perms = __salt__['file.check_perms'](name,
                                                      ret,
                                                      user,
                                                      group,
                                                      mode)
            if __opts__['test']:
                ret['comment'] = 'File {0} not updated'.format(name)
            elif not ret['changes'] and ret['result']:
                ret['comment'] = ('File {0} exists with proper permissions. '
                                  'No changes made.').format(name)
            return ret
        if not source:
            return touch(name, makedirs=makedirs)

    if name in accumulators:
        if not context:
            context = {}
        context['accumulator'] = accumulators[name]

    if __opts__['test']:
        ret['result'], ret['comment'] = __salt__['file.check_managed'](
                name,
                source,
                source_hash,
                user,
                group,
                mode,
                template,
                makedirs,
                context,
                defaults,
                env,
                **kwargs
                )
        return ret

    # If the source is a list then find which file exists
    source, source_hash = __salt__['file.source_list'](
                                                      source,
                                                      source_hash,
                                                      env
                                                      )

    # Gather the source file from the server
    sfn, source_sum, comment = __salt__['file.get_managed'](
            name,
            template,
            source,
            source_hash,
            user,
            group,
            mode,
            env,
            context,
            defaults,
            **kwargs
            )
    if comment:
        return _error(ret, comment)
    else:
        return __salt__['file.manage_file'](name,
                                            sfn,
                                            ret,
                                            source,
                                            source_sum,
                                            user,
                                            group,
                                            mode,
                                            env,
                                            backup)


def directory(name,
        user=None,
        group=None,
        recurse=[],
        mode=None,
        makedirs=False,
        clean=False,
        require=None,
        exclude_pat=None):
    '''
    Ensure that a named directory is present and has the right perms

    name
        The location to create or manage a directory

    user
        The user to own the directory, this defaults to the user salt is
        running as on the minion

    group
        The group ownership set for the directory, this defaults to the group
        salt is running as on the minion

    recurse
        Enforce user/group ownership of directory recursively

    mode
        The permissions to set on this directory, aka 755

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
    '''
    mode = __salt__['config.manage_mode'](mode)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))
    if os.path.isfile(name):
        return _error(
            ret, 'Specified location {0} exists and is a file'.format(name))
    if __opts__['test']:
        ret['result'], ret['comment'] = _check_directory(
                name,
                user,
                group,
                recurse,
                mode,
                clean,
                require)
        return ret

    if not os.path.isdir(name):
        # The dir does not exist, make it
        if not os.path.isdir(os.path.dirname(name)):
            if makedirs:
                __salt__['file.makedirs'](name, user=user,
                                          group=group, mode=mode)
            else:
                return _error(
                    ret, 'No directory to create {0} in'.format(name))
    if not os.path.isdir(name):
        __salt__['file.makedirs'](name, user=user, group=group, mode=mode)
        os.makedirs(name)
    if not os.path.isdir(name):
        return _error(ret, 'Failed to create directory {0}'.format(name))

    # Check permissions
    ret, perms = __salt__['file.check_perms'](name, ret, user, group, mode)

    if recurse:
        if not set(['user', 'group']) >= set(recurse):
            ret['result'] = False
            ret['comment'] = 'Types for "recurse" limited to "user" and ' \
                             '"group"'
        else:
            targets = copy.copy(recurse)
            if 'user' in targets:
                if user:
                    uid = __salt__['file.user_to_uid'](user)
                    # file.user_to_uid returns '' if user does not exist. Above
                    # check for user is not fatal, so we need to be sure user
                    # exists.
                    if type(uid).__name__ == 'str':
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce ownership for ' \
                                         'user {0} (user does not ' \
                                         'exist)'.format(user)
                        # Remove 'user' from list of recurse targets
                        targets = list(x for x in targets if x != 'user')
                else:
                    ret['result'] = False
                    ret['comment'] = 'user not specified, but configured as ' \
                             'a target for recursive ownership management'
                    # Remove 'user' from list of recurse targets
                    targets = list(x for x in targets if x != 'user')
            if 'group' in targets:
                if group:
                    gid = __salt__['file.group_to_gid'](group)
                    # As above with user, we need to make sure group exists.
                    if type(gid).__name__ == 'str':
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce group ownership ' \
                                         'for group {0}'.format(group, user)
                        # Remove 'group' from list of recurse targets
                        targets = list(x for x in targets if x != 'group')
                else:
                    ret['result'] = False
                    ret['comment'] = 'group not specified, but configured ' \
                             'as a target for recursive ownership management'
                    # Remove 'group' from list of recurse targets
                    targets = list(x for x in targets if x != 'group')

            needs_fixed = {}
            if targets:
                file_tree = __salt__['file.find'](name)
                for path in file_tree:
                    fstat = os.stat(path)
                    if 'user' in targets and fstat.st_uid != uid:
                            needs_fixed['user'] = True
                            if needs_fixed.get('group'):
                                break
                    if 'group' in targets and fstat.st_gid != gid:
                            needs_fixed['group'] = True
                            if needs_fixed.get('user'):
                                break

            if needs_fixed.get('user'):
                # Make sure the 'recurse' subdict exists
                ret['changes'].setdefault('recurse', {})
                if 'user' in targets:
                    if __salt__['cmd.retcode']('chown -R {0} "{1}"'.format(
                            user, name)) != 0:
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce ownership on ' \
                                         '{0} for user {1}'.format(name, group)
                    else:
                        ret['changes']['recurse']['user'] = \
                                __salt__['file.uid_to_user'](uid)
            if needs_fixed.get('group'):
                ret['changes'].setdefault('recurse', {})
                if 'group' in targets:
                    if __salt__['cmd.retcode']('chown -R :{0} "{1}"'.format(
                            group, name)) != 0:
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce group ownership ' \
                                         'on {0} for group ' \
                                         '{1}'.format(name, group)
                    else:
                        ret['changes']['recurse']['group'] = \
                                __salt__['file.gid_to_group'](gid)

    if clean:
        keep = _gen_keep_files(name, require)
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
        template=None,
        context=None,
        defaults=None,
        env=None,
        include_empty=False,
        backup='',
        include_pat=None,
        exclude_pat=None,
        **kwargs):
    '''
    Recurse through a subdirectory on the master and copy said subdirecory
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
        The user to own the directory, this defaults to the user salt is
        running as on the minion

    group
        The group ownership set for the directory, this defaults to the group
        salt is running as on the minion

    dir_mode
        The permissions mode to set any directories created

    file_mode
        The permissions mode to set any files created

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file, currently jinja, mako, and wempy
        are supported

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    include_empty
        Set this to True if empty directories should also be created
        (default is False)

    include_pat
	When copying, include only this pattern from the source. Default
        is glob match , if prefixed with E@ then regexp match
        Example::

          - include_pat: hello*       :: glob matches 'hello01', 'hello02' ... but not 'otherhello'
          - include_pat: E@hello      :: regexp matches 'otherhello', 'hello01' ...

    exclude_pat
	When copying, exclude this pattern from the source. If both
        include_pat and exclude_pat are supplied, then it will apply
        conditions cumulatively. i.e. first select based on include_pat and
        then with in that result, applies exclude_pat.

        Also when 'clean=True', exclude this pattern from the removal
        list and preserve in the destination.
        Example::

          - exclude: APPDATA*               :: glob matches APPDATA.01, APPDATA.02,.. for exclusion
          - exclude: E@(APPDATA)|(TEMPDATA) :: regexp matches APPDATA or TEMPDATA for exclusion
    '''
    ret = {'name': name,
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

    u_check = _check_user(user, group)
    if u_check:
        # The specified user or group do not exist
        return _error(ret, u_check)
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))
    if env is None:
        env = kwargs.get('__env__', 'base')

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
        if isinstance(comment, basestring):
            comments.append(comment)
        else:
            comments.extend(comment)

    def merge_ret(path, _ret):
        # Use the most "negative" result code (out of True, None, False)
        if _ret['result'] == False or ret['result'] == True:
            ret['result'] = _ret['result']

        # Only include comments about files that changed
        if _ret['result'] != True and _ret['comment']:
            add_comment(path, _ret['comment'])

        if _ret['changes']:
            ret['changes'][path] = _ret['changes']

    def manage_file(path, source):
        if clean and os.path.exists(path) and os.path.isdir(path):
            _ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
            if __opts__['test']:
                _ret['comment'] = 'Replacing directory {0} with a file'.format(path)
                _ret['result'] = None
                merge_ret(path, _ret)
                return
            else:
                shutil.rmtree(path)
                _ret['changes'] = { 'diff': 'Replaced directory with a new file' }
                merge_ret(path, _ret)

        # Conflicts can occur is some kwargs are passed in here
        pass_kwargs = {}
        faults = ['mode', 'makedirs', 'replace']
        for key in kwargs:
            if not key in faults:
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
            replace=True,
            defaults=defaults,
            env=env,
            backup=backup,
            **pass_kwargs)
        merge_ret(path, _ret)

    def manage_directory(path):
        if clean and os.path.exists(path) and not os.path.isdir(path):
            _ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
            if __opts__['test']:
                _ret['comment'] = 'Replacing {0} with a directory'.format(path)
                _ret['result'] = None
                merge_ret(path, _ret)
                return
            else:
                os.remove(path)
                _ret['changes'] = { 'diff': 'Replaced file with a directory' }
                merge_ret(path, _ret)

        _ret = directory(
            path,
            user=user,
            group=group,
            recurse=[],
            mode=dir_mode,
            makedirs=True,
            clean=False,
            require=None)
        merge_ret(path, _ret)

    # If source is a list, find which in the list actually exists
    source, source_hash = __salt__['file.source_list'](source, '', env)

    keep = set()
    vdir = set()
    for fn_ in __salt__['cp.cache_dir'](source, env, include_empty):
        if not fn_.strip():
            continue
        # fn_ here is the absolute source path of the file to copy from;
        # it is either a normal file or an empty dir(if include_empty==true).

        dest = _get_recurse_dest(name, fn_, source, env)
        #- Check if it is to be excluded. Match only trailing part of the path after base directory
        if not _check_include_exclude(dest[len(name)+1:], include_pat, exclude_pat):
            continue
        dirname = os.path.dirname(dest)
        keep.add(dest)

        if not dirname in vdir:
            # verify the directory perms if they are set
            manage_directory(dirname)
            vdir.add(dirname)

        if os.path.isdir(fn_) and include_empty:
            #create empty dir
            manage_directory(dest)
        else:
            src = source + _get_recurse_dest('/', fn_, source, env)
            manage_file(dest, src)

    keep = list(keep)
    if clean:
        # TODO: Use directory(clean=True) instead
        keep += _gen_keep_files(name, require)
        removed = _clean_dir(name, list(keep), exclude_pat)
        if removed:
            if __opts__['test']:
                if ret['result']: ret['result'] = None
                add_comment('removed', removed)
            else:
              ret['changes']['removed'] = removed

    # Flatten comments until salt command line client learns
    # to display structured comments in a readable fashion
    ret['comment'] = '\n'.join("\n#### %s ####\n%s" % (k,
            v if isinstance(v, basestring) else '\n'.join(v))
        for (k, v) in ret['comment'].iteritems()).strip()

    if not ret['comment']:
        ret['comment'] = 'Recursively updated {0}'.format(name)

    if not ret['changes'] and ret['result']:
        ret['comment'] = 'The directory {0} is in the correct state'.format(name)

    return ret


def sed(name, before, after, limit='', backup='.bak', options='-r -e',
        flags='g'):
    '''
    Maintain a simple edit to a file

    The file will be searched for the ``before`` pattern before making the edit
    and then searched for the ``after`` pattern to verify the edit was
    successful using :mod:`salt.modules.file.contains`. In general the
    ``limit`` pattern should be as specific as possible and ``before`` and
    ``after`` should contain the minimal text to be changed.

    Usage::

        # Disable the epel repo by default
        /etc/yum.repos.d/epel.repo:
          file.sed:
            - before: 1
            - after: 0
            - limit: ^enabled=

        # Remove ldap from nsswitch
        /etc/nsswitch.conf:
          file.sed:
            - before: 'ldap'
            - after: ''
            - limit: '^passwd:'

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    # sed returns no output if the edit matches anything or not so we'll have
    # to look for ourselves

    # Mandate that before and after are strings
    before = str(before)
    after = str(after)

    # Look for the pattern before attempting the edit
    if not __salt__['file.contains_regex'](name, before):
        # Pattern not found; try to guess why
        if __salt__['file.contains_regex'](name, after):
            ret['comment'] = 'Edit already performed'
            ret['result'] = True
            return ret
        else:
            ret['comment'] = 'Pattern not matched'
            return ret

    if __opts__['test']:
        ret['comment'] = 'File {0} is set to be updated'.format(name)
        ret['result'] = None
        return ret
    with salt.utils.fopen(name, 'rb') as fp_:
        slines = fp_.readlines()
    # should be ok now; perform the edit
    __salt__['file.sed'](name, before, after, limit, backup, options, flags)
    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    # check the result
    ret['result'] = __salt__['file.contains_regex'](name, after)
    if slines != nlines:
        # Changes happened, add them
        ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
                )

    if ret['result']:
        ret['comment'] = 'File successfully edited'
    else:
        ret['comment'] = 'Expected edit does not appear in file'

    return ret


def comment(name, regex, char='#', backup='.bak'):
    '''
    Comment out specified lines in a file.

    path
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be commented;
        this pattern will be wrapped in parenthesis and will move any
        preceding/trailing ``^`` or ``$`` characters outside the parenthesis
        (e.g., the pattern ``^foo$`` will be rewritten as ``^(foo)$``)
    char : ``#``
        The character to be inserted at the beginning of a line in order to
        comment it out
    backup : ``.bak``
        The file will be backed up before edit with this file extension

        .. warning::

            This backup will be overwritten each time ``sed`` / ``comment`` /
            ``uncomment`` is called. Meaning the backup will only be useful
            after the first invocation.

    Usage::

        /etc/fstab:
          file.comment:
            - regex: ^bind 127.0.0.1

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    unanchor_regex = regex.lstrip('^').rstrip('$')

    # Make sure the pattern appears in the file before continuing
    if not __salt__['file.contains_regex'](name, regex):
        if __salt__['file.contains_regex'](name, unanchor_regex):
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
    __salt__['file.comment'](name, regex, char, backup)

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    # Check the result
    ret['result'] = __salt__['file.contains_regex'](name, unanchor_regex)

    if slines != nlines:
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

    path
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be uncommented.
        This regex should not include the comment character. A leading ``^``
        character will be stripped for convenience (for easily switching
        between comment() and uncomment()).
    char : ``#``
        The character to remove in order to uncomment a line; if a single
        whitespace character follows the comment it will also be removed
    backup : ``.bak``
        The file will be backed up before edit with this file extension;
        **WARNING:** each time ``sed``/``comment``/``uncomment`` is called will
        overwrite this backup

    Usage::

        /etc/adduser.conf:
          file.uncomment:
            - regex: EXTRA_GROUPS

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    # Make sure the pattern appears in the file
    if __salt__['file.contains_regex'](name, regex):
        ret['comment'] = 'Pattern already uncommented'
        ret['result'] = True
        return ret
    elif __salt__['file.contains_regex'](name, regex, lchar=char):
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
    __salt__['file.uncomment'](name, regex, char, backup)

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    # Check the result
    ret['result'] = __salt__['file.contains_regex'](name, regex)

    if slines != nlines:
        # Changes happened, add them
        ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
                )

    if ret['result']:
        ret['comment'] = 'Uncommented lines successfully'
    else:
        ret['comment'] = 'Expected uncommented lines not found'

    return ret


def append(name, text=None, makedirs=False, source=None, source_hash=None):
    '''
    Ensure that some text appears at the end of a file

    The text will not be appended again if it already exists in the file. You
    may specify a single line of text or a list of lines to append.

    Multi-line example::

        /etc/motd:
          file.append:
            - text: |
                Thou hadst better eat salt with the Philosophers of Greece,
                than sugar with the Courtiers of Italy.
                - Benjamin Franklin

    Multiple lines of text::

        /etc/motd:
          file.append:
            - text:
              - Trust no one unless you have eaten much salt with him.
              - Salt is born of the purest of parents: the sun and the sea.

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if makedirs:
        dirname = os.path.dirname(name)
        if not __salt__['file.directory_exists'](dirname):
            __salt__['file.makedirs'](name)
            check_res, check_msg = _check_directory(
                dirname, None, None, False, None, False, False
            )
            if not check_res:
                return _error(ret, check_msg)

        # Make sure that we have a file
        __salt__['file.touch'](name)

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    if source:
        # get cached file or copy it to cache
        cached_source_path = __salt__['cp.cache_file'](source)
        logger.debug(
            "state file.append cached source {0} -> {1}".format(
                source, cached_source_path
            )
        )
        cached_source = managed(
            cached_source_path, source=source, source_hash=source_hash
        )
        if cached_source['result'] is True:
            logger.debug(
                "state file.append is loading text contents from cached source "
                "{0}({1})".format(source, cached_source_path)
            )
            text = salt.utils.fopen(cached_source_path, 'r').read()

    if isinstance(text, string_types):
        text = (text,)

    with salt.utils.fopen(name, 'rb') as fp_:
        slines = fp_.readlines()

    count = 0

    for chunk in text:

        if __salt__['file.contains_regex'](
                        name, salt.utils.build_whitepace_splited_regex(chunk)):
            continue

        try:
            lines = chunk.splitlines()
        except AttributeError:
            logger.debug(
                'Error appending text to {0}; given object is: {1}'.format(
                    name, type(chunk)
                )
            )
            return _error(ret, 'Given text is not a string')

        for line in lines:
            if __opts__['test']:
                ret['comment'] = 'File {0} is set to be updated'.format(name)
                ret['result'] = None
                return ret
            __salt__['file.append'](name, line)
            count += 1

    with salt.utils.fopen(name, 'rb') as fp_:
        nlines = fp_.readlines()

    if slines != nlines:
        # Changes happened, add them
        ret['changes']['diff'] = (
                ''.join(difflib.unified_diff(slines, nlines))
                )

    ret['comment'] = 'Appended {0} lines'.format(count)
    ret['result'] = True
    return ret


def patch(name, source=None, hash=None, options='',
        dry_run_first=True, env='base'):
    '''
    Apply a patch to a file. Note: a suitable ``patch`` executable must be
    available on the minion when using this state function.

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

    Usage::

        # Equivalent to ``patch --forward /opt/file.txt file.patch``
        /opt/file.txt:
          file.patch:
            - source: salt://file.patch
            - hash: md5=e138491e9d5b97023cea823fe17bac22
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
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

    # get cached file or copy it to cache
    cached_source_path = __salt__['cp.cache_file'](source, env)
    logger.debug(
        "State patch.applied cached source {0} -> {1}".format(
            source, cached_source_path
        )
    )

    if dry_run_first or __opts__['test']:
        ret['changes'] = __salt__['file.patch'](
            name, cached_source_path, options=options, dry_run=True
        )
        if __opts__['test']:
            ret['comment'] = 'File {} will be patched'.format(name)
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
            comment='File {0} hash mismatch after patch was applied'.format(name)
        )
    return ret


def touch(name, atime=None, mtime=None, makedirs=False):
    '''
    Replicate the 'nix "touch" command to create a new empty
    file or update the atime and mtime of an existing  file.

    Usage::

        /var/log/httpd/logrotate.empty:
          file.touch

    .. versionadded:: 0.9.5
    '''
    ret = {
        'name': name,
        'changes': {},
    }
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
    exists = os.path.exists(name)
    ret['result'] = __salt__['file.touch'](name, atime, mtime)

    if not exists and ret['result']:
        ret['comment'] = 'Created empty file {0}'.format(name)
        ret['changes']['new'] = name
    elif exists and ret['result']:
        ret['comment'] = 'Updated times on {0} {1}'.format(
            'directory' if os.path.isdir(name) else 'file', name
        )

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

    force:
        If the target location is present then the file will not be moved,
        specify "force: True" to overwrite the target file

    makedirs:
        If the target subdirectories don't exist create them

    '''
    ret = {
        'name': name,
        'changes': {},
        'comment': '',
        'result': True}

    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if not os.path.isfile(source):
        ret['comment'] = ('Source file "{0}" has already been moved out of '
                          'place').format(source)
        return ret

    if os.path.isfile(source) and os.path.isfile(name) and not force:
        ret['comment'] = ('The target file "{0}" exists and will not be '
                          'overwritten').format(name)
        ret['result'] = False
        return ret

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
            os.makedirs(dname)
        else:
            return _error(
                    ret,
                    'The target directory {0} is not present'.format(dname))
    # All tests pass, move the file into place
    try:
        shutil.move(source, name)
    except (IOError, OSError):
        return _error(
            ret, 'Failed to move "{0}" to "{1}"'.format(source, name))
        return ret

    ret['comment'] = 'Moved "{0}" to "{1}"'.format(source, name)
    ret['changes'] = {name: source}
    return ret


def accumulated(name, filename, text, **kwargs):
    '''
    Prepare accumulator which can be used in template in file.managed state.
    accumulator dictionary becomes available in template.

    name
        Accumulator name

    filename
        Filename which would receive this accumulator (see file.managed state
        documentation about ''name``)

    text
        String or list for adding in accumulator

    require_in / watch_in
        One of them required for sure we fill up accumulator before we manage
        the file. Probably the same as filename
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }
    if not filter(lambda x: 'file' in x,
                  kwargs.get('require_in', ()) + kwargs.get('watch_in', ())):
        ret['result'] = False
        ret['comment'] = ('Orphaned accumulator {0} in '
                          '{1}:{2}'.format(name, kwargs['__sls__'],
                          kwargs['__id__']))
        return ret
    if isinstance(text, string_types):
        text = (text,)
    if filename not in accumulators:
        accumulators[filename] = {}
    if name not in accumulators[filename]:
        accumulators[filename][name] = []
    for chunk in text:
        if chunk not in accumulators[filename][name]:
            accumulators[filename][name].append(chunk)
            ret['comment'] = ('Accumulator {0} for file {1} '
                              'was charged by text').format(name, filename)
    return ret

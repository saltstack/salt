'''
File Management
===============

Salt States can aggressively manipulate files on a system. There are a number of
ways in which files can be managed.

Regular files can be enforced with the ``managed`` function. This function
downloads files from the salt master and places them on the target system.
The downloaded files can be rendered as a jinja or mako template adding
a dynamic component to file management. An example of ``file.managed`` which
makes use of the jinja templating system would look like this:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file:
        - managed
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
      file:
        - directory
        - user: fred
        - group: users
        - mode: 755
        - makedirs: True

If you need to enforce user and/or group ownership recursively on the
directory's contents, you can do so by adding a ``recurse`` directive:

.. code-block:: yaml

    /srv/stuff/substuf:
      file:
        - directory
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
      file:
        - symlink
        - target: /boot/grub/grub.conf

Recursive directory management can also be set via the ``recurse``
function. Recursive directory management allows for a directory on the salt
master to be recursively copied down to the minion. This is a great tool for
deploying large code and configuration systems. A recuse state would look
something like this:

.. code-block:: yaml

    /opt/code/flask:
      file:
        - recurse
        - source: salt://code/flask
'''

import codecs
from contextlib import nested  # For < 2.7 compat
import os
import shutil
import difflib
import hashlib
import imp
import logging
import tempfile
import traceback
import urlparse
import copy

logger = logging.getLogger(__name__)

COMMENT_REGEX = r'^([[:space:]]*){0}[[:space:]]?'


def __manage_mode(mode):
    '''
    Convert the mode into something usable
    '''
    if mode:
        mode = str(mode).lstrip('0')
        if not mode:
            return '0'
        else:
            return mode
    return mode


def __clean_tmp(sfn):
    '''
    Clean out a template temp file
    '''
    if not sfn.startswith(__opts__['cachedir']):
        # Only clean up files that exist
        if os.path.exists(sfn):
            os.remove(sfn)


def _makedirs(path):
    '''
    Ensure that the directory containing this path is available.
    '''
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))


def _is_bin(path):
    '''
    Return True if a file is a bin, just checks for NULL char, this should be
    expanded to reflect how git checks for bins
    '''
    with open(path, 'rb') as f:
        return '\0' in f.read(2048)


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


def _clean_dir(root, keep):
    '''
    Clean out all of the files and directories in a directory (root) while
    preserving the files in a list (keep)
    '''
    removed = set()
    real_keep = set()
    real_keep.add(root)
    if isinstance(keep, list):
        for fn_ in keep:
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
                removed.add(nfn)
                os.remove(nfn)
        for name in dirs:
            nfn = os.path.join(roots, name)
            if not nfn in real_keep:
                removed.add(nfn)
                shutil.rmtree(nfn)
    return list(removed)


def _error(ret, err_msg):
    ret['result'] = False,
    ret['comment'] = err_msg
    return ret


def _mako(sfn, name, source, user, group, mode, env, context=None):
    '''
    Render a mako template, returns the location of the rendered file,
    return False if render fails.
    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from mako.template import Template
    except ImportError:
        return {'result': False,
                'data': 'Failed to import jinja'}
    try:
        tgt = tempfile.mkstemp()[1]
        passthrough = context if context else {}
        passthrough.update(__salt__)
        passthrough.update(__grains__)
        with nested(open(sfn, 'r'), open(tgt, 'w+')) as (src, target):
            template = Template(src.read())
            target.write(template.render(**passthrough))
        return {'result': True,
                'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


def _jinja(sfn, name, source, user, group, mode, env, context=None):
    '''
    Render a jinja2 template, returns the location of the rendered file,
    return False if render fails.
    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from salt.utils.jinja import get_template
    except ImportError:
        return {'result': False,
                'data': 'Failed to import jinja'}
    try:
        newline = False
        with open(sfn, 'rb') as source:
            if source.read().endswith('\n'):
                newline = True
        tgt = tempfile.mkstemp()[1]
        passthrough = context if context else {}
        passthrough['salt'] = __salt__
        passthrough['grains'] = __grains__
        passthrough['name'] = name
        passthrough['source'] = source
        passthrough['user'] = user
        passthrough['group'] = group
        passthrough['mode'] = mode
        passthrough['env'] = env
        template = get_template(sfn, __opts__, env)
        try:
            with open(tgt, 'w+') as target:
                target.write(template.render(**passthrough))
                if newline:
                    target.write('\n')
        except UnicodeEncodeError:
            with codecs.open(tgt, encoding='utf-8', mode='w+') as target:
                target.write(template.render(**passthrough))
                if newline:
                    target.write('\n')
        return {'result': True,
                    'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


def _py(sfn, name, source, user, group, mode, env, context=None):
    '''
    Render a template from a python source file

    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    if not os.path.isfile(sfn):
        return {}

    mod = imp.load_source(
            os.path.basename(sfn).split('.')[0],
            sfn
            )
    mod.salt = __salt__
    mod.grains = __grains__
    mod.name = name
    mod.source = source
    mod.user = user
    mod.group = group
    mod.mode = mode
    mod.env = env
    mod.context = context

    try:
        tgt = tempfile.mkstemp()[1]
        with open(tgt, 'w+') as target:
            target.write(mod.run())
        return {'result': True,
                'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


template_registry = {
    'jinja': _jinja,
    'mako': _mako,
    'py': _py,
}


def _check_perms(name, ret, user, group, mode):
    # Check permissions
    perms = {}
    perms['luser'] = __salt__['file.get_user'](name)
    perms['lgroup'] = __salt__['file.get_group'](name)
    perms['lmode'] = __salt__['file.get_mode'](name)

    # Mode changes if needed
    if mode:
        if mode != perms['lmode']:
            if not __opts__['test']:
                __salt__['file.set_mode'](name, mode)
            if mode != __salt__['file.get_mode'](name):
                ret['result'] = False
                ret['comment'] += 'Failed to change mode to {0} '.format(mode)
            else:
                ret['changes']['mode'] = mode
    # user/group changes if needed, then check if it worked
    if user:
        if user != perms['luser']:
            perms['cuser'] = user
    if group:
        if group != perms['lgroup']:
            perms['cgroup'] = group
    if 'cuser' in perms or 'cgroup' in perms:
        if not __opts__['test']:
            __salt__['file.chown'](
                    name,
                    user,
                    group
                    )
    if user:
        if user != __salt__['file.get_user'](name):
            ret['result'] = False
            ret['comment'] = 'Failed to change user to {0} '.format(user)
        elif 'cuser' in perms:
            ret['changes']['user'] = user
    if group:
        if group != __salt__['file.get_group'](name):
            ret['result'] = False
            ret['comment'] += ('Failed to change group to {0} '
                               .format(group))
        elif 'cgroup' in perms:
            ret['changes']['group'] = group

    return ret, perms


def symlink(name, target, force=False, makedirs=False):
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

    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            _makedirs(name)
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
        try:
            os.remove(name)
            ret['comment'] = 'Removed file {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except:
            return _error(ret, 'Failed to remove file {0}'.format(name))

    elif os.path.isdir(name):
        try:
            shutil.rmtree(name)
            ret['comment'] = 'Removed directory {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except:
            return _error(ret, 'Failed to remove directory {0}'.format(name))

    ret['comment'] = 'File {0} is not present'.format(name)
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
        defaults=None,
        __env__='base'):
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
        used to render the downloaded file, currently jinja and mako are
        supported

    makedirs
        If the file is located in a path without a parent directory, then
        the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.
    '''
    mode = __manage_mode(mode)
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if not os.path.isabs(name):
        return _error(
            ret, ('Specified file {0} is not an absolute'
                  ' path').format(name))
    # Gather the source file from the server
    sfn = ''
    source_sum = {}

    # If the source is a list then find which file exists
    if isinstance(source, list):
        # get the master file list
        mfiles = __salt__['cp.list_master'](__env__)
        for single in source:
            if isinstance(single, dict):
                # check the proto, if it is http or ftp then download the file
                # to check, if it is salt then check the master list
                if len(single) != 1:
                    continue
                single_src = single.keys()[0]
                single_hash = single[single_src]
                proto = urlparse.urlparse(single_src).scheme
                if proto == 'salt':
                    if single_src in mfiles:
                        source = single_src
                        break
                elif proto.startswith('http') or proto == 'ftp':
                    dest = tempfile.mkstemp()[1]
                    fn_ = __salt__['cp.get_url'](single_src, dest)
                    os.remove(fn_)
                    if fn_:
                        source = single_src
                        source_hash = single_hash
                        break
            elif isinstance(single, basestring):
                if single in mfiles:
                    source = single
                    break

    # If the file is a template and the contents is managed
    # then make sure to cpy it down and templatize  things.
    if template and source:
        sfn = __salt__['cp.cache_file'](source, __env__)
        if not os.path.exists(sfn):
            return _error(
                ret, ('File "{sfn}" could not be found').format(sfn=sfn))
        if template in template_registry:
            context_dict = defaults if defaults else {}
            if context:
                context_dict.update(context)
            data = template_registry[template](
                    sfn,
                    name,
                    source,
                    user,
                    group,
                    mode,
                    __env__,
                    context_dict
                    )
        else:
            return _error(
                ret, ('Specified template format {0} is not supported'
                      ).format(template))

        if data['result']:
            sfn = data['data']
            hsum = ''
            with open(sfn, 'r') as source:
                hsum = hashlib.md5(source.read()).hexdigest()
            source_sum = {'hash_type': 'md5',
                          'hsum': hsum}
        else:
            __clean_tmp(sfn)
            return _error(ret, data['data'])
    else:
        # Copy the file down if there is a source
        if source:
            if urlparse.urlparse(source).scheme == 'salt':
                source_sum = __salt__['cp.hash_file'](source, __env__)
                if not source_sum:
                    return _error(
                        ret, 'Source file {0} not found'.format(source))
            elif source_hash:
                protos = ['salt', 'http', 'ftp']
                if urlparse.urlparse(source_hash).scheme in protos:
                    # The sourc_hash is a file on a server
                    hash_fn = __salt__['cp.cache_file'](source_hash)
                    if not hash_fn:
                        return _error(
                            ret, 'Source hash file {0} not found'.format(
                             source_hash
                             ))
                    comps = []
                    with open(hash_fn, 'r') as hashfile:
                        comps = hashfile.read().split('=')
                    if len(comps) < 2:
                        return _error(
                            ret, ('Source hash file {0} contains an '
                                  ' invalid hash format, it must be in '
                                  ' the format <hash type>=<hash>'
                                  ).format(source_hash))
                    source_sum['hsum'] = comps[1].strip()
                    source_sum['hash_type'] = comps[0].strip()
                else:
                    # The source_hash is a hash string
                    comps = source_hash.split('=')
                    if len(comps) < 2:
                        return _error(
                            ret, ('Source hash file {0} contains an '
                                  ' invalid hash format, it must be in '
                                  ' the format <hash type>=<hash>'
                                  ).format(source_hash))
                    source_sum['hsum'] = comps[1].strip()
                    source_sum['hash_type'] = comps[0].strip()
            else:
                return _error(
                    ret, ('Unable to determine upstream hash of'
                          ' source file {0}').format(source))

    # Check changes if the target file exists
    if os.path.isfile(name):
        # Only test the checksums on files with managed contents
        if source:
            name_sum = ''
            hash_func = getattr(hashlib, source_sum['hash_type'])
            with open(name, 'rb') as namefile:
                name_sum = hash_func(namefile.read()).hexdigest()

        # Check if file needs to be replaced
        if source and source_sum['hsum'] != name_sum:
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, __env__)
            if not sfn:
                return _error(
                    ret, 'Source file {0} not found'.format(source))

            # Check to see if the files are bins
            if _is_bin(sfn) or _is_bin(name):
                ret['changes']['diff'] = 'Replace binary file'
            else:
                with nested(open(sfn, 'rb'), open(name, 'rb')) as (src, name_):
                    slines = src.readlines()
                    nlines = name_.readlines()
                # Print a diff equivalent to diff -u old new
                    ret['changes']['diff'] = (''.join(difflib
                                                      .unified_diff(nlines,
                                                                    slines)))
            # Pre requisites are met, and the file needs to be replaced, do it
            if not __opts__['test']:
                shutil.copyfile(sfn, name)
                __clean_tmp(sfn)

        ret, perms = _check_perms(name, ret, user, group, mode)

        if not ret['comment']:
            ret['comment'] = 'File {0} updated'.format(name)

        if __opts__['test']:
            ret['comment'] = 'File {0} not updated'.format(name)
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File {0} is in the correct state'.format(name)
        __clean_tmp(sfn)
        return ret
    else:
        # Only set the diff if the file contents is managed
        if source:
            # It is a new file, set the diff accordingly
            ret['changes']['diff'] = 'New file'
            # Apply the new file
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, __env__)
            if not sfn:
                return ret.error(
                    ret, 'Source file {0} not found'.format(source))

            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    _makedirs(name)
                else:
                    __clean_tmp(sfn)
                    return _error(ret, 'Parent directory not present')
        else:
            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    _makedirs(name)
                else:
                    __clean_tmp(sfn)
                    return _error(ret, 'Parent directory not present')
            # Create the file, user-rw-only if mode will be set
            if mode:
                cumask = os.umask(384)
            if mode:
                os.umask(cumask)
                ret['changes']['new'] = 'file {0} created'.format(name)
                ret['comment'] = 'Empty file'

        # Now copy the file contents if there is a source file
        if sfn:
            shutil.copyfile(sfn, name)
            __clean_tmp(sfn)

        ret, perms = _check_perms(name, ret, user, group, mode)

        if not ret['comment']:
            ret['comment'] = 'File ' + name + ' updated'

        if __opts__['test']:
            ret['comment'] = 'File ' + name + ' not updated'
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File ' + name + ' is in the correct state'
        __clean_tmp(sfn)
        return ret


def directory(name,
        user=None,
        group=None,
        recurse=[],
        mode=None,
        makedirs=False,
        clean=False,
        require=None):
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
    '''
    mode = __manage_mode(mode)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))
    if os.path.isfile(name):
        return _error(
            ret, 'Specified location {0} exists and is a file'.format(name))
    if not os.path.isdir(name):
        # The dir does not exist, make it
        if not os.path.isdir(os.path.dirname(name)):
            if makedirs:
                _makedirs(name)
            else:
                return _error(
                    ret, 'No directory to create {0} in'.format(name))
    if not os.path.isdir(name):
        _makedirs(name)
        os.makedirs(name)
    if not os.path.isdir(name):
        return _error(ret, 'Failed to create directory {0}'.format(name))

    # Check permissions
    ret, perms = _check_perms(name, ret, user, group, mode)

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
                        targets = filter(lambda x: x != 'user', targets)
                else:
                    ret['result'] = False
                    ret['comment'] = 'user not specified, but configured as ' \
                             'a target for recursive ownership management'
                    # Remove 'user' from list of recurse targets
                    targets = filter(lambda x: x != 'user', targets)
            if 'group' in targets:
                if group:
                    gid = __salt__['file.group_to_gid'](group)
                    # As above with user, we need to make sure group exists.
                    if type(gid).__name__ == 'str':
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce group ownership ' \
                                         'for group {0}'.format(group,user)
                        # Remove 'group' from list of recurse targets
                        targets = filter(lambda x: x != 'group', targets)
                else:
                    ret['result'] = False
                    ret['comment'] = 'group not specified, but configured ' \
                             'as a target for recursive ownership management'
                    # Remove 'group' from list of recurse targets
                    targets = filter(lambda x: x != 'group', targets)

            needs_fixed = {}
            if targets:
                file_tree = __salt__['file.find'](name)
                for path in file_tree:
                    fstat = os.stat(path)
                    if 'user' in targets and fstat.st_uid != uid:
                            needs_fixed['user'] = True
                            if needs_fixed.get('group'): break
                    if 'group' in targets and fstat.st_gid != gid:
                            needs_fixed['group'] = True
                            if needs_fixed.get('user'): break

            if needs_fixed.get('user'):
                # Make sure the 'recurse' subdict exists
                ret['changes'].setdefault('recurse',{})
                if 'user' in targets:
                    if __salt__['cmd.retcode']('chown -R {0} "{1}"'.format(
                            user,name)) != 0:
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce ownership on ' \
                                         '{0} for user {1}'.format(name,group)
                    else:
                        ret['changes']['recurse']['user'] = \
                                __salt__['file.uid_to_user'](uid)
            if needs_fixed.get('group'):
                ret['changes'].setdefault('recurse',{})
                if 'group' in targets:
                    if __salt__['cmd.retcode']('chown -R :{0} "{1}"'.format(
                            group,name)) != 0:
                        ret['result'] = False
                        ret['comment'] = 'Failed to enforce group ownership ' \
                                         'on {0} for group ' \
                                         '{1}'.format(name,group)
                    else:
                        ret['changes']['recurse']['group'] = \
                                __salt__['file.gid_to_group'](gid)

    if clean:
        keep = _gen_keep_files(name, require)
        removed = _clean_dir(name, list(keep))
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
        __env__='base'):
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
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not os.path.isabs(name):
        return _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    keep = set()
    # Verify the target directory
    if not os.path.isdir(name):
        if os.path.exists(name):
            # it is not a dir, but it exists - fail out
            return _error(
                ret, 'The path {0} exists and is not a directory'.format(name))
        os.makedirs(name)
    for fn_ in __salt__['cp.cache_dir'](source, __env__):
        if not fn_.strip():
            continue
        dest = os.path.join(name,
                os.path.relpath(
                    fn_,
                    os.path.join(
                        __opts__['cachedir'],
                        'files',
                        __env__,
                        source[7:]
                        )
                    )
                )
        if not os.path.isdir(os.path.dirname(dest)):
            _makedirs(dest)
        if os.path.isfile(dest):
            keep.add(dest)
            srch = ''
            dsth = ''
            # The file is present, if the sum differes replace it
            with nested(open(fn_, 'r'), open(dest, 'r')) as (src_, dst_):
                srch = hashlib.md5(src_.read()).hexdigest()
                dsth = hashlib.md5(dst_.read()).hexdigest()
            if srch != dsth:
                # The downloaded file differes, replace!
                # FIXME: no metadata (ownership, permissions) available
                shutil.copyfile(fn_, dest)
                ret['changes'][dest] = 'updated'
        else:
            keep.add(dest)
            # The destination file is not present, make it
            # FIXME: no metadata (ownership, permissions) available
            shutil.copyfile(fn_, dest)
            ret['changes'][dest] = 'new'
    keep = list(keep)
    if clean:
        keep += _gen_keep_files(name, require)
        removed = _clean_dir(name, list(keep))
        if removed:
            ret['changes']['removed'] = removed
            ret['comment'] = 'Files cleaned from directory {0}'.format(name)
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
          file:
            - sed
            - before: 1
            - after: 0
            - limit: ^enabled=

        # Remove ldap from nsswitch
        /etc/nsswitch.conf:
        file:
            - sed
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

    # Look for the pattern before attempting the edit
    if not __salt__['file.contains'](name, before, limit):
        # Pattern not found; try to guess why
        if __salt__['file.contains'](name, after, limit):
            ret['comment'] = "Edit already performed"
            ret['result'] = True
            return ret
        else:
            ret['comment'] = "Pattern not matched"
            return ret

    # should be ok now; perform the edit
    __salt__['file.sed'](name, before, after, limit, backup, options, flags)

    # check the result
    ret['result'] = __salt__['file.contains'](name, after, limit)

    if ret['result']:
        ret['comment'] = "File successfully edited"
        ret['changes'].update({'old': before, 'new': after})
    else:
        ret['comment'] = "Expected edit does not appear in file"

    return ret

def comment(name, regex, char='#', backup='.bak'):
    '''
    Usage::

        /etc/fstab:
          file:
            - comment
            - regex: ^//10.10.20.5

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    unanchor_regex = regex.lstrip('^').rstrip('$')

    # Make sure the pattern appears in the file before continuing
    if not __salt__['file.contains'](name, regex):
        if __salt__['file.contains'](name, unanchor_regex,
                limit=COMMENT_REGEX.format(char)):
            ret['comment'] = "Pattern already commented"
            ret['result'] = True
            return ret
        else:
            return _error(ret, '{0}: Pattern not found'.format(unanchor_regex))

    # Perform the edit
    __salt__['file.comment'](name, regex, char, backup)

    # Check the result
    ret['result'] = __salt__['file.contains'](name, unanchor_regex,
            limit=COMMENT_REGEX.format(char))
    ret['result'] = __salt__['file.contains'](name, unanchor_regex,
            limit=COMMENT_REGEX.format(char))

    if ret['result']:
        ret['comment'] = "Commented lines successfully"
        ret['changes'] = {'old': '',
                'new': 'Commented lines matching: {0}'.format(regex)}
    else:
        ret['comment'] = "Expected commented lines not found"

    return ret

def uncomment(name, regex, char='#', backup='.bak'):
    '''
    Usage::

        /etc/adduser.conf:
          file:
            - uncomment
            - regex: EXTRA_GROUPS

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    unanchor_regex = regex.lstrip('^')

    # Make sure the pattern appears in the file
    if not __salt__['file.contains'](name, unanchor_regex,
            limit=r'^([[:space:]]*){0}[[:space:]]?'.format(char)):
        if __salt__['file.contains'](name, regex):
            ret['comment'] = "Pattern already uncommented"
            ret['result'] = True
            return ret
        else:
            return _error(ret, '{0}: Pattern not found'.format(regex))

    # Perform the edit
    __salt__['file.uncomment'](name, regex, char, backup)

    # Check the result
    ret['result'] = __salt__['file.contains'](name, regex)

    if ret['result']:
        ret['comment'] = "Uncommented lines successfully"
        ret['changes'] = {'old': '',
                'new': 'Uncommented lines matching: {0}'.format(regex)}
    else:
        ret['comment'] = "Expected uncommented lines not found"

    return ret

def append(name, text):
    '''
    Ensure that some text appears at the end of a file

    The text will not be appended again if it already exists in the file. You
    may specify a single line of text or a list of lines to append.

    Multi-line example::

        /etc/motd:
          file:
            - append
            - text: |
                Thou hadst better eat salt with the Philosophers of Greece,
                than sugar with the Courtiers of Italy.
                - Benjamin Franklin

    Multiple lines of text::

        /etc/motd:
          file:
            - append
            - text:
              - Trust no one unless you have eaten much salt with him.
              - Salt is born of the purest of parents: the sun and the sea.

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    check_res, check_msg = _check_file(name)
    if not check_res:
        return _error(ret, check_msg)

    if isinstance(text, basestring):
        text = (text,)

    for chunk in text:
        try:
            lines = chunk.split('\n')
        except AttributeError:
            logger.debug("Error appending text to %s; given object is: %s",
                    name, type(chunk))
            return _error(ret, "Given text is not a string")

        for line in lines:
            if __salt__['file.contains'](name, line):
                continue
            else:
                __salt__['file.append'](name, line)
                cgs = ret['changes'].setdefault('new', [])
                cgs.append(line)

    count = len(ret['changes'].get('new', []))

    ret['comment'] = "Appended {0} lines".format(count)
    ret['result'] = True
    return ret


def touch(name, atime=None, mtime=None, makedirs=False):
    """
    Replicate the 'nix "touch" command to create a new empty
    file or update the atime and mtime of an existing  file.

    Usage::

        /var/log/httpd/logrotate.empty
          file:
            - touch

    .. versionadded:: 0.9.5
    """
    ret = {
        'name': name,
        'changes': {},
    }
    if not os.path.isabs(name):
        _error(
            ret, 'Specified file {0} is not an absolute path'.format(name))

    if makedirs:
        _makedirs(name)
    if not os.path.isdir(os.path.dirname(name)):
        return _error(
            ret, 'Directory not present to touch file {0}'.format(name))
    exists = os.path.exists(name)
    ret['result'] = __salt__['file.touch'](name, atime, mtime)

    if not exists and ret['result']:
        ret["comment"] = 'Created empty file {0}'.format(name)
        ret["changes"]['new'] = name
    elif exists and ret['result']:
        ret["comment"] = 'Updated times on file {0}'.format(name)

    return ret

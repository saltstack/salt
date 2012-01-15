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

Symlinks can be easily created, the symlink function is very simple and only
takes a few arguments

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

import os
import shutil
import difflib
import hashlib
import logging
import tempfile
import traceback

logger = logging.getLogger(__name__)

COMMENT_REGEX = r'^([[:space:]]*){0}[[:space:]]?'


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
    if open(path, 'rb').read(2048).count('\0'):
        return True
    return False


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
    rm_files = []
    print real_keep
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
        template = Template(open(sfn, 'r').read())
        open(tgt, 'w+').write(template.render(**passthrough))
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
        open(tgt, 'w+').write(template.render(**passthrough))
        return {'result': True,
                    'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


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
    if not os.path.isdir(os.path.dirname(name)):
        if makedirs:
            _makedirs(name)
        else:
            ret['result'] = False
            ret['comment'] = ('Directory {0} for symlink is not present'
                            .format(os.path.dirname(name)))
            return ret
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
            ret['result'] = False
            ret['comment'] = ('File exists where the symlink {0} should be'
                              .format(name))
            return ret
    elif os.path.isdir(name):
        # It is not a link or a file, it is a dir, error out
        if force:
            shutil.rmtree(name)
        else:
            ret['result'] = False
            ret['comment'] = ('Directory exists where the symlink {0} '
                              'should be'.format(name))
            return ret
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
    if os.path.isfile(name) or os.path.islink(name):
        try:
            os.remove(name)
            ret['comment'] = 'Removed file {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except:
            ret['result'] = False
            ret['comment'] = 'Failed to remove file {0}'.format(name)
            return ret
    elif os.path.isdir(name):
        try:
            shutil.rmtree(name)
            ret['comment'] = 'Removed directory {0}'.format(name)
            ret['changes']['removed'] = name
            return ret
        except:
            ret['result'] = False
            ret['comment'] = 'Failed to remove directory {0}'.format(name)
            return ret
    ret['comment'] = 'File {0} is not present'.format(name)
    return ret


def managed(name,
        source=None,
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
        The source file, this file is located on the salt master file server
        and is specified with the salt:// protocol. If the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs. If source is left blank or None, the file
        will be created as an empty file and the content will not be  managed

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
    if mode:
        mode = str(mode)
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    # Gather the source file from the server
    sfn = ''
    source_sum = {}

    # If the file is a template and the contents is managed
    # then make sure to cpy it down and templatize  things.
    if template and source:
        sfn = __salt__['cp.cache_file'](source, __env__)
        t_key = '_{0}'.format(template)
        if t_key in globals():
            context_dict = defaults if defaults else {}
            if context: context_dict.update(context)
            data = globals()[t_key](
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
            ret['result'] = False
            ret['comment'] = ('Specified template format {0} is not supported'
                              .format(template))
            return ret
        if data['result']:
            sfn = data['data']
            hsum = hashlib.md5(open(sfn, 'r').read()).hexdigest()
            source_sum = {'hash_type': 'md5',
                          'hsum': hsum}
        else:
            ret['result'] = False
            ret['comment'] = data['data']
            __clean_tmp(sfn)
            return ret
    else:
        # Copy the file down if there is a source
        if source:
            source_sum = __salt__['cp.hash_file'](source, __env__)
            if not source_sum:
                ret['result'] = False
                ret['comment'] = 'Source file {0} not found'.format(source)
                return ret
    # If the source file is a template render it accordingly

    # Check changes if the target file exists
    if os.path.isfile(name):
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
                    ret['comment'] += 'Mode not changed '
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

        # Only test the checksums on files with managed contents
        if source:
            name_sum = getattr(hashlib, source_sum['hash_type'])(open(name,
            'rb').read()).hexdigest()

        # Check if file needs to be replaced
        if source and source_sum['hsum'] != name_sum:
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, __env__)
            if not sfn:
                ret['result'] = False
                ret['comment'] = 'Source file {0} not found'.format(source)
                return ret
            # Check to see if the files are bins
            if _is_bin(sfn) or _is_bin(name):
                ret['changes']['diff'] = 'Replace binary file'
            else:
                slines = open(sfn, 'rb').readlines()
                nlines = open(name, 'rb').readlines()
                # Print a diff equivalent to diff -u old new
                ret['changes']['diff'] = (''.join(difflib
                                                    .unified_diff(nlines,
                                                                  slines)))
            # Pre requisites are met, and the file needs to be replaced, do it
            if not __opts__['test']:
                shutil.copyfile(sfn, name)

        if not ret['comment']:
            ret['comment'] = 'File {0} updated'.format(name)

        if __opts__['test']:
            ret['comment'] = 'File {0} not updated'.format(name)
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File {0} is in the correct state'.format(name)
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
                ret['result'] = False
                ret['comment'] = 'Source file {0} not found'.format(source)
                return ret
            if not __opts__['test']:
                if not os.path.isdir(os.path.dirname(name)):
                    if makedirs:
                        _makedirs(name)
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Parent directory not present'
                        __clean_tmp(sfn)
                        return ret
        else:
            ret['changes']['new'] = 'file {0} created'.format(name)
            ret['comment'] = 'Empty file'
        # Create the file, user-rw-only if mode will be set
        if mode:
          cumask = os.umask(384)
        open(name, 'a').close()
        if mode:
          os.umask(cumask)
        # Check permissions
        perms = {}
        perms['luser'] = __salt__['file.get_user'](name)
        perms['lgroup'] = __salt__['file.get_group'](name)
        perms['lmode'] = __salt__['file.get_mode'](name)
        # Run through the perms and detect and apply the needed changes to
        # permissions
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
        if mode:
            if mode != perms['lmode']:
                if not __opts__['test']:
                    __salt__['file.set_mode'](name, mode)
                if mode != __salt__['file.get_mode'](name):
                    ret['result'] = False
                    ret['comment'] += 'Mode not changed '
                else:
                    ret['changes']['mode'] = mode
        if user:
            if user != __salt__['file.get_user'](name):
                ret['result'] = False
                ret['comment'] += 'User not changed '
            elif 'cuser' in perms:
                ret['changes']['user'] = user
        if group:
            if group != __salt__['file.get_group'](name):
                ret['result'] = False
                ret['comment'] += 'Group not changed '
            elif 'cgroup' in perms:
                ret['changes']['group'] = group

        # Now copy the file contents if there is a source file
        if sfn:
            shutil.copyfile(sfn, name)

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
    if mode:
        mode = str(mode)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if os.path.isfile(name):
        ret['result'] = False
        ret['comment'] = ('Specified location {0} exists and is a file'
                          .format(name))
        return ret
    if not os.path.isdir(name):
        # The dir does not exist, make it
        if not os.path.isdir(os.path.dirname(name)):
            if makedirs:
                _makedirs(name)
            else:
                ret['result'] = False
                ret['comment'] = 'No directory to create {0} in'.format(name)
                return ret
    if not os.path.isdir(name):
        _makedirs(name)
        os.makedirs(name)
    if not os.path.isdir(name):
        ret['result'] = False
        ret['comment'] = 'Failed to create directory {0}'.format(name)
        return ret

    # Check permissions
    perms = {}
    perms['luser'] = __salt__['file.get_user'](name)
    perms['lgroup'] = __salt__['file.get_group'](name)
    perms['lmode'] = __salt__['file.get_mode'](name)
    # Run through the perms and detect and apply the needed changes
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
    if mode:
        if mode != perms['lmode']:
            if not __opts__['test']:
                __salt__['file.set_mode'](name, mode)
            if mode != __salt__['file.get_mode'](name):
                ret['result'] = False
                ret['comment'] += 'Mode not changed '
            else:
                ret['changes']['mode'] = mode
    if user:
        if user != __salt__['file.get_user'](name):
            ret['result'] = False
            ret['comment'] = 'Failed to change user to {0} '.format(user)
        elif 'cuser' in perms:
            ret['changes']['user'] = user
    if group:
        if group != __salt__['file.get_group'](name):
            ret['result'] = False
            ret['comment'] += 'Failed to change group to {0} '.format(group)
        elif 'cgroup' in perms:
            ret['changes']['group'] = group

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
    keep = set()
    # Verify the target directory
    if not os.path.isdir(name):
        if os.path.exists(name):
            # it is not a dir, but it exists - fail out
            ret['result'] = False
            ret['comment'] = ('The path {0} exists and is not a directory'
                              .format(name))
            return ret
        os.makedirs(name)
    for fn_ in __salt__['cp.cache_dir'](source, __env__):
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
            # The file is present, if the sum differes replace it
            srch = hashlib.md5(open(fn_, 'r').read()).hexdigest()
            dsth = hashlib.md5(open(dest, 'r').read()).hexdigest()
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

    Usage::

        # Disable the epel repo by default
        /etc/yum.repos.d/epel.repo:
          file:
            - sed
            - before: 1
            - after: 0
            - limit: ^enabled=

    .. versionadded:: 0.9.5
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if not os.path.exists(name):
        ret['comment'] = "File '{0}' not found".format(name)
        return ret

    # sed returns no output if the edit matches anything or not so we'll have
    # to look for ourselves

    # make sure the pattern(s) match
    if not __salt__['file.contains'](name, before, limit):
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

    unanchor_regex = regex.lstrip('^').rstrip('$')

    if not os.path.exists(name):
        ret['comment'] = "File not found"
        return ret

    # Make sure the pattern appears in the file before continuing
    if not __salt__['file.contains'](name, regex):
        if __salt__['file.contains'](name, unanchor_regex,
                limit=COMMENT_REGEX.format(char)):
            ret['comment'] = "Pattern already commented"
            ret['result'] = True
            return ret
        else:
            ret['comment'] = "Pattern not found"
            return ret

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
    unanchor_regex = regex.lstrip('^')

    if not os.path.exists(name):
        ret['comment'] = "File not found"
        return ret

    # Make sure the pattern appears in the file
    if not __salt__['file.contains'](name, unanchor_regex,
            limit=r'^([[:space:]]*){0}[[:space:]]?'.format(char)):
        if __salt__['file.contains'](name, regex):
            ret['comment'] = "Pattern already uncommented"
            ret['result'] = True
            return ret
        else:
            ret['comment'] = "Pattern not found"
            return ret

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

    if isinstance(text, basestring):
        text = (text,)

    for chunk in text:
        for line in chunk.split('\n'):
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

def touch(name, atime=None, mtime=None):
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
    exists = os.path.exists(name)
    ret['result'] = __salt__['file.touch'](name, atime, mtime)

    if not exists and ret['result']:
        ret["comment"] = 'Created empty file {0}'.format(name)
        ret["changes"]['new'] = name
    elif exists and ret['result']:
        ret["comment"] = 'Updated times on file {0}'.format(name)

    return ret

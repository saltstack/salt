'''
File Management
===============

Salt States can agresively manipulate files on a system. There are a number of
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

Directories can be managed via the ``directory`` function. This function can
create and enforce the premissions on a directory. A directory statement will
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
master to be recursively coppied down to the minion. This is a great tool for
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
import tempfile
import difflib
import hashlib
import traceback

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

def _mako(sfn):
    '''
    Render a jinja2 template, returns the location of the rendered file,
    return False if render fails.
    Returns:
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
        passthrough = {}
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

def _jinja(sfn):
    '''
    Render a jinja2 template, returns the location of the rendered file,
    return False if render fails.
    Returns:
        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from jinja2 import Template
    except ImportError:
        return {'result': False,
                'data': 'Failed to import jinja'}
    try:
        tgt = tempfile.mkstemp()[1]
        passthrough = {}
        passthrough['salt'] = __salt__
        passthrough['grains'] = __grains__
        template = Template(open(sfn, 'r').read())
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
        ret['result'] = False
        ret['comment'] = 'Directory {0} for symlink is not present'.format(os.path.dirname(name))
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
            ret['comment'] = 'File exists where the symlink {0} should be'.format(name)
            return ret
    elif os.path.isdir(name):
        # It is not a link or a file, it is a dir, error out
        if force:
            shutil.rmtree(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Direcotry exists where the symlink {0} should be'.format(name)
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
        source,
        user=None,
        group=None,
        mode=None,
        template=None,
        makedirs=False,
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
        string is salt://spam/eggs

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
        If the file is located in a path without a parent directory, then the
        the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.
    '''
    if mode:
        mode = str(mode)
    ret =  {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}
    # Gather the source file from the server
    sfn = ''
    source_sum = {}
    if template:
        sfn = __salt__['cp.cache_file'](source, __env__)
        t_key = '_{0}'.format(template)
        if globals().has_key(t_key):
            data = globals()[t_key](sfn)
        else:
            ret['result'] = False
            ret['comment'] = 'Specified template format {0} is not supported'.format(template)
            return ret
        if data['result']:
            sfn = data['data']
            hsum = hashlib.md5(open(sfn, 'r').read()).hexdigest()
            source_sum = {'hash_type': 'md5',
                          'hsum': hsum}
        else:
            ret['result'] = False
            ret['comment'] = data['data']
            return ret
    else:
        source_sum = __salt__['cp.hash_file'](source, __env__)
        if not source_sum:
            ret['result'] = False
            ret['comment'] = 'Source file {0} not found'.format(source)
            return ret
    # If the source file is a template render it accordingly

    # Check changes if the target file exists
    if os.path.isfile(name):
        name_sum = getattr(hashlib, source_sum['hash_type'])(open(name,
            'rb').read()).hexdigest()
        # Check if file needs to be replaced
        if source_sum['hsum'] != name_sum:
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
                ret['changes']['diff'] = '\n'.join(difflib.unified_diff(slines, nlines))
            # Pre requs are met, and the file needs to be replaced, do it
            if not __opts__['test']:
                shutil.copy(sfn, name)
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
        if perms.has_key('cuser') or perms.has_key('cgroup'):
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
            elif perms.has_key('cuser'):
                ret['changes']['user'] = user
        if group:
            if group != __salt__['file.get_group'](name):
                ret['result'] = False
                ret['comment'] += 'Failed to change group to {0} '.format(group)
            elif perms.has_key('cgroup'):
                ret['changes']['group'] = group

        if not ret['comment']:
            ret['comment'] = 'File {0} updated'.format(name)

        if __opts__['test']:
            ret['comment'] = 'File {0} not updated'.format(name)
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File {0} is in the correct state'.format(name)
        return ret
    else:
        # It is a new file, set the diff accordingly
        ret['changes']['diff'] = 'New file'
        # Apply the new file
        if not __opts__['test']:
            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    _makedirs(name)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Parent directory not present'
                    return ret
            shutil.copy(sfn, name)
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
        if perms.has_key('cuser') or perms.has_key('cgroup'):
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
            elif perms.has_key('cuser'):
                ret['changes']['user'] = user
        if group:
            if group != __salt__['file.get_group'](name):
                ret['result'] = False
                ret['comment'] += 'Group not changed '
            elif perms.has_key('cgroup'):
                ret['changes']['group'] = group

        if not ret['comment']:
            ret['comment'] = 'File ' + name + ' updated'

        if __opts__['test']:
            ret['comment'] = 'File ' + name + ' not updated'
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File ' + name + ' is in the correct state'
        return ret

def directory(name,
        user=None,
        group=None,
        mode=None,
        makedirs=False):
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
        the the state will fail. If makedirs is set to True, then the parent
        directories will be created to facilitate the creation of the named
        file.
    '''
    if mode:
        mode = str(mode)
    ret =  {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}
    if os.path.isfile(name):
        ret['result'] = False
        ret['comment'] = 'Specifed location {0} exists and is a file'.format(name)
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
    if perms.has_key('cuser') or perms.has_key('cgroup'):
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
        elif perms.has_key('cuser'):
            ret['changes']['user'] = user
    if group:
        if group != __salt__['file.get_group'](name):
            ret['result'] = False
            ret['comment'] += 'Failed to change group to {0} '.format(group)
        elif perms.has_key('cgroup'):
            ret['changes']['group'] = group

    if not ret['comment']:
        ret['comment'] = 'Directory {0} updated'.format(name)

    if __opts__['test']:
        ret['comment'] = 'Directory {0} not updated'.format(name)
    elif not ret['changes'] and ret['result']:
        ret['comment'] = 'Directory {0} is in the correct state'.format(name)
    return ret

def recurse(name,
        source,
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
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    # Verify the target directory
    if not os.path.isdir(name):
        if os.path.exists(name):
            # it is not a dir, but it exists - fail out
            ret['result'] = False
            ret['comment'] = 'The path {0} exists and is not a directory'.format(name)
            return ret
        os.makedirs(name)
    for fn_ in __salt__['cp.cache_dir'](source, __env__):
        dest = os.path.join(name,
                os.path.relpath(
                    fn_,
                    os.path.join(
                        __opts__['cachedir'],
                        'files',
                        __env__
                        )
                    )
                )
        if not os.path.isdir(os.path.dirname(dest)):
            _makedirs(dest)
        if os.path.isfile(dest):
            # The file is present, if the sum differes replace it
            srch = hashlib.md5(open(fn_, 'r').read()).hexdigest()
            dsth = hashlib.md5(open(dest, 'r').read()).hexdigest()
            if srch != dsth:
                # The downloaded file differes, replace!
                shutil.copy(fn_, dest)
                ret['changes'][dest] = 'updated'
        else:
            # The destination file is not present, make it
            shutil.copy(fn_, dest)
            ret['changes'][dest] = 'new'
    return ret

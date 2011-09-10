'''
Manage file states
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

def managed(name,
        source,
        user=None,
        group=None,
        mode=None,
        template=None,
        makedirs=False):
    '''
    Manage a given file
    '''
    if mode:
        mode = str(mode)
    ret =  {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}
    # Check changes if the target file exists
    if os.path.isfile(name):
        # Check sums
        source_sum = __salt__['cp.hash_file'](source)
        if not source_sum:
            ret['result'] = False
            ret['comment'] = 'Source file {0} not found'.format(source)
            return ret
        name_sum = getattr(hashlib, source_sum['hash_type'])(open(name,
            'rb').read()).hexdigest()
        # Check if file needs to be replaced
        if source_sum['hsum'] != name_sum:
            sfn = __salt__['cp.cache_file'](source)
            if not sfn:
                ret['result'] = False
                ret['comment'] = 'Source file {0} not found'.format(source)
                return ret
            # If the source file is a template render it accordingly
            if template:
                t_key = '_' + template
                if locals().has_key(t_key):
                    data = locals()[t_key](sfn)
                if data['result']:
                    sfn = data['data']
                else:
                    ret['result'] = False
                    ret['comment'] = data['data']
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
        # The file is not currently present, throw it down, log all changes
        sfn = __salt__['cp.cache_file'](source)
        if not sfn:
            ret['result'] = False
            ret['comment'] = 'Source file {0} not found'.format(source)
            return ret
        # Handle any template management that is needed
        if template:
            t_key = '_' + template
            if locals().has_key(t_key):
                data = locals()[t_key](sfn)
            if data['result']:
                sfn = data['data']
            else:
                ret['result'] = False
                return ret
        # It is a new file, set the diff accordingly
        ret['changes']['diff'] = 'New file'
        # Apply the new file
        if not __opts__['test']:
            if makedirs:
                _makedirs(name)
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


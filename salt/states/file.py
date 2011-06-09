'''
Manage file states
'''

import os
import shutil
import tempfile
import difflib
import hashlib

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
    changes = {}
    # Check changes if the target file exists
    if os.path.isfile(name):
        # Check sums
        source_sum = __salt__['cp.hash_file'](source)
        name_sum = getattr(hashlib, source_sum['hash_type'])(open(name,
            'rb').read()).hexdigest()
        if not source_sum:
            return {'name': name,
                    'changes': changes,
                    'result': False,
                    'comment': 'Source file ' + source + ' not found'}
        # Check if file needs to be replaced
        if source_sum['hsum'] != name_sum:
            sfn = __salt__['cp.cache_file'](source)
            if not sfn:
                return {'name': name,
                        'changes': changes,
                        'result': False,
                        'comment': 'Source file ' + source + ' not found'}
            # If the source file is a template render it accordingly
            if template:
                t_key = '_' + template
                if locals().has_key(t_key):
                    data = locals()[t_key](sfn)
                if data['result']:
                    sfn = data['data']
                else:
                    return {'name': name,
                            'changes': changes,
                            'result': False,
                            'comment': data['data']}
            # Check to see if the files are bins
            if _is_bin(sfn) or _is_bin(name):
                changes['diff'] = 'Replace binary file'
            else:
                slines = open(sfn, 'rb').readlines()
                nlines = open(name, 'rb').readlines()
                changes['diff'] = '\n'.join(difflib.unified_diff(slines, nlines))
            # Pre requs are met, and the file needs to be replaced, do it
            if not __opts__['test']:
                shutil.copy(sfn, name)
        # Check permissions
        luser = __salt__['file.get_user'](name)
        lgroup = __salt__['file.get_group'](name)
        lmode = __salt__['file.get_mode'](name)
        # Run through the perms and detect and apply the needed changes
        if user:
            if user != luser:
                changes['user'] = user
                luser = user
        if group:
            if group != lgroup:
                changes['group'] = group
                lgroup = group
        if changes.has_key('user') or changes.has_key('group'):
            if not __opts__['test']:
                __salt__['file.chown'](name, luser, lgroup)
        if mode:
            if mode != lmode:
                changes['mode'] = mode
                if not __opts__['test']:
                    __salt__['file.set_mode'](name, mode)
        comment = 'File ' + name + ' updated'
        if __opts__['test']:
            comment = 'File ' + name + ' not updated'
        elif not changes:
            comment = 'File ' + name + ' is in the correct state'
        return {'name': name,
                'changes': changes,
                'result': True,
                'comment': comment}
    else:
        # The file is not currently present, throw it down, log all changes
        sfn = __salt__['cp.cache_file'](source)
        if not sfn:
            return {'name': name,
                    'changes': changes,
                    'result': False,
                    'comment': 'Source file ' + source + ' not found'}
        # Handle any template management that is needed
        if template:
            t_key = '_' + template
            if locals().has_key(t_key):
                data = locals()[t_key](sfn)
            if data['result']:
                sfn = data['data']
            else:
                return {'name': name,
                        'changes': changes,
                        'result': False,
                        'comment': data['data']}
        # It is a new file, set the diff accordingly
        changes['diff'] = 'New file'
        # Apply the new file
        if not __opts__['test']:
            if makedirs:
                _makedirs(name)
            shutil.copy(sfn, name)
        # Get the data about the file
        luser = __salt__['file.get_user'](name)
        lgroup = __salt__['file.get_group'](name)
        lmode = __salt__['file.get_mode'](name)
        # Set up user, group and mode for the file
        if user:
            changes['user'] = user
            luser = user
        if group:
            changes['group'] = group
            lgroup = group
        if changes.has_key('user') or changes.has_key('group'):
            if not __opts__['test']:
                __salt__['file.chown'](name, luser, lgroup)
        if mode:
            changes['mode'] = mode
            if not __opts__['test']:
                __salt__['file.set_mode'](name, mode)
        # All done, apply the comment and get out of here
        comment = 'File ' + name + ' not updated'
        if not __opts__['test']:
            comment = 'File ' + name + ' updated'
        return {'name': name,
                'changes': changes,
                'result': True,
                'comment': comment}


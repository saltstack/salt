# -*- coding: utf-8 -*-
'''
Read in files from the file_root and save files to the file root
'''

# Import python libs
from __future__ import absolute_import
import os

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


def find(path, saltenv='base', env=None):
    '''
    Return a dict of the files located with the given path and environment
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    # Return a list of paths + text or bin
    ret = []
    if saltenv not in __opts__['file_roots']:
        return ret
    for root in __opts__['file_roots'][saltenv]:
        full = os.path.join(root, path)
        if os.path.isfile(full):
            # Add it to the dict
            with salt.utils.fopen(full, 'rb') as fp_:
                if salt.utils.istextfile(fp_):
                    ret.append({full: 'txt'})
                else:
                    ret.append({full: 'bin'})
    return ret


def list_env(saltenv='base', env=None):
    '''
    Return all of the file paths found in an environment
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    ret = {}
    if saltenv not in __opts__['file_roots']:
        return ret
    for f_root in __opts__['file_roots'][saltenv]:
        ret[f_root] = {}
        for root, dirs, files in os.walk(f_root):
            sub = ret[f_root]
            if root != f_root:
                # grab subroot ref
                sroot = root
                above = []
                # Populate the above dict
                while not os.path.samefile(sroot, f_root):
                    base = os.path.basename(sroot)
                    if base:
                        above.insert(0, base)
                    sroot = os.path.dirname(sroot)
                for aroot in above:
                    sub = sub[aroot]
            for dir_ in dirs:
                sub[dir_] = {}
            for fn_ in files:
                sub[fn_] = 'f'
    return ret


def list_roots():
    '''
    Return all of the files names in all available environments
    '''
    ret = {}
    for saltenv in __opts__['file_roots']:
        ret[saltenv] = []
        ret[saltenv].append(list_env(saltenv))
    return ret


def read(path, saltenv='base', env=None):
    '''
    Read the contents of a text file, if the file is binary then
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    # Return a dict of paths + content
    ret = []
    files = find(path, saltenv)
    for fn_ in files:
        full = next(six.iterkeys(fn_))
        form = fn_[full]
        if form == 'txt':
            with salt.utils.fopen(full, 'rb') as fp_:
                ret.append({full: fp_.read()})
    return ret


def write(data, path, saltenv='base', index=0, env=None):
    '''
    Write the named file, by default the first file found is written, but the
    index of the file can be specified to write to a lower priority file root
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    if saltenv not in __opts__['file_roots']:
        return 'Named environment {0} is not present'.format(saltenv)
    if len(__opts__['file_roots'][saltenv]) <= index:
        return 'Specified index {0} in environment {1} is not present'.format(
                index, saltenv)
    if os.path.isabs(path):
        return ('The path passed in {0} is not relative to the environment '
                '{1}').format(path, saltenv)
    dest = os.path.join(__opts__['file_roots'][saltenv][index], path)
    dest_dir = os.path.dirname(dest)
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    with salt.utils.fopen(dest, 'w+') as fp_:
        fp_.write(data)
    return 'Wrote data to file {0}'.format(dest)

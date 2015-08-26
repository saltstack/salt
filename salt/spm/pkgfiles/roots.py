# -*- coding: utf-8 -*-
'''
This module allows SPM to use the local filesystem (``file_roots``) to install
files for SPM.

.. versionadded:: 2015.8.0
'''

from __future__ import absolute_import
import os
import os.path
import logging

# Get logging started
log = logging.getLogger(__name__)


def init(**kwargs):
    '''
    Initialize the directories for the files
    '''
    roots_path = __opts__['file_roots']['base'][0]
    pillar_path = __opts__['pillar_roots']['base'][0]
    for dir_ in (roots_path, pillar_path):
        if not os.path.exists(dir_):
            os.makedirs(dir_)
    return {
        'roots_path': roots_path,
        'pillar_path': pillar_path,
    }


def check_existing(package, pkg_files, conn=None):
    '''
    Check the filesystem for existing files
    '''
    if conn is None:
        conn = init()

    existing_files = []
    for member in pkg_files:
        if member.isdir():
            continue
        if member.name.startswith('{0}/_'.format(package)):
            # Module files are distributed via _modules, _states, etc
            new_name = member.name.replace('{0}/'.format(package), '')
            out_file = os.path.join(conn['roots_path'], new_name)
        elif member.name == '{0}/pillar.example'.format(package):
            # Pillars are automatically put in the pillar_roots
            new_name = '{0}.sls.orig'.format(package)
            out_file = os.path.join(conn['pillar_path'], new_name)
        elif package.endswith('-conf'):
            # Module files are distributed via _modules, _states, etc
            new_name = member.name.replace('{0}/'.format(package), '')
            out_file = os.path.join('/', 'etc', 'salt', new_name)
        else:
            out_file = os.path.join(conn['roots_path'], member.name)

        if os.path.exists(out_file):
            existing_files.append(out_file)
            if not __opts__['force']:
                log.error('{0} already exists, not installing'.format(out_file))

    return existing_files


def install_file(package, formula_tar, member, conn=None):
    '''
    Install a single file to the file system
    '''
    if conn is None:
        conn = init()

    out_path = conn['roots_path']

    if member.name.startswith('{0}/_'.format(package)):
        # Module files are distributed via _modules, _states, etc
        member.name = member.name.replace('{0}/'.format(package), '')
    elif member.name == '{0}/pillar.example'.format(package):
        # Pillars are automatically put in the pillar_roots
        member.name = '{0}.sls.orig'.format(package)
        out_path = conn['pillar_path']
    elif package.endswith('-conf'):
        # Module files are distributed via _modules, _states, etc
        member.name = member.name.replace('{0}/'.format(package), '')
        out_path = os.path.join('/', 'etc', 'salt')

    log.debug('Installing package file {0} to {1}'.format(member.name, out_path))
    formula_tar.extract(member, out_path)

    return out_path


def remove_file(path, conn=None):
    '''
    Install a single file to the file system
    '''
    if conn is None:
        conn = init()

    log.debug('Removing package file {0}'.format(path))
    os.remove(path)


def path_exists(path):
    '''
    Check to see whether the file already exists
    '''
    return os.path.exists(path)


def path_isdir(path):
    '''
    Check to see whether the file already exists
    '''
    return os.path.isdir(path)

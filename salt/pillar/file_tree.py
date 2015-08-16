# -*- coding: utf-8 -*-

'''
Recursively iterate over directories and add all files as Pillar data.

Example configuration:

.. code-block:: yaml

    ext_pillar:
      - file_tree:
          root_dir: /path/to/root/directory
          follow_dir_links: False
          raw_data: False

The ``root_dir`` parameter is required and points to the directory where files
for each host are stored. The ``follow_dir_links`` parameter is optional
and defaults to False. If ``follow_dir_links`` is set to True, file_tree will
follow symbolic links to other directories. Be careful when using
``follow_dir_links``, the current implementation is dumb and will run into
infinite recursion if a recursive symlink chain exists in the root_dir!

If ``raw_data`` is set to True, it will revert the behavior of the python
open() function, which adds a line break character at the end of the file,
in this case, the pillar data.

To fill pillar data for each host, file_tree recursively iterates over
``root_dir``/hosts/``id`` (where ``id`` is a minion ID), and constructs
the same directory tree with contents of all the files inside the pillar tree.

For example, the following ``root_dir`` tree::

    ./hosts/
    ./hosts/test-host/
    ./hosts/test-host/files/
    ./hosts/test-host/files/testdir/
    ./hosts/test-host/files/testdir/file1.txt
    ./hosts/test-host/files/testdir/file2.txt
    ./hosts/test-host/files/another-testdir/
    ./hosts/test-host/files/another-testdir/symlink-to-file1.txt

will result in the following pillar tree for minion with ID "test-host"::

    test-host:
        ----------
        files:
            ----------
            another-testdir:
                ----------
                symlink-to-file1.txt:
                    Contents of file #1.

            testdir:
                ----------
                file1.txt:
                    Contents of file #1.

                file2.txt:
                    Contents of file #2.

To fill pillar data for minion in a node group, file_tree recursively
iterates over ``root_dir``/nodegroups/``nodegroup`` (where ``nodegroup`` is a
minion node group), and constructs the same directory tree with contents of all
the files inside the pillar tree.
**IMPORTANT**: The host data take precedence over the node group data

For example, the following ``root_dir`` tree::

    ./nodegroups/
    ./nodegroups/test-group/
    ./nodegroups/test-group/files/
    ./nodegroups/test-group/files/testdir/
    ./nodegroups/test-group/files/testdir/file1.txt
    ./nodegroups/test-group/files/testdir/file2.txt
    ./nodegroups/test-group/files/another-testdir/
    ./nodegroups/test-group/files/another-testdir/symlink-to-file1.txt

will result in the following pillar tree for minion in the node group
"test-group"::

    test-host:
        ----------
        files:
            ----------
            another-testdir:
                ----------
                symlink-to-file1.txt:
                    Contents of file #1.

            testdir:
                ----------
                file1.txt:
                    Contents of file #1.

                file2.txt:
                    Contents of file #2.
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import os.path
from copy import deepcopy

# Import salt libs
import salt.utils
import salt.utils.minions
import salt.ext.six as six

# Set up logging
log = logging.getLogger(__name__)


def _on_walk_error(err):
    '''
    Log os.walk() error.
    '''
    log.error('"%s": %s', err.filename, err.strerror)


# Thanks to Ross McFarland for the dict_merge function
# (Source: https://www.xormedia.com/recursively-merge-dictionaries-in-python/)
def _dict_merge(dict_a, dict_b):
    '''
    recursively merges dict's. not just simple dict_a['key'] = dict_b['key'],
    if both dict_a and dict_b have a key who's value is a dict then
    _dict_merge is called on both values and the result stored in the returned
     dictionary.
    '''
    if not isinstance(dict_b, dict):
        return dict_b
    result = deepcopy(dict_a)
    for key, value in six.iteritems(dict_b):
        if key in result and isinstance(result[key], dict):
            result[key] = _dict_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _construct_pillar(top_dir, follow_dir_links, raw_data=False):
    '''
    Construct pillar from file tree.
    '''
    pillar = {}

    norm_top_dir = os.path.normpath(top_dir)
    for dir_path, dir_names, file_names in os.walk(
            top_dir, topdown=True, onerror=_on_walk_error,
            followlinks=follow_dir_links):
        # Find current path in pillar tree.
        pillar_node = pillar
        norm_dir_path = os.path.normpath(dir_path)
        if norm_dir_path != norm_top_dir:
            rel_path = os.path.relpath(norm_dir_path, norm_top_dir)
            path_parts = []
            while rel_path:
                rel_path, tail = os.path.split(rel_path)
                path_parts.insert(0, tail)
            while path_parts:
                pillar_node = pillar_node[path_parts.pop(0)]

        # Create dicts for subdirectories.
        for dir_name in dir_names:
            pillar_node[dir_name] = {}

        # Add files.
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            if not os.path.isfile(file_path):
                log.error('"%s": Not a regular file', file_path)
                continue

            try:
                with salt.utils.fopen(file_path, 'rb') as fhr:
                    pillar_node[file_name] = fhr.read()
                    if raw_data is False and pillar_node[file_name].endswith('\n'):
                        pillar_node[file_name] = pillar_node[file_name][:-1]
            except IOError as err:
                log.error('%s', str(err))

    return pillar


def ext_pillar(
        minion_id, pillar, root_dir=None,
        follow_dir_links=False, debug=False, raw_data=False):
    '''
    Find pillar data for specified ID.
    '''
    # Not used.
    del pillar

    if not root_dir:
        log.error('No root_dir specified for file_tree pillar')
        return {}
    if not os.path.isdir(root_dir):
        log.error('"%s" does not exist or not a directory', root_dir)
        return {}

    ngroup_pillar = {}
    nodegroups_dir = os.path.join(root_dir, 'nodegroups')
    if os.path.exists(nodegroups_dir) and len(__opts__['nodegroups']) > 0:
        master_ngroups = __opts__['nodegroups']
        ext_pillar_dirs = os.listdir(nodegroups_dir)
        if len(ext_pillar_dirs) > 0:
            for nodegroup in ext_pillar_dirs:
                if (os.path.isdir(nodegroups_dir) and
                        nodegroup in master_ngroups):
                    ckminions = salt.utils.minions.CkMinions(__opts__)
                    match = ckminions.check_minions(
                        master_ngroups[nodegroup],
                        'compound')
                    if minion_id in match:
                        ngroup_dir = os.path.join(
                            nodegroups_dir, str(nodegroup))
                        ngroup_pillar.update(
                            _construct_pillar(ngroup_dir, follow_dir_links))
        else:
            if debug is True:
                log.debug('File tree - No nodegroups found in file tree \
                            directory ext_pillar_dirs, skipping...')
    else:
        if debug is True:
            log.debug('File tree - No nodegroups found in master \
                      configuration, skipping nodegroups pillar function...')

    host_dir = os.path.join(root_dir, 'hosts', minion_id)
    if not os.path.exists(host_dir):
        # No data for host with this ID.
        return ngroup_pillar

    if not os.path.isdir(host_dir):
        log.error('"%s" exists, but not a directory', host_dir)
        return ngroup_pillar

    host_pillar = _construct_pillar(host_dir, follow_dir_links, raw_data)
    return _dict_merge(ngroup_pillar, host_pillar)

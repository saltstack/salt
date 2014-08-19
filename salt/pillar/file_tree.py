# -*- coding: utf-8 -*-

'''
Recursively iterate over directories and add all files as Pillar data.

Example configuration:

.. code-block:: yaml

    ext_pillar:
      - file_tree:
          root_dir: /path/to/root/directory
          follow_dir_links: False

The ``root_dir`` parameter is required and points to the directory where files
for each host are stored. The ``follow_dir_links`` paramater is optional
and defaults to False. If ``follow_dir_links`` is set to True, file_tree will
follow symbolic links to other directories. Be careful when using
``follow_dir_links``, the current implementation is dumb and will run into
infinite recursion if a recursive symlink chain exists in the root_dir!

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
'''
# TODO: Add git support.

# Import python libs
import logging
import os
import os.path

# Set up logging
log = logging.getLogger(__name__)


def _on_walk_error(err):
    '''
    Log os.walk() error.
    '''
    log.error('"%s": %s', err.filename, err.strerror)


def _construct_pillar(top_dir, follow_dir_links):
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
                pillar_node[file_name] = open(file_path, 'rb').read()
            except IOError as err:
                log.error('%s', str(err))
            except:
                log.error('Unknown exception while reading "%s"', file_path,
                          exc_info=True)

    return pillar


def ext_pillar(minion_id, pillar, root_dir=None, follow_dir_links=False):
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

    host_dir = os.path.join(root_dir, 'hosts', minion_id)
    if not os.path.exists(host_dir):
        # No data for host with this ID.
        return {}
    if not os.path.isdir(host_dir):
        log.error('"%s" exists, but not a directory', host_dir)
        return {}

    return _construct_pillar(host_dir, follow_dir_links)

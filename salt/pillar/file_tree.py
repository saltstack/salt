# -*- coding: utf-8 -*-
'''

``File_tree`` is an external pillar that allows
values from all files in a directory tree to be imported as Pillar data.

Note this is an external pillar, and is subject to the rules and constraints
governing external pillars detailed here: :ref:`external-pillars`.

.. versionadded:: 2015.5.0

Example Configuration
---------------------

.. code-block:: yaml

    ext_pillar:
      - file_tree:
          root_dir: /path/to/root/directory
          follow_dir_links: False
          keep_newline: True

The ``root_dir`` parameter is required and points to the directory where files
for each host are stored. The ``follow_dir_links`` parameter is optional and
defaults to False. If ``follow_dir_links`` is set to True, this external pillar
will follow symbolic links to other directories.

.. warning::
    Be careful when using ``follow_dir_links``, as a recursive symlink chain
    will result in unexpected results.

.. versionchanged:: 2018.3.0
    If ``root_dir`` is a relative path, it will be treated as relative to the
    :conf_master:`pillar_roots` of the environment specified by
    :conf_minion:`pillarenv`. If an environment specifies multiple
    roots, this module will search for files relative to all of them, in order,
    merging the results.

If ``keep_newline`` is set to ``True``, then the pillar values for files ending
in newlines will keep that newline. The default behavior is to remove the
end-of-file newline. ``keep_newline`` should be turned on if the pillar data is
intended to be used to deploy a file using ``contents_pillar`` with a
:py:func:`file.managed <salt.states.file.managed>` state.

.. versionchanged:: 2015.8.4
    The ``raw_data`` parameter has been renamed to ``keep_newline``. In earlier
    releases, ``raw_data`` must be used. Also, this parameter can now be a list
    of globs, allowing for more granular control over which pillar values keep
    their end-of-file newline. The globs match paths relative to the
    directories named for minion IDs and nodegroups underneath the ``root_dir``
    (see the layout examples in the below sections).

    .. code-block:: yaml

        ext_pillar:
          - file_tree:
              root_dir: /path/to/root/directory
              keep_newline:
                - files/testdir/*

.. note::
    In earlier releases, this documentation incorrectly stated that binary
    files would not affected by the ``keep_newline`` configuration.  However,
    this module does not actually distinguish between binary and text files.

.. versionchanged:: 2017.7.0
    Templating/rendering has been added. You can now specify a default render
    pipeline and a black- and whitelist of (dis)allowed renderers.

    ``template`` must be set to ``True`` for templating to happen.

    .. code-block:: yaml

        ext_pillar:
          - file_tree:
            root_dir: /path/to/root/directory
            render_default: jinja|yaml
            renderer_blacklist:
              - gpg
            renderer_whitelist:
              - jinja
              - yaml
            template: True

Assigning Pillar Data to Individual Hosts
-----------------------------------------

To configure pillar data for each host, this external pillar will recursively
iterate over ``root_dir``/hosts/``id`` (where ``id`` is a minion ID), and
compile pillar data with each subdirectory as a dictionary key and each file
as a value.

For example, the following ``root_dir`` tree:

.. code-block:: text

    ./hosts/
    ./hosts/test-host/
    ./hosts/test-host/files/
    ./hosts/test-host/files/testdir/
    ./hosts/test-host/files/testdir/file1.txt
    ./hosts/test-host/files/testdir/file2.txt
    ./hosts/test-host/files/another-testdir/
    ./hosts/test-host/files/another-testdir/symlink-to-file1.txt

will result in the following pillar tree for minion with ID ``test-host``:

.. code-block:: text

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

.. note::
    Subdirectories underneath ``root_dir``/hosts/``id`` become nested
    dictionaries, as shown above.


Assigning Pillar Data to Entire Nodegroups
------------------------------------------

To assign Pillar data to all minions in a given nodegroup, this external pillar
recursively iterates over ``root_dir``/nodegroups/``nodegroup`` (where
``nodegroup`` is the name of a nodegroup), and like for individual hosts,
compiles pillar data with each subdirectory as a dictionary key and each file
as a value.

.. important::
    If the same Pillar key is set for a minion both by nodegroup and by
    individual host, then the value set for the individual host will take
    precedence.

For example, the following ``root_dir`` tree:

.. code-block:: text

    ./nodegroups/
    ./nodegroups/test-group/
    ./nodegroups/test-group/files/
    ./nodegroups/test-group/files/testdir/
    ./nodegroups/test-group/files/testdir/file1.txt
    ./nodegroups/test-group/files/testdir/file2.txt
    ./nodegroups/test-group/files/another-testdir/
    ./nodegroups/test-group/files/another-testdir/symlink-to-file1.txt

will result in the following pillar data for minions in the node group
``test-group``:

.. code-block:: text

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
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import fnmatch
import logging
import os

# Import salt libs
import salt.loader
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.minions
import salt.utils.path
import salt.utils.stringio
import salt.template
from salt.ext import six

# Set up logging
log = logging.getLogger(__name__)


def _on_walk_error(err):
    '''
    Log salt.utils.path.os_walk() error.
    '''
    log.error('%s: %s', err.filename, err.strerror)


def _check_newline(prefix, file_name, keep_newline):
    '''
    Return a boolean stating whether or not a file's trailing newline should be
    removed. To figure this out, first check if keep_newline is a boolean and
    if so, return its opposite. Otherwise, iterate over keep_newline and check
    if any of the patterns match the file path. If a match is found, return
    False, otherwise return True.
    '''
    if isinstance(keep_newline, bool):
        return not keep_newline
    full_path = os.path.join(prefix, file_name)
    for pattern in keep_newline:
        try:
            if fnmatch.fnmatch(full_path, pattern):
                return False
        except TypeError:
            if fnmatch.fnmatch(full_path, six.text_type(pattern)):
                return False
    return True


def _construct_pillar(top_dir,
                      follow_dir_links,
                      keep_newline=False,
                      render_default=None,
                      renderer_blacklist=None,
                      renderer_whitelist=None,
                      template=False):
    '''
    Construct pillar from file tree.
    '''
    pillar = {}
    renderers = salt.loader.render(__opts__, __salt__)

    norm_top_dir = os.path.normpath(top_dir)
    for dir_path, dir_names, file_names in salt.utils.path.os_walk(
            top_dir, topdown=True, onerror=_on_walk_error,
            followlinks=follow_dir_links):
        # Find current path in pillar tree
        pillar_node = pillar
        norm_dir_path = os.path.normpath(dir_path)
        prefix = os.path.relpath(norm_dir_path, norm_top_dir)
        if norm_dir_path != norm_top_dir:
            path_parts = []
            head = prefix
            while head:
                head, tail = os.path.split(head)
                path_parts.insert(0, tail)
            while path_parts:
                pillar_node = pillar_node[path_parts.pop(0)]

        # Create dicts for subdirectories
        for dir_name in dir_names:
            pillar_node[dir_name] = {}

        # Add files
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            if not os.path.isfile(file_path):
                log.error('file_tree: %s: not a regular file', file_path)
                continue

            contents = b''
            try:
                with salt.utils.files.fopen(file_path, 'rb') as fhr:
                    buf = fhr.read(__opts__['file_buffer_size'])
                    while buf:
                        contents += buf
                        buf = fhr.read(__opts__['file_buffer_size'])
                    if contents.endswith(b'\n') \
                            and _check_newline(prefix,
                                               file_name,
                                               keep_newline):
                        contents = contents[:-1]
            except (IOError, OSError) as exc:
                log.error('file_tree: Error reading %s: %s',
                          file_path,
                          exc.strerror)
            else:
                data = contents
                if template is True:
                    data = salt.template.compile_template_str(template=contents,
                                                              renderers=renderers,
                                                              default=render_default,
                                                              blacklist=renderer_blacklist,
                                                              whitelist=renderer_whitelist)
                if salt.utils.stringio.is_readable(data):
                    pillar_node[file_name] = data.getvalue()
                else:
                    pillar_node[file_name] = data

    return pillar


def ext_pillar(minion_id,
               pillar,
               root_dir=None,
               follow_dir_links=False,
               debug=False,
               keep_newline=False,
               render_default=None,
               renderer_blacklist=None,
               renderer_whitelist=None,
               template=False):
    '''
    Compile pillar data for the specified minion ID
    '''
    # Not used
    del pillar

    if not root_dir:
        log.error('file_tree: no root_dir specified')
        return {}

    if not os.path.isabs(root_dir):
        pillarenv = __opts__['pillarenv']
        if pillarenv is None:
            log.error('file_tree: root_dir is relative but pillarenv is not set')
            return {}
        log.debug('file_tree: pillarenv = %s', pillarenv)

        env_roots = __opts__['pillar_roots'].get(pillarenv, None)
        if env_roots is None:
            log.error('file_tree: root_dir is relative but no pillar_roots are specified '
                      ' for pillarenv %s', pillarenv)
            return {}

        env_dirs = []
        for env_root in env_roots:
            env_dir = os.path.normpath(os.path.join(env_root, root_dir))
            # don't redundantly load consecutively, but preserve any expected precedence
            if env_dir not in env_dirs or env_dir != env_dirs[-1]:
                env_dirs.append(env_dir)
        dirs = env_dirs
    else:
        dirs = [root_dir]

    result_pillar = {}
    for root in dirs:
        dir_pillar = _ext_pillar(minion_id,
                                 root,
                                 follow_dir_links,
                                 debug,
                                 keep_newline,
                                 render_default,
                                 renderer_blacklist,
                                 renderer_whitelist,
                                 template)
        result_pillar = salt.utils.dictupdate.merge(result_pillar,
                                                    dir_pillar,
                                                    strategy='recurse')
    return result_pillar


def _ext_pillar(minion_id,
                root_dir,
                follow_dir_links,
                debug,
                keep_newline,
                render_default,
                renderer_blacklist,
                renderer_whitelist,
                template):
    '''
    Compile pillar data for a single root_dir for the specified minion ID
    '''
    log.debug('file_tree: reading %s', root_dir)

    if not os.path.isdir(root_dir):
        log.error(
            'file_tree: root_dir %s does not exist or is not a directory',
            root_dir
        )
        return {}

    if not isinstance(keep_newline, (bool, list)):
        log.error(
            'file_tree: keep_newline must be either True/False or a list '
            'of file globs. Skipping this ext_pillar for root_dir %s',
            root_dir
        )
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
                    _res = ckminions.check_minions(
                        master_ngroups[nodegroup],
                        'compound')
                    match = _res['minions']
                    if minion_id in match:
                        ngroup_dir = os.path.join(
                            nodegroups_dir, six.text_type(nodegroup))
                        ngroup_pillar = salt.utils.dictupdate.merge(ngroup_pillar,
                            _construct_pillar(ngroup_dir,
                                              follow_dir_links,
                                              keep_newline,
                                              render_default,
                                              renderer_blacklist,
                                              renderer_whitelist,
                                              template),
                            strategy='recurse'
                        )
        else:
            if debug is True:
                log.debug(
                    'file_tree: no nodegroups found in file tree directory '
                    'ext_pillar_dirs, skipping...'
                )
    else:
        if debug is True:
            log.debug('file_tree: no nodegroups found in master configuration')

    host_dir = os.path.join(root_dir, 'hosts', minion_id)
    if not os.path.exists(host_dir):
        # No data for host with this ID
        return ngroup_pillar

    if not os.path.isdir(host_dir):
        log.error('file_tree: %s exists, but is not a directory', host_dir)
        return ngroup_pillar

    host_pillar = _construct_pillar(host_dir,
                                    follow_dir_links,
                                    keep_newline,
                                    render_default,
                                    renderer_blacklist,
                                    renderer_whitelist,
                                    template)
    return salt.utils.dictupdate.merge(ngroup_pillar,
                                       host_pillar,
                                       strategy='recurse')

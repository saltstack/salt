# -*- coding: utf-8 -*-
'''
The ``file_tree`` external pillar allows values from all files in a directory
tree to be imported as Pillar data.

.. note::

    This is an external pillar and is subject to the :ref:`rules and
    constraints <external-pillars>` governing external pillars.

.. versionadded:: 2015.5.0

In this pillar, data is organized by either Minion ID or Nodegroup name.  To
setup pillar data for a specific Minion, place it in
``<root_dir>/hosts/<minion_id>``.  To setup pillar data for an entire
Nodegroup, place it in ``<root_dir>/nodegroups/<node_group>`` where
``<node_group>`` is the Nodegroup's name.

Example ``file_tree`` Pillar
============================

Master Configuration
--------------------

.. code-block:: yaml

    ext_pillar:
      - file_tree:
          root_dir: /srv/ext_pillar
          follow_dir_links: False
          keep_newline: True

    node_groups:
      internal_servers: 'L@bob,stuart,kevin'

Pillar Configuration
--------------------

.. code-block:: bash

    (salt-master) # tree /srv/ext_pillar
    /srv/ext_pillar/
    |-- hosts
    |   |-- bob
    |   |   |-- apache
    |   |   |   `-- config.d
    |   |   |       |-- 00_important.conf
    |   |   |       `-- 20_bob_extra.conf
    |   |   `-- corporate_app
    |   |       `-- settings
    |   |           `-- bob_settings.cfg
    |   `-- kevin
    |       |-- apache
    |       |   `-- config.d
    |       |       `-- 00_important.conf
    |       `-- corporate_app
    |           `-- settings
    |               `-- kevin_settings.cfg
    `-- nodegroups
        `-- internal_servers
            `-- corporate_app
                `-- settings
                    `-- common_settings.cfg

Verify Pillar Data
------------------

.. code-block:: bash

    (salt-master) # salt bob pillar.items
    bob:
        ----------
        apache:
            ----------
            config.d:
                ----------
                00_important.conf:
                    <important_config important_setting="yes" />
                20_bob_extra.conf:
                    <bob_specific_cfg has_freeze_ray="yes" />
        corporate_app:
            ----------
            settings:
                ----------
                common_settings:
                    // This is the main settings file for the corporate
                    // internal web app
                    main_setting: probably
                bob_settings:
                    role: bob

.. note::

    The leaf data in the example shown is the contents of the pillar files.
'''
from __future__ import absolute_import

# Import python libs
import fnmatch
import logging
import os

# Import salt libs
import salt.loader
import salt.utils
import salt.utils.dictupdate
import salt.utils.minions
import salt.utils.stringio
import salt.template

# Set up logging
log = logging.getLogger(__name__)


def _on_walk_error(err):
    '''
    Log os.walk() error.
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
            if fnmatch.fnmatch(full_path, str(pattern)):
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
    for dir_path, dir_names, file_names in os.walk(
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

            contents = ''
            try:
                with salt.utils.fopen(file_path, 'rb') as fhr:
                    buf = fhr.read(__opts__['file_buffer_size'])
                    while buf:
                        contents += buf
                        buf = fhr.read(__opts__['file_buffer_size'])
                    if contents.endswith('\n') \
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
    Compile pillar data from the given ``root_dir`` specific to Nodegroup names
    and Minion IDs.

    If a Minion's ID is not found at ``<root_dir>/host/<minion_id>`` or if it
    is not included in any Nodegroups named at
    ``<root_dir>/nodegroups/<node_group>``, no pillar data provided by this
    pillar module will be available for that Minion.

    .. versionchanged:: 2017.7.0
        Templating/rendering has been added. You can now specify a default
        render pipeline and a black- and whitelist of (dis)allowed renderers.

        :param:`template` must be set to ``True`` for templating to happen.

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

    :param minion_id:
        The ID of the Minion whose pillar data is to be collected

    :param pillar:
        Unused by the ``file_tree`` pillar module

    :param root_dir:
        Filesystem directory used as the root for pillar data (e.g.
        ``/srv/ext_pillar``)

    :param follow_dir_links:
        Follow symbolic links to directories while collecting pillar files.
        Defaults to ``False``.

        .. warning::

            Care should be exercised when enabling this option as it will
            follow links that point outside of :param:`root_dir`.

        .. warning::

            Symbolic links that lead to infinite recursion are not filtered.

    :param debug:
        Enable debug information at log level ``debug``.  Defaults to
        ``False``.  This option may be useful to help debug errors when setting
        up the ``file_tree`` pillar module.

    :param keep_newline:
        Preserve the end-of-file newline in files.  Defaults to ``False``.
        This option may either be a boolean or a list of file globs (as defined
        by the `Python fnmatch package
        <https://docs.python.org/library/fnmatch.html>`_) for which end-of-file
        newlines are to be kept.

        ``keep_newline`` should be turned on if the pillar data is intended to
        be used to deploy a file using ``contents_pillar`` with a
        :py:func:`file.managed <salt.states.file.managed>` state.

        .. versionchanged:: 2015.8.4
            The ``raw_data`` parameter has been renamed to ``keep_newline``. In
            earlier releases, ``raw_data`` must be used. Also, this parameter
            can now be a list of globs, allowing for more granular control over
            which pillar values keep their end-of-file newline. The globs match
            paths relative to the directories named for Minion IDs and
            Nodegroup namess underneath the :param:`root_dir`.

            .. code-block:: yaml

                ext_pillar:
                  - file_tree:
                      root_dir: /srv/ext_pillar
                      keep_newline:
                        - apache/config.d/*
                        - corporate_app/settings/*

        .. note::
            In earlier releases, this documentation incorrectly stated that
            binary files would not affected by the ``keep_newline``.  However,
            this module does not actually distinguish between binary and text
            files.


    :param render_default:
        Override Salt's :conf_master:`default global renderer <renderer>` for
        the ``file_tree`` pillar.

        .. code-block:: yaml

            render_default: jinja

    :param renderer_blacklist:
        Disallow renderers for pillar files.

        .. code-block:: yaml

            renderer_blacklist:
              - json

    :param renderer_whitelist:
        Allow renderers for pillar files.

        .. code-block:: yaml

            renderer_whitelist:
              - yaml
              - jinja

    :param template:
        Enable templating of pillar files.  Defaults to ``False``.
    '''
    # Not used
    del pillar

    if not root_dir:
        log.error('file_tree: no root_dir specified')
        return {}

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
    if os.path.exists(nodegroups_dir) and len(__opts__.get('nodegroups', ())) > 0:
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
                            _construct_pillar(ngroup_dir,
                                              follow_dir_links,
                                              keep_newline,
                                              render_default,
                                              renderer_blacklist,
                                              renderer_whitelist,
                                              template)
                        )
        else:
            if debug is True:
                log.debug(
                    'file_tree: no nodegroups found in file tree directory %s, skipping...',
                    ext_pillar_dirs
                )
    else:
        if debug is True:
            log.debug('file_tree: no nodegroups found in master configuration')

    host_dir = os.path.join(root_dir, 'hosts', minion_id)
    if not os.path.exists(host_dir):
        if debug is True:
            log.debug(
                'file_tree: no pillar data for minion %s found in file tree directory %s',
                minion_id,
                host_dir
            )
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

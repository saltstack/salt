"""
Network Config
==============

Manage the configuration on a network device given a specific static config or template.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`Network-related basic features execution module <salt.modules.napalm_network>`

.. versionadded:: 2017.7.0
"""

import logging

import salt.utils.napalm

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "netconfig"

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _update_config(
    template_name,
    template_source=None,
    template_hash=None,
    template_hash_name=None,
    template_user="root",
    template_group="root",
    template_mode="755",
    template_attrs="--------------e----",
    saltenv=None,
    template_engine="jinja",
    skip_verify=False,
    defaults=None,
    test=False,
    commit=True,
    debug=False,
    replace=False,
    **template_vars,
):
    """
    Call the necessary functions in order to execute the state.
    For the moment this only calls the ``net.load_template`` function from the
    :mod:`Network-related basic features execution module <salt.modules.napalm_network>`, but this may change in time.
    """

    return __salt__["net.load_template"](
        template_name,
        template_source=template_source,
        template_hash=template_hash,
        template_hash_name=template_hash_name,
        template_user=template_user,
        template_group=template_group,
        template_mode=template_mode,
        template_attrs=template_attrs,
        saltenv=saltenv,
        template_engine=template_engine,
        skip_verify=skip_verify,
        defaults=defaults,
        test=test,
        commit=commit,
        debug=debug,
        replace=replace,
        **template_vars,
    )


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def replace_pattern(
    name,
    pattern,
    repl,
    count=0,
    flags=8,
    bufsize=1,
    append_if_not_found=False,
    prepend_if_not_found=False,
    not_found_content=None,
    search_only=False,
    show_changes=True,
    backslash_literal=False,
    source="running",
    path=None,
    test=False,
    replace=True,
    debug=False,
    commit=True,
):
    """
    .. versionadded:: 2019.2.0

    Replace occurrences of a pattern in the configuration source. If
    ``show_changes`` is ``True``, then a diff of what changed will be returned,
    otherwise a ``True`` will be returned when changes are made, and ``False``
    when no changes are made.
    This is a pure Python implementation that wraps Python's :py:func:`~re.sub`.

    pattern
        A regular expression, to be matched using Python's
        :py:func:`~re.search`.

    repl
        The replacement text.

    count: ``0``
        Maximum number of pattern occurrences to be replaced. If count is a
        positive integer ``n``, only ``n`` occurrences will be replaced,
        otherwise all occurrences will be replaced.

    flags (list or int): ``8``
        A list of flags defined in the ``re`` module documentation from the
        Python standard library. Each list item should be a string that will
        correlate to the human-friendly flag name. E.g., ``['IGNORECASE',
        'MULTILINE']``. Optionally, ``flags`` may be an int, with a value
        corresponding to the XOR (``|``) of all the desired flags. Defaults to
        8 (which supports 'MULTILINE').

    bufsize (int or str): ``1``
        How much of the configuration to buffer into memory at once. The
        default value ``1`` processes one line at a time. The special value
        ``file`` may be specified which will read the entire file into memory
        before processing.

    append_if_not_found: ``False``
        If set to ``True``, and pattern is not found, then the content will be
        appended to the file.

    prepend_if_not_found: ``False``
        If set to ``True`` and pattern is not found, then the content will be
        prepended to the file.

    not_found_content
        Content to use for append/prepend if not found. If None (default), uses
        ``repl``. Useful when ``repl`` uses references to group in pattern.

    search_only: ``False``
        If set to true, this no changes will be performed on the file, and this
        function will simply return ``True`` if the pattern was matched, and
        ``False`` if not.

    show_changes: ``True``
        If ``True``, return a diff of changes made. Otherwise, return ``True``
        if changes were made, and ``False`` if not.

    backslash_literal: ``False``
        Interpret backslashes as literal backslashes for the repl and not
        escape characters.  This will help when using append/prepend so that
        the backslashes are not interpreted for the repl on the second run of
        the state.

    source: ``running``
        The configuration source. Choose from: ``running``, ``candidate``, or
        ``startup``. Default: ``running``.

    path
        Save the temporary configuration to a specific path, then read from
        there.

    test: ``False``
        Dry run? If set as ``True``, will apply the config, discard and return
        the changes. Default: ``False`` and will commit the changes on the
        device.

    commit: ``True``
        Commit the configuration changes? Default: ``True``.

    debug: ``False``
        Debug mode. Will insert a new key in the output dictionary, as
        ``loaded_config`` containing the raw configuration loaded on the device.

    replace: ``True``
        Load and replace the configuration. Default: ``True``.

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    State SLS Example:

    .. code-block:: yaml

        update_policy_name:
          netconfig.replace_pattern:
            - pattern: OLD-POLICY-NAME
            - repl: new-policy-name
            - debug: true
    """
    ret = salt.utils.napalm.default_ret(name)
    # the user can override the flags the equivalent CLI args
    # which have higher precedence
    test = test or __opts__["test"]
    debug = __salt__["config.merge"]("debug", debug)
    commit = __salt__["config.merge"]("commit", commit)
    replace = __salt__["config.merge"]("replace", replace)  # this might be a bit risky
    replace_ret = __salt__["net.replace_pattern"](
        pattern,
        repl,
        count=count,
        flags=flags,
        bufsize=bufsize,
        append_if_not_found=append_if_not_found,
        prepend_if_not_found=prepend_if_not_found,
        not_found_content=not_found_content,
        search_only=search_only,
        show_changes=show_changes,
        backslash_literal=backslash_literal,
        source=source,
        path=path,
        test=test,
        replace=replace,
        debug=debug,
        commit=commit,
    )
    return salt.utils.napalm.loaded_ret(ret, replace_ret, test, debug)


def saved(
    name,
    source="running",
    user=None,
    group=None,
    mode=None,
    attrs=None,
    makedirs=False,
    dir_mode=None,
    replace=True,
    backup="",
    show_changes=True,
    create=True,
    tmp_dir="",
    tmp_ext="",
    encoding=None,
    encoding_errors="strict",
    allow_empty=False,
    follow_symlinks=True,
    check_cmd=None,
    win_owner=None,
    win_perms=None,
    win_deny_perms=None,
    win_inheritance=True,
    win_perms_reset=False,
    **kwargs,
):
    """
    .. versionadded:: 2019.2.0

    Save the configuration to a file on the local file system.

    name
        Absolute path to file where to save the configuration.
        To push the files to the Master, use
        :mod:`cp.push <salt.modules.cp.push>` Execution function.

    source: ``running``
        The configuration source. Choose from: ``running``, ``candidate``,
        ``startup``. Default: ``running``.

    user
        The user to own the file, this defaults to the user salt is running as
        on the minion

    group
        The group ownership set for the file, this defaults to the group salt
        is running as on the minion. On Windows, this is ignored

    mode
        The permissions to set on this file, e.g. ``644``, ``0775``, or
        ``4664``.
        The default mode for new files and directories corresponds to the
        umask of the salt process. The mode of existing files and directories
        will only be changed if ``mode`` is specified.

        .. note::
            This option is **not** supported on Windows.
    attrs
        The attributes to have on this file, e.g. ``a``, ``i``. The attributes
        can be any or a combination of the following characters:
        ``aAcCdDeijPsStTu``.

        .. note::
            This option is **not** supported on Windows.

    makedirs: ``False``
        If set to ``True``, then the parent directories will be created to
        facilitate the creation of the named file. If ``False``, and the parent
        directory of the destination file doesn't exist, the state will fail.

    dir_mode
        If directories are to be created, passing this option specifies the
        permissions for those directories. If this is not set, directories
        will be assigned permissions by adding the execute bit to the mode of
        the files.

        The default mode for new files and directories corresponds umask of salt
        process. For existing files and directories it's not enforced.

    replace: ``True``
        If set to ``False`` and the file already exists, the file will not be
        modified even if changes would otherwise be made. Permissions and
        ownership will still be enforced, however.

    backup
        Overrides the default backup mode for this specific file. See
        :ref:`backup_mode documentation <file-state-backups>` for more details.

    show_changes: ``True``
        Output a unified diff of the old file and the new file. If ``False``
        return a boolean if any changes were made.

    create: ``True``
        If set to ``False``, then the file will only be managed if the file
        already exists on the system.

    encoding
        If specified, then the specified encoding will be used. Otherwise, the
        file will be encoded using the system locale (usually UTF-8). See
        https://docs.python.org/3/library/codecs.html#standard-encodings for
        the list of available encodings.

    encoding_errors: ``'strict'``
        Error encoding scheme. Default is ```'strict'```.
        See https://docs.python.org/2/library/codecs.html#codec-base-classes
        for the list of available schemes.

    allow_empty: ``True``
        If set to ``False``, then the state will fail if the contents specified
        by ``contents_pillar`` or ``contents_grains`` are empty.

    follow_symlinks: ``True``
        If the desired path is a symlink follow it and make changes to the
        file to which the symlink points.

    check_cmd
        The specified command will be run with an appended argument of a
        *temporary* file containing the new managed contents.  If the command
        exits with a zero status the new managed contents will be written to
        the managed destination. If the command exits with a nonzero exit
        code, the state will fail and no changes will be made to the file.

    tmp_dir
        Directory for temp file created by ``check_cmd``. Useful for checkers
        dependent on config file location (e.g. daemons restricted to their
        own config directories by an apparmor profile).

    tmp_ext
        Suffix for temp file created by ``check_cmd``. Useful for checkers
        dependent on config file extension (e.g. the init-checkconf upstart
        config checker).

    win_owner: ``None``
        The owner of the directory. If this is not passed, user will be used. If
        user is not passed, the account under which Salt is running will be
        used.

    win_perms: ``None``
        A dictionary containing permissions to grant and their propagation. For
        example: ``{'Administrators': {'perms': 'full_control'}}`` Can be a
        single basic perm or a list of advanced perms. ``perms`` must be
        specified. ``applies_to`` does not apply to file objects.

    win_deny_perms: ``None``
        A dictionary containing permissions to deny and their propagation. For
        example: ``{'Administrators': {'perms': 'full_control'}}`` Can be a
        single basic perm or a list of advanced perms. ``perms`` must be
        specified. ``applies_to`` does not apply to file objects.

    win_inheritance: ``True``
        True to inherit permissions from the parent directory, False not to
        inherit permission.

    win_perms_reset: ``False``
        If ``True`` the existing DACL will be cleared and replaced with the
        settings defined in this function. If ``False``, new entries will be
        appended to the existing DACL. Default is ``False``.

    State SLS Example:

    .. code-block:: yaml

        /var/backups/{{ opts.id }}/{{ salt.status.time('%s') }}.cfg:
          netconfig.saved:
            - source: running
            - makedirs: true

    The state SLS  above would create a backup config grouping the files by the
    Minion ID, in chronological files. For example, if the state is executed at
    on the 3rd of August 2018, at 5:15PM, on the Minion ``core1.lon01``, the
    configuration would saved in the file:
    ``/var/backups/core01.lon01/1533316558.cfg``
    """
    ret = __salt__["net.config"](source=source)
    if not ret["result"]:
        return {"name": name, "changes": {}, "result": False, "comment": ret["comment"]}
    return __states__["file.managed"](
        name,
        user=user,
        group=group,
        mode=mode,
        attrs=attrs,
        makedirs=makedirs,
        dir_mode=dir_mode,
        replace=replace,
        backup=backup,
        show_changes=show_changes,
        create=create,
        contents=ret["out"][source],
        tmp_dir=tmp_dir,
        tmp_ext=tmp_ext,
        encoding=encoding,
        encoding_errors=encoding_errors,
        allow_empty=allow_empty,
        follow_symlinks=follow_symlinks,
        check_cmd=check_cmd,
        win_owner=win_owner,
        win_perms=win_perms,
        win_deny_perms=win_deny_perms,
        win_inheritance=win_inheritance,
        win_perms_reset=win_perms_reset,
        **kwargs,
    )


def managed(
    name,
    template_name=None,
    template_source=None,
    template_hash=None,
    template_hash_name=None,
    saltenv="base",
    template_engine="jinja",
    skip_verify=False,
    context=None,
    defaults=None,
    test=False,
    commit=True,
    debug=False,
    replace=False,
    commit_in=None,
    commit_at=None,
    revert_in=None,
    revert_at=None,
    **template_vars,
):
    """
    Manages the configuration on network devices.

    By default this state will commit the changes on the device. If there are no changes required, it does not commit
    and the field ``already_configured`` from the output dictionary will be set as ``True`` to notify that.

    To avoid committing the configuration, set the argument ``test`` to ``True`` (or via the CLI argument ``test=True``)
    and will discard (dry run).

    To preserve the changes, set ``commit`` to ``False`` (either as CLI argument, either as state parameter).
    However, this is recommended to be used only in exceptional cases when there are applied few consecutive states
    and/or configuration changes. Otherwise the user might forget that the config DB is locked and the candidate config
    buffer is not cleared/merged in the running config.

    To replace the config, set ``replace`` to ``True``. This option is recommended to be used with caution!

    template_name
        Identifies path to the template source. The template can be either stored on the local machine,
        either remotely.
        The recommended location is under the ``file_roots`` as specified in the master config file.
        For example, let's suppose the ``file_roots`` is configured as:

        .. code-block:: yaml

            file_roots:
              base:
                 - /etc/salt/states

        Placing the template under ``/etc/salt/states/templates/example.jinja``, it can be used as
        ``salt://templates/example.jinja``.
        Alternatively, for local files, the user can specify the absolute path.
        If remotely, the source can be retrieved via ``http``, ``https`` or ``ftp``.

        Examples:

        - ``salt://my_template.jinja``
        - ``/absolute/path/to/my_template.jinja``
        - ``http://example.com/template.cheetah``
        - ``https:/example.com/template.mako``
        - ``ftp://example.com/template.py``

        .. versionchanged:: 2019.2.0
            This argument can now support a list of templates to be rendered.
            The resulting configuration text is loaded at once, as a single
            configuration chunk.

    template_source: None
        Inline config template to be rendered and loaded on the device.

    template_hash: None
        Hash of the template file. Format: ``{hash_type: 'md5', 'hsum': <md5sum>}``

    template_hash_name: None
        When ``template_hash`` refers to a remote file, this specifies the filename to look for in that file.

    saltenv: base
        Specifies the template environment. This will influence the relative imports inside the templates.

    template_engine: jinja
        The following templates engines are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    skip_verify: False
        If ``True``, hash verification of remote file sources (``http://``, ``https://``, ``ftp://``) will be skipped,
        and the ``source_hash`` argument will be ignored.

        .. versionchanged:: 2017.7.1

    test: False
        Dry run? If set to ``True``, will apply the config, discard and return the changes. Default: ``False``
        (will commit the changes on the device).

    commit: True
        Commit? Default: ``True``.

    debug: False
        Debug mode. Will insert a new key under the output dictionary, as ``loaded_config`` containing the raw
        result after the template was rendered.

        .. note::
            This argument cannot be used directly on the command line. Instead,
            it can be passed through the ``pillar`` variable when executing
            either of the :py:func:`state.sls <salt.modules.state.sls>` or
            :py:func:`state.apply <salt.modules.state.apply>` (see below for an
            example).

    commit_in: ``None``
        Commit the changes in a specific number of minutes / hours. Example of
        accepted formats: ``5`` (commit in 5 minutes), ``2m`` (commit in 2
        minutes), ``1h`` (commit the changes in 1 hour)`, ``5h30m`` (commit
        the changes in 5 hours and 30 minutes).

        .. note::
            This feature works on any platforms, as it does not rely on the
            native features of the network operating system.

        .. note::
            After the command is executed and the ``diff`` is not satisfactory,
            or for any other reasons you have to discard the commit, you are
            able to do so using the
            :py:func:`net.cancel_commit <salt.modules.napalm_network.cancel_commit>`
            execution function, using the commit ID returned by this function.

        .. warning::
            Using this feature, Salt will load the exact configuration you
            expect, however the diff may change in time (i.e., if an user
            applies a manual configuration change, or a different process or
            command changes the configuration in the meanwhile).

        .. versionadded:: 2019.2.0

    commit_at: ``None``
        Commit the changes at a specific time. Example of accepted formats:
        ``1am`` (will commit the changes at the next 1AM), ``13:20`` (will
        commit at 13:20), ``1:20am``, etc.

        .. note::
            This feature works on any platforms, as it does not rely on the
            native features of the network operating system.

        .. note::
            After the command is executed and the ``diff`` is not satisfactory,
            or for any other reasons you have to discard the commit, you are
            able to do so using the
            :py:func:`net.cancel_commit <salt.modules.napalm_network.cancel_commit>`
            execution function, using the commit ID returned by this function.

        .. warning::
            Using this feature, Salt will load the exact configuration you
            expect, however the diff may change in time (i.e., if an user
            applies a manual configuration change, or a different process or
            command changes the configuration in the meanwhile).

        .. versionadded:: 2019.2.0

    revert_in: ``None``
        Commit and revert the changes in a specific number of minutes / hours.
        Example of accepted formats: ``5`` (revert in 5 minutes), ``2m`` (revert
        in 2 minutes), ``1h`` (revert the changes in 1 hour)`, ``5h30m`` (revert
        the changes in 5 hours and 30 minutes).

        .. note::
            To confirm the commit, and prevent reverting the changes, you will
            have to execute the
            :mod:`net.confirm_commit <salt.modules.napalm_network.confirm_commit>`
            function, using the commit ID returned by this function.

        .. warning::
            This works on any platform, regardless if they have or don't have
            native capabilities to confirming a commit. However, please be
            *very* cautious when using this feature: on Junos (as it is the only
            NAPALM core platform supporting this natively) it executes a commit
            confirmed as you would do from the command line.
            All the other platforms don't have this capability natively,
            therefore the revert is done via Salt. That means, your device needs
            to be reachable at the moment when Salt will attempt to revert your
            changes. Be cautious when pushing configuration changes that would
            prevent you reach the device.

            Similarly, if an user or a different process apply other
            configuration changes in the meanwhile (between the moment you
            commit and till the changes are reverted), these changes would be
            equally reverted, as Salt cannot be aware of them.

        .. versionadded:: 2019.2.0

    revert_at: ``None``
        Commit and revert the changes at a specific time. Example of accepted
        formats: ``1am`` (will commit and revert the changes at the next 1AM),
        ``13:20`` (will commit and revert at 13:20), ``1:20am``, etc.

        .. note::
            To confirm the commit, and prevent reverting the changes, you will
            have to execute the
            :mod:`net.confirm_commit <salt.modules.napalm_network.confirm_commit>`
            function, using the commit ID returned by this function.

        .. warning::
            This works on any platform, regardless if they have or don't have
            native capabilities to confirming a commit. However, please be
            *very* cautious when using this feature: on Junos (as it is the only
            NAPALM core platform supporting this natively) it executes a commit
            confirmed as you would do from the command line.
            All the other platforms don't have this capability natively,
            therefore the revert is done via Salt. That means, your device needs
            to be reachable at the moment when Salt will attempt to revert your
            changes. Be cautious when pushing configuration changes that would
            prevent you reach the device.

            Similarly, if an user or a different process apply other
            configuration changes in the meanwhile (between the moment you
            commit and till the changes are reverted), these changes would be
            equally reverted, as Salt cannot be aware of them.

        .. versionadded:: 2019.2.0

    replace: False
        Load and replace the configuration. Default: ``False`` (will apply load merge).

    context: None
        Overrides default context variables passed to the template.

        .. versionadded:: 2019.2.0

    defaults: None
        Default variables/context passed to the template.

    template_vars
        Dictionary with the arguments/context to be used when the template is rendered. Do not explicitly specify this
        argument. This represents any other variable that will be sent to the template rendering system. Please
        see an example below! In both ``ntp_peers_example_using_pillar`` and ``ntp_peers_example``, ``peers`` is sent as
        template variable.

        .. note::
            It is more recommended to use the ``context`` argument instead, to
            avoid any conflicts with other arguments.

    SLS Example (e.g.: under salt://router/config.sls) :

    .. code-block:: yaml

        whole_config_example:
            netconfig.managed:
                - template_name: salt://path/to/complete_config.jinja
                - debug: True
                - replace: True
        bgp_config_example:
            netconfig.managed:
                - template_name: /absolute/path/to/bgp_neighbors.mako
                - template_engine: mako
        prefix_lists_example:
            netconfig.managed:
                - template_name: prefix_lists.cheetah
                - debug: True
                - template_engine: cheetah
        ntp_peers_example:
            netconfig.managed:
                - template_name: http://bit.ly/2gKOj20
                - skip_verify: False
                - debug: True
                - peers:
                    - 192.168.0.1
                    - 192.168.0.1
        ntp_peers_example_using_pillar:
            netconfig.managed:
                - template_name: http://bit.ly/2gKOj20
                - peers: {{ pillar.get('ntp.peers', []) }}

    Multi template example:

    .. code-block:: yaml

        hostname_and_ntp:
          netconfig.managed:
            - template_name:
                - https://bit.ly/2OhSgqP
                - https://bit.ly/2M6C4Lx
                - https://bit.ly/2OIWVTs
            - debug: true
            - context:
                hostname: {{ opts.id }}
                servers:
                  - 172.17.17.1
                  - 172.17.17.2
                peers:
                  - 192.168.0.1
                  - 192.168.0.2

    Usage examples:

    .. code-block:: bash

        $ sudo salt 'juniper.device' state.sls router.config test=True

        $ sudo salt -N all-routers state.sls router.config pillar="{'debug': True}"

    ``router.config`` depends on the location of the SLS file (see above). Running this command, will be executed all
    five steps from above. These examples above are not meant to be used in a production environment, their sole purpose
    is to provide usage examples.

    Output example:

    .. code-block:: bash

        $ sudo salt 'juniper.device' state.sls router.config test=True
        juniper.device:
        ----------
                  ID: ntp_peers_example_using_pillar
            Function: netconfig.managed
              Result: None
             Comment: Testing mode: Configuration discarded.
             Started: 12:01:40.744535
            Duration: 8755.788 ms
             Changes:
                      ----------
                      diff:
                          [edit system ntp]
                               peer 192.168.0.1 { ... }
                          +    peer 172.17.17.1;
                          +    peer 172.17.17.3;

        Summary for juniper.device
        ------------
        Succeeded: 1 (unchanged=1, changed=1)
        Failed:    0
        ------------
        Total states run:     1
        Total run time:   8.756 s

    Raw output example (useful when the output is reused in other states/execution modules):

    .. code-block:: bash

        $ sudo salt --out=pprint 'juniper.device' state.sls router.config test=True debug=True

    .. code-block:: python

        {
            'juniper.device': {
                'netconfig_|-ntp_peers_example_using_pillar_|-ntp_peers_example_using_pillar_|-managed': {
                    '__id__': 'ntp_peers_example_using_pillar',
                    '__run_num__': 0,
                    'already_configured': False,
                    'changes': {
                        'diff': '[edit system ntp]   peer 192.168.0.1 { ... }+   peer 172.17.17.1;+   peer 172.17.17.3;'
                    },
                    'comment': 'Testing mode: Configuration discarded.',
                    'duration': 7400.759,
                    'loaded_config': 'system {  ntp {  peer 172.17.17.1;  peer 172.17.17.3; } }',
                    'name': 'ntp_peers_example_using_pillar',
                    'result': None,
                    'start_time': '12:09:09.811445'
                }
            }
        }
    """
    ret = salt.utils.napalm.default_ret(name)

    # the user can override the flags the equivalent CLI args
    # which have higher precedence
    test = test or __opts__["test"]
    debug = __salt__["config.merge"]("debug", debug)
    commit = __salt__["config.merge"]("commit", commit)
    replace = __salt__["config.merge"]("replace", replace)  # this might be a bit risky
    skip_verify = __salt__["config.merge"]("skip_verify", skip_verify)
    commit_in = __salt__["config.merge"]("commit_in", commit_in)
    commit_at = __salt__["config.merge"]("commit_at", commit_at)
    revert_in = __salt__["config.merge"]("revert_in", revert_in)
    revert_at = __salt__["config.merge"]("revert_at", revert_at)

    config_update_ret = _update_config(
        template_name=template_name,
        template_source=template_source,
        template_hash=template_hash,
        template_hash_name=template_hash_name,
        saltenv=saltenv,
        template_engine=template_engine,
        skip_verify=skip_verify,
        context=context,
        defaults=defaults,
        test=test,
        commit=commit,
        commit_in=commit_in,
        commit_at=commit_at,
        revert_in=revert_in,
        revert_at=revert_at,
        debug=debug,
        replace=replace,
        **template_vars,
    )

    return salt.utils.napalm.loaded_ret(ret, config_update_ret, test, debug)


def commit_cancelled(name):
    """
    .. versionadded:: 2019.2.0

    Cancel a commit scheduled to be executed via the ``commit_in`` and
    ``commit_at`` arguments from the
    :py:func:`net.load_template <salt.modules.napalm_network.load_template>` or
    :py:func:`net.load_config <salt.modules.napalm_network.load_config>`
    execution functions. The commit ID is displayed when the commit is scheduled
    via the functions named above.

    State SLS Example:

    .. code-block:: yaml

        '20180726083540640360':
          netconfig.commit_cancelled
    """
    cancelled = {"name": name, "result": None, "changes": {}, "comment": ""}
    if __opts__["test"]:
        cancelled["comment"] = f"It would cancel commit #{name}"
        return cancelled
    ret = __salt__["net.cancel_commit"](name)
    cancelled.update(ret)
    return cancelled


def commit_confirmed(name):
    """
    .. versionadded:: 2019.2.0

    Confirm a commit scheduled to be reverted via the ``revert_in`` and
    ``revert_at`` arguments from the
    :mod:`net.load_template <salt.modules.napalm_network.load_template>` or
    :mod:`net.load_config <salt.modules.napalm_network.load_config>`
    execution functions. The commit ID is displayed when the commit confirmed
    is scheduled via the functions named above.

    State SLS Example:

    .. code-block:: yaml

        '20180726083540640360':
          netconfig.commit_confirmed
    """
    confirmed = {"name": name, "result": None, "changes": {}, "comment": ""}
    if __opts__["test"]:
        confirmed["comment"] = f"It would confirm commit #{name}"
        return confirmed
    ret = __salt__["net.confirm_commit"](name)
    confirmed.update(ret)
    return confirmed

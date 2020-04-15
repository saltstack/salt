# -*- coding: utf-8 -*-
"""
Cisco IOS configuration manipulation helpers

.. versionadded:: 2019.2.0

This module provides a collection of helper functions for Cisco IOS style
configuration manipulation. This module does not have external dependencies
and can be used from any Proxy or regular Minion.
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import python stdlib
import difflib

import salt.utils.dictdiffer
import salt.utils.dictupdate
from salt.exceptions import SaltException

# Import Salt modules
from salt.ext import six
from salt.utils.odict import OrderedDict

# ------------------------------------------------------------------------------
# module properties
# ------------------------------------------------------------------------------

__virtualname__ = "iosconfig"
__proxyenabled__ = ["*"]

# ------------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------------


def _attach_data_to_path(obj, ele, data):
    if ele not in obj:
        obj[ele] = OrderedDict()
        obj[ele] = data
    else:
        obj[ele].update(data)


def _attach_data_to_path_tags(obj, path, data, list_=False):
    if "#list" not in obj:
        obj["#list"] = []
    path = [path]
    obj_tmp = obj
    first = True
    while True:
        obj_tmp["#text"] = " ".join(path)
        path_item = path.pop(0)
        if not path:
            break
        else:
            if path_item not in obj_tmp:
                obj_tmp[path_item] = OrderedDict()
            obj_tmp = obj_tmp[path_item]

            if first and list_:
                obj["#list"].append({path_item: obj_tmp})
                first = False
    if path_item in obj_tmp:
        obj_tmp[path_item].update(data)
    else:
        obj_tmp[path_item] = data
    obj_tmp[path_item]["#standalone"] = True


def _parse_text_config(config_lines, with_tags=False, current_indent=0, nested=False):
    struct_cfg = OrderedDict()
    while config_lines:
        line = config_lines.pop(0)
        if not line.strip() or line.lstrip().startswith("!"):
            # empty or comment
            continue
        current_line = line.lstrip()
        leading_spaces = len(line) - len(current_line)
        if leading_spaces > current_indent:
            current_block = _parse_text_config(
                config_lines,
                current_indent=leading_spaces,
                with_tags=with_tags,
                nested=True,
            )
            if with_tags:
                _attach_data_to_path_tags(
                    struct_cfg, current_line, current_block, nested
                )
            else:
                _attach_data_to_path(struct_cfg, current_line, current_block)
        elif leading_spaces < current_indent:
            config_lines.insert(0, line)
            break
        else:
            if not nested:
                current_block = _parse_text_config(
                    config_lines,
                    current_indent=leading_spaces,
                    with_tags=with_tags,
                    nested=True,
                )
                if with_tags:
                    _attach_data_to_path_tags(
                        struct_cfg, current_line, current_block, nested
                    )
                else:
                    _attach_data_to_path(struct_cfg, current_line, current_block)
            else:
                config_lines.insert(0, line)
                break
    return struct_cfg


def _get_diff_text(old, new):
    """
    Returns the diff of two text blobs.
    """
    diff = difflib.unified_diff(old.splitlines(1), new.splitlines(1))
    return "".join([x.replace("\r", "") for x in diff])


def _print_config_text(tree, indentation=0):
    """
    Return the config as text from a config tree.
    """
    config = ""
    for key, value in six.iteritems(tree):
        config += "{indent}{line}\n".format(indent=" " * indentation, line=key)
        if value:
            config += _print_config_text(value, indentation=indentation + 1)
    return config


# ------------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------------


def tree(config=None, path=None, with_tags=False, saltenv="base"):
    """
    Transform Cisco IOS style configuration to structured Python dictionary.
    Depending on the value of the ``with_tags`` argument, this function may
    provide different views, valuable in different situations.

    config
        The configuration sent as text. This argument is ignored when ``path``
        is configured.

    path
        Absolute or remote path from where to load the configuration text. This
        argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    with_tags: ``False``
        Whether this function should return a detailed view, with tags.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.tree path=salt://path/to/my/config.txt
        salt '*' iosconfig.tree path=https://bit.ly/2mAdq7z
    """
    if path:
        config = __salt__["cp.get_file_str"](path, saltenv=saltenv)
        if config is False:
            raise SaltException("{} is not available".format(path))
    config_lines = config.splitlines()
    return _parse_text_config(config_lines, with_tags=with_tags)


def clean(config=None, path=None, saltenv="base"):
    """
    Return a clean version of the config, without any special signs (such as
    ``!`` as an individual line) or empty lines, but just lines with significant
    value in the configuration of the network device.

    config
        The configuration sent as text. This argument is ignored when ``path``
        is configured.

    path
        Absolute or remote path from where to load the configuration text. This
        argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.clean path=salt://path/to/my/config.txt
        salt '*' iosconfig.clean path=https://bit.ly/2mAdq7z
    """
    config_tree = tree(config=config, path=path, saltenv=saltenv)
    return _print_config_text(config_tree)


def merge_tree(
    initial_config=None,
    initial_path=None,
    merge_config=None,
    merge_path=None,
    saltenv="base",
):
    """
    Return the merge tree of the ``initial_config`` with the ``merge_config``,
    as a Python dictionary.

    initial_config
        The initial configuration sent as text. This argument is ignored when
        ``initial_path`` is set.

    initial_path
        Absolute or remote path from where to load the initial configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    merge_config
        The config to be merged into the initial config, sent as text. This
        argument is ignored when ``merge_path`` is set.

    merge_path
        Absolute or remote path from where to load the merge configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``initial_path`` or ``merge_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.merge_tree initial_path=salt://path/to/running.cfg merge_path=salt://path/to/merge.cfg
    """
    merge_tree = tree(config=merge_config, path=merge_path, saltenv=saltenv)
    initial_tree = tree(config=initial_config, path=initial_path, saltenv=saltenv)
    return salt.utils.dictupdate.merge(initial_tree, merge_tree)


def merge_text(
    initial_config=None,
    initial_path=None,
    merge_config=None,
    merge_path=None,
    saltenv="base",
):
    """
    Return the merge result of the ``initial_config`` with the ``merge_config``,
    as plain text.

    initial_config
        The initial configuration sent as text. This argument is ignored when
        ``initial_path`` is set.

    initial_path
        Absolute or remote path from where to load the initial configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    merge_config
        The config to be merged into the initial config, sent as text. This
        argument is ignored when ``merge_path`` is set.

    merge_path
        Absolute or remote path from where to load the merge configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``initial_path`` or ``merge_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.merge_text initial_path=salt://path/to/running.cfg merge_path=salt://path/to/merge.cfg
    """
    candidate_tree = merge_tree(
        initial_config=initial_config,
        initial_path=initial_path,
        merge_config=merge_config,
        merge_path=merge_path,
        saltenv=saltenv,
    )
    return _print_config_text(candidate_tree)


def merge_diff(
    initial_config=None,
    initial_path=None,
    merge_config=None,
    merge_path=None,
    saltenv="base",
):
    """
    Return the merge diff, as text, after merging the merge config into the
    initial config.

    initial_config
        The initial configuration sent as text. This argument is ignored when
        ``initial_path`` is set.

    initial_path
        Absolute or remote path from where to load the initial configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    merge_config
        The config to be merged into the initial config, sent as text. This
        argument is ignored when ``merge_path`` is set.

    merge_path
        Absolute or remote path from where to load the merge configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``initial_path`` or ``merge_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.merge_diff initial_path=salt://path/to/running.cfg merge_path=salt://path/to/merge.cfg
    """
    if initial_path:
        initial_config = __salt__["cp.get_file_str"](initial_path, saltenv=saltenv)
    candidate_config = merge_text(
        initial_config=initial_config,
        merge_config=merge_config,
        merge_path=merge_path,
        saltenv=saltenv,
    )
    clean_running_dict = tree(config=initial_config)
    clean_running = _print_config_text(clean_running_dict)
    return _get_diff_text(clean_running, candidate_config)


def diff_tree(
    candidate_config=None,
    candidate_path=None,
    running_config=None,
    running_path=None,
    saltenv="base",
):
    """
    Return the diff, as Python dictionary, between the candidate and the running
    configuration.

    candidate_config
        The candidate configuration sent as text. This argument is ignored when
        ``candidate_path`` is set.

    candidate_path
        Absolute or remote path from where to load the candidate configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    running_config
        The running configuration sent as text. This argument is ignored when
        ``running_path`` is set.

    running_path
        Absolute or remote path from where to load the runing configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``candidate_path`` or ``running_path`` is not a
        ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.diff_tree candidate_path=salt://path/to/candidate.cfg running_path=salt://path/to/running.cfg
    """
    candidate_tree = tree(config=candidate_config, path=candidate_path, saltenv=saltenv)
    running_tree = tree(config=running_config, path=running_path, saltenv=saltenv)
    return salt.utils.dictdiffer.deep_diff(running_tree, candidate_tree)


def diff_text(
    candidate_config=None,
    candidate_path=None,
    running_config=None,
    running_path=None,
    saltenv="base",
):
    """
    Return the diff, as text, between the candidate and the running config.

    candidate_config
        The candidate configuration sent as text. This argument is ignored when
        ``candidate_path`` is set.

    candidate_path
        Absolute or remote path from where to load the candidate configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    running_config
        The running configuration sent as text. This argument is ignored when
        ``running_path`` is set.

    running_path
        Absolute or remote path from where to load the runing configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``candidate_path`` or ``running_path`` is not a
        ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' iosconfig.diff_text candidate_path=salt://path/to/candidate.cfg running_path=salt://path/to/running.cfg
    """
    candidate_text = clean(
        config=candidate_config, path=candidate_path, saltenv=saltenv
    )
    running_text = clean(config=running_config, path=running_path, saltenv=saltenv)
    return _get_diff_text(running_text, candidate_text)

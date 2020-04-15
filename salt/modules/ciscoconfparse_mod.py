# -*- coding: utf-8 -*-
"""
Execution module for `ciscoconfparse <http://www.pennington.net/py/ciscoconfparse/index.html>`_

.. versionadded:: 2019.2.0

This module can be used for basic configuration parsing, audit or validation
for a variety of network platforms having Cisco IOS style configuration (one
space indentation), including: Cisco IOS, Cisco Nexus, Cisco IOS-XR,
Cisco IOS-XR, Cisco ASA, Arista EOS, Brocade, HP Switches, Dell PowerConnect
Switches, or Extreme Networks devices. In newer versions, ``ciscoconfparse``
provides support for brace-delimited configuration style as well, for platforms
such as: Juniper Junos, Palo Alto, or F5 Networks.

See http://www.pennington.net/py/ciscoconfparse/index.html for further details.

:depends: ciscoconfparse

This module depends on the Python library with the same name,
``ciscoconfparse`` - to install execute: ``pip install ciscoconfparse``.
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

from salt.exceptions import SaltException

# Import Salt modules
from salt.ext import six

try:
    import ciscoconfparse

    HAS_CISCOCONFPARSE = True
except ImportError:
    HAS_CISCOCONFPARSE = False

# ------------------------------------------------------------------------------
# module properties
# ------------------------------------------------------------------------------

__virtualname__ = "ciscoconfparse"

# ------------------------------------------------------------------------------
# property functions
# ------------------------------------------------------------------------------


def __virtual__():
    return HAS_CISCOCONFPARSE


# ------------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------------


def _get_ccp(config=None, config_path=None, saltenv="base"):
    """
    """
    if config_path:
        config = __salt__["cp.get_file_str"](config_path, saltenv=saltenv)
        if config is False:
            raise SaltException("{} is not available".format(config_path))
    if isinstance(config, six.string_types):
        config = config.splitlines()
    ccp = ciscoconfparse.CiscoConfParse(config)
    return ccp


# ------------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------------


def find_objects(config=None, config_path=None, regex=None, saltenv="base"):
    """
    Return all the line objects that match the expression in the ``regex``
    argument.

    .. warning::
        This function is mostly valuable when invoked from other Salt
        components (i.e., execution modules, states, templates etc.). For CLI
        usage, please consider using
        :py:func:`ciscoconfparse.find_lines <salt.ciscoconfparse_mod.find_lines>`

    config
        The configuration sent as text.

        .. note::
            This argument is ignored when ``config_path`` is specified.

    config_path
        The absolute or remote path to the file with the configuration to be
        parsed. This argument supports the usual Salt filesystem URIs, e.g.,
        ``salt://``, ``https://``, ``ftp://``, ``s3://``, etc.

    regex
        The regular expression to match the lines against.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. This
        argument is ignored when ``config_path`` is not a ``salt://`` URL.

    Usage example:

    .. code-block:: python

        objects = __salt__['ciscoconfparse.find_objects'](config_path='salt://path/to/config.txt',
                                                          regex='Gigabit')
        for obj in objects:
            print(obj.text)
    """
    ccp = _get_ccp(config=config, config_path=config_path, saltenv=saltenv)
    lines = ccp.find_objects(regex)
    return lines


def find_lines(config=None, config_path=None, regex=None, saltenv="base"):
    """
    Return all the lines (as text) that match the expression in the ``regex``
    argument.

    config
        The configuration sent as text.

        .. note::
            This argument is ignored when ``config_path`` is specified.

    config_path
        The absolute or remote path to the file with the configuration to be
        parsed. This argument supports the usual Salt filesystem URIs, e.g.,
        ``salt://``, ``https://``, ``ftp://``, ``s3://``, etc.

    regex
        The regular expression to match the lines against.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. This
        argument is ignored when ``config_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' ciscoconfparse.find_lines config_path=https://bit.ly/2mAdq7z regex='ip address'

    Output example:

    .. code-block:: text

       cisco-ios-router:
            -  ip address dhcp
            -  ip address 172.20.0.1 255.255.255.0
            -  no ip address
    """
    lines = find_objects(
        config=config, config_path=config_path, regex=regex, saltenv=saltenv
    )
    return [line.text for line in lines]


def find_objects_w_child(
    config=None,
    config_path=None,
    parent_regex=None,
    child_regex=None,
    ignore_ws=False,
    saltenv="base",
):
    """
    Parse through the children of all parent lines matching ``parent_regex``,
    and return a list of child objects, which matched the ``child_regex``.

    .. warning::
        This function is mostly valuable when invoked from other Salt
        components (i.e., execution modules, states, templates etc.). For CLI
        usage, please consider using
        :py:func:`ciscoconfparse.find_lines_w_child <salt.ciscoconfparse_mod.find_lines_w_child>`

    config
        The configuration sent as text.

        .. note::
            This argument is ignored when ``config_path`` is specified.

    config_path
        The absolute or remote path to the file with the configuration to be
        parsed. This argument supports the usual Salt filesystem URIs, e.g.,
        ``salt://``, ``https://``, ``ftp://``, ``s3://``, etc.

    parent_regex
        The regular expression to match the parent lines against.

    child_regex
        The regular expression to match the child lines against.

    ignore_ws: ``False``
        Whether to ignore the white spaces.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. This
        argument is ignored when ``config_path`` is not a ``salt://`` URL.

    Usage example:

    .. code-block:: python

        objects = __salt__['ciscoconfparse.find_objects_w_child'](config_path='https://bit.ly/2mAdq7z',
                                                                  parent_regex='line con',
                                                                  child_regex='stopbits')
        for obj in objects:
            print(obj.text)
    """
    ccp = _get_ccp(config=config, config_path=config_path, saltenv=saltenv)
    lines = ccp.find_objects_w_child(parent_regex, child_regex, ignore_ws=ignore_ws)
    return lines


def find_lines_w_child(
    config=None,
    config_path=None,
    parent_regex=None,
    child_regex=None,
    ignore_ws=False,
    saltenv="base",
):
    r"""
    Return a list of parent lines (as text)  matching the regular expression
    ``parent_regex`` that have children lines matching ``child_regex``.

    config
        The configuration sent as text.

        .. note::
            This argument is ignored when ``config_path`` is specified.

    config_path
        The absolute or remote path to the file with the configuration to be
        parsed. This argument supports the usual Salt filesystem URIs, e.g.,
        ``salt://``, ``https://``, ``ftp://``, ``s3://``, etc.

    parent_regex
        The regular expression to match the parent lines against.

    child_regex
        The regular expression to match the child lines against.

    ignore_ws: ``False``
        Whether to ignore the white spaces.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. This
        argument is ignored when ``config_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' ciscoconfparse.find_lines_w_child config_path=https://bit.ly/2mAdq7z parent_line='line con' child_line='stopbits'
        salt '*' ciscoconfparse.find_lines_w_child config_path=https://bit.ly/2uIRxau parent_regex='ge-(.*)' child_regex='unit \d+'
   """
    lines = find_objects_w_child(
        config=config,
        config_path=config_path,
        parent_regex=parent_regex,
        child_regex=child_regex,
        ignore_ws=ignore_ws,
        saltenv=saltenv,
    )
    return [line.text for line in lines]


def find_objects_wo_child(
    config=None,
    config_path=None,
    parent_regex=None,
    child_regex=None,
    ignore_ws=False,
    saltenv="base",
):
    """
    Return a list of parent ``ciscoconfparse.IOSCfgLine`` objects, which matched
    the ``parent_regex`` and whose children did *not* match ``child_regex``.
    Only the parent ``ciscoconfparse.IOSCfgLine`` objects will be returned. For
    simplicity, this method only finds oldest ancestors without immediate
    children that match.

    .. warning::
        This function is mostly valuable when invoked from other Salt
        components (i.e., execution modules, states, templates etc.). For CLI
        usage, please consider using
        :py:func:`ciscoconfparse.find_lines_wo_child <salt.ciscoconfparse_mod.find_lines_wo_child>`

    config
        The configuration sent as text.

        .. note::
            This argument is ignored when ``config_path`` is specified.

    config_path
        The absolute or remote path to the file with the configuration to be
        parsed. This argument supports the usual Salt filesystem URIs, e.g.,
        ``salt://``, ``https://``, ``ftp://``, ``s3://``, etc.

    parent_regex
        The regular expression to match the parent lines against.

    child_regex
        The regular expression to match the child lines against.

    ignore_ws: ``False``
        Whether to ignore the white spaces.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. This
        argument is ignored when ``config_path`` is not a ``salt://`` URL.

    Usage example:

    .. code-block:: python

        objects = __salt__['ciscoconfparse.find_objects_wo_child'](config_path='https://bit.ly/2mAdq7z',
                                                                   parent_regex='line con',
                                                                   child_regex='stopbits')
        for obj in objects:
            print(obj.text)
   """
    ccp = _get_ccp(config=config, config_path=config_path, saltenv=saltenv)
    lines = ccp.find_objects_wo_child(parent_regex, child_regex, ignore_ws=ignore_ws)
    return lines


def find_lines_wo_child(
    config=None,
    config_path=None,
    parent_regex=None,
    child_regex=None,
    ignore_ws=False,
    saltenv="base",
):
    """
    Return a list of parent ``ciscoconfparse.IOSCfgLine`` lines as text, which
    matched the ``parent_regex`` and whose children did *not* match ``child_regex``.
    Only the parent ``ciscoconfparse.IOSCfgLine`` text lines  will be returned.
    For simplicity, this method only finds oldest ancestors without immediate
    children that match.

    config
        The configuration sent as text.

        .. note::
            This argument is ignored when ``config_path`` is specified.

    config_path
        The absolute or remote path to the file with the configuration to be
        parsed. This argument supports the usual Salt filesystem URIs, e.g.,
        ``salt://``, ``https://``, ``ftp://``, ``s3://``, etc.

    parent_regex
        The regular expression to match the parent lines against.

    child_regex
        The regular expression to match the child lines against.

    ignore_ws: ``False``
        Whether to ignore the white spaces.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. This
        argument is ignored when ``config_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' ciscoconfparse.find_lines_wo_child config_path=https://bit.ly/2mAdq7z parent_line='line con' child_line='stopbits'
    """
    lines = find_objects_wo_child(
        config=config,
        config_path=config_path,
        parent_regex=parent_regex,
        child_regex=child_regex,
        ignore_ws=ignore_ws,
        saltenv=saltenv,
    )
    return [line.text for line in lines]


def filter_lines(
    config=None, config_path=None, parent_regex=None, child_regex=None, saltenv="base"
):
    """
    Return a list of detailed matches, for the configuration blocks (parent-child
    relationship) whose parent respects the regular expressions configured via
    the ``parent_regex`` argument, and the child matches the ``child_regex``
    regular expression. The result is a list of dictionaries with the following
    keys:

    - ``match``: a boolean value that tells whether ``child_regex`` matched any
      children lines.
    - ``parent``: the parent line (as text).
    - ``child``: the child line (as text). If no child line matched, this field
      will be ``None``.

    Note that the return list contains the elements that matched the parent
    condition, the ``parent_regex`` regular expression. Therefore, the ``parent``
    field will always have a valid value, while ``match`` and ``child`` may
    default to ``False`` and ``None`` respectively when there is not child match.

    CLI Example:

    .. code-block:: bash

        salt '*' ciscoconfparse.filter_lines config_path=https://bit.ly/2mAdq7z parent_regex='Gigabit' child_regex='shutdown'

    Example output (for the example above):

    .. code-block:: python

        [
            {
                'parent': 'interface GigabitEthernet1',
                'match': False,
                'child': None
            },
            {
                'parent': 'interface GigabitEthernet2',
                'match': True,
                'child': ' shutdown'
            },
            {
                'parent': 'interface GigabitEthernet3',
                'match': True,
                'child': ' shutdown'
            }
        ]
    """
    ret = []
    ccp = _get_ccp(config=config, config_path=config_path, saltenv=saltenv)
    parent_lines = ccp.find_objects(parent_regex)
    for parent_line in parent_lines:
        child_lines = parent_line.re_search_children(child_regex)
        if child_lines:
            for child_line in child_lines:
                ret.append(
                    {
                        "match": True,
                        "parent": parent_line.text,
                        "child": child_line.text,
                    }
                )
        else:
            ret.append({"match": False, "parent": parent_line.text, "child": None})
    return ret

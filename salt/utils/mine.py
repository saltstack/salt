"""
This module contains routines used for the salt mine
"""

import logging

import salt.utils.data

log = logging.getLogger(__name__)

MINE_ITEM_ACL_ID = "__saltmine_acl__"
MINE_ITEM_ACL_VERSION = 1
MINE_ITEM_ACL_DATA = "__data__"


def minion_side_acl_denied(minion_acl_cache, mine_minion, mine_function, req_minion):
    """
    Helper function to determine if a ``req_minion`` is not allowed to retrieve
    ``mine_function``-data from the mine of ``mine_minion``.

    :param dict minion_acl_cache: Contains minion_id as first level key, and mine
        function as 2nd level key. Value of 2nd level is a list of minions that
        are allowed to retrieve the function from the mine of the minion.
    :param str mine_minion: The minion that the mine value originated from.
    :param str mine_function: The mine function that is requested.
    :param str req_minion: The minion that is requesting the mine data.

    :rtype: bool
    :return:
        False if no ACL has been defined for ``mine_minion``, ``mine_function``.
        False if an ACL has been defined and it grants access.
        True if an ACL has been defined and does not grant access.
    """
    minion_acl_entry = minion_acl_cache.get(mine_minion, {}).get(mine_function, [])
    ret = minion_acl_entry and req_minion not in minion_acl_entry
    if ret:
        log.debug(
            "Salt mine request from %s for function %s on minion %s denied.",
            req_minion,
            mine_function,
            mine_minion,
        )
    return ret


def wrap_acl_structure(function_data, allow_tgt=None, allow_tgt_type=None):
    """
    Helper function to convert an non-ACL mine entry into the new entry which
    includes ACL data.

    :param dict function_data: The function data to wrap.
    :param str allow_tgt: The targeting string that designates which minions can
        request this mine entry.
    :param str allow_tgt_type: The type of targeting string.
        .. seealso:: :ref:`targeting`

    :rtype: dict
    :return: Mine entry structured to include ACL data.
    """
    res = {
        MINE_ITEM_ACL_DATA: function_data,
        MINE_ITEM_ACL_ID: MINE_ITEM_ACL_VERSION,
    }
    # Add minion-side ACL
    if allow_tgt:
        res.update(
            salt.utils.data.filter_falsey(
                {"allow_tgt": allow_tgt, "allow_tgt_type": allow_tgt_type}
            )
        )
    return res


def parse_function_definition(function_definition):
    """
    Helper function to parse the mine_function definition as provided in config,
    or pillar.

    :param function_definition: The function definition to parse.
    :type function_definition: list or dict

    :rtype: tuple
    :return: Tuple with function_name, function_args, function_kwargs, minion_acl (dict)
    """
    function_name = None
    function_args = []
    function_kwargs = {}
    minion_acl = {}
    if isinstance(function_definition, dict):
        # dictionary format for specifying mine function
        function_name = function_definition.pop("mine_function", None)
        function_kwargs = function_definition
    elif isinstance(function_definition, list):
        for item in function_definition:
            if isinstance(item, dict):
                # if len(item) > 1: # Multiple kwargs in a single list item
                function_kwargs.update(item)
            else:
                function_args.append(item)
        function_name = function_kwargs.pop("mine_function", None)

    minion_acl = salt.utils.data.filter_falsey(
        {
            "allow_tgt": function_kwargs.pop("allow_tgt", None),
            "allow_tgt_type": function_kwargs.pop("allow_tgt_type", None),
        }
    )

    return (function_name, function_args, function_kwargs, minion_acl)

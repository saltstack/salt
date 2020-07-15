# -*- coding: utf-8 -*-
"""
Decorators for salt.state

:codeauthor: :email:`Bo Maryniuk (bo@suse.de)`
"""

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging

# Import salt libs
import salt.utils.stringutils
from salt.exceptions import SaltException

log = logging.getLogger(__name__)


class OutputUnifier(object):
    def __init__(self, *policies):
        self.policies = []
        for pls in policies:
            if not hasattr(self, pls):
                raise SaltException("Unknown policy: {0}".format(pls))
            else:
                self.policies.append(getattr(self, pls))

    def __call__(self, func):
        def _func(*args, **kwargs):
            result = func(*args, **kwargs)
            for pls in self.policies:
                try:
                    result = pls(result)
                except Exception as exc:  # pylint: disable=broad-except
                    log.debug(
                        "An exception occurred in this state: %s",
                        exc,
                        exc_info_on_loglevel=logging.DEBUG,
                    )
                    result = {
                        "result": False,
                        "name": "later",
                        "changes": {},
                        "comment": "An exception occurred in this state: {0}".format(
                            exc
                        ),
                    }
            return result

        return _func

    def content_check(self, result):
        """
        Checks for specific types in the state output.
        Raises an Exception in case particular rule is broken.

        :param result:
        :return:
        """
        if not isinstance(result, dict):
            err_msg = "Malformed state return. Data must be a dictionary type."
        elif not isinstance(result.get("changes"), dict):
            err_msg = "'Changes' should be a dictionary."
        else:
            missing = []
            for val in ["name", "result", "changes", "comment"]:
                if val not in result:
                    missing.append(val)
            if missing:
                err_msg = "The following keys were not present in the state return: {0}.".format(
                    ", ".join(missing)
                )
            else:
                err_msg = None

        if err_msg:
            raise SaltException(err_msg)

        return result

    def unify(self, result):
        """
        While comments as a list are allowed,
        comments needs to be strings for backward compatibility.
        See such claim here: https://github.com/saltstack/salt/pull/43070

        Rules applied:
          - 'comment' is joined into a multi-line string, in case the value is a list.
          - 'result' should be always either True, False or None.

        :param result:
        :return:
        """
        if isinstance(result.get("comment"), list):
            result["comment"] = "\n".join(
                [salt.utils.stringutils.to_unicode(elm) for elm in result["comment"]]
            )
        if result.get("result") is not None:
            result["result"] = bool(result["result"])

        return result

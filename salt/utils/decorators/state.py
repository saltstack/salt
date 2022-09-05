"""
Decorators for salt.state

:codeauthor: :email:`Bo Maryniuk (bo@suse.de)`
"""


import logging

import salt.utils.stringutils
from salt.exceptions import SaltException

log = logging.getLogger(__name__)


class OutputUnifier:
    def __init__(self, *policies):
        self.policies = []
        for pls in policies:
            if not hasattr(self, pls):
                raise SaltException("Unknown policy: {}".format(pls))
            else:
                self.policies.append(getattr(self, pls))

    def _run_policies(self, data):
        for pls in self.policies:
            try:
                data = pls(data)
            except Exception as exc:  # pylint: disable=broad-except
                log.debug(
                    "An exception occurred in this state: %s",
                    exc,
                    exc_info_on_loglevel=logging.DEBUG,
                )
                data = {
                    "result": False,
                    "name": "later",
                    "changes": {},
                    "comment": "An exception occurred in this state: {}".format(exc),
                }
        return data

    def __call__(self, func):
        def _func(*args, **kwargs):
            result = func(*args, **kwargs)
            sub_state_run = None
            if isinstance(result, dict):
                sub_state_run = result.get("sub_state_run", ())
            result = self._run_policies(result)
            if sub_state_run:
                result["sub_state_run"] = [
                    self._run_policies(sub_state_data)
                    for sub_state_data in sub_state_run
                ]
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
                err_msg = "The following keys were not present in the state return: {}.".format(
                    ", ".join(missing)
                )
            else:
                err_msg = None

        if err_msg:
            raise SaltException(err_msg)

        for sub_state in result.get("sub_state_run", ()):
            self.content_check(sub_state)

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

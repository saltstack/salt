"""
Decorators for salt.state
"""
import logging
import warnings
from functools import wraps

import salt.utils.stringutils
from salt.exceptions import SaltException

log = logging.getLogger(__name__)


class OutputUnifier:
    """
    :codeauthor: :email:`Bo Maryniuk (bo@suse.de)`
    """

    def __init__(self, *policies):
        self.policies = []
        for pls in policies:
            if not hasattr(self, pls):
                raise SaltException(f"Unknown policy: {pls}")
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
                    "comment": f"An exception occurred in this state: {exc}",
                }
        return data

    def __call__(self, func):
        @wraps(func)
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


def include_warnings_in_state_return(func):
    """
    Include any warnings thrown by Python's :ref:`warnings <python:warnings>` module
    in state returns.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings(record=True) as collected_warnings:
            ret = func(*args, **kwargs)
        if collected_warnings:
            if isinstance(ret, dict):
                for warning in collected_warnings:
                    try:
                        ret.setdefault("warnings", []).append(
                            warnings.formatwarning(
                                warning.message,
                                warning.category,
                                warning.filename,
                                warning.lineno,
                                line=warning.line,
                            )
                        )
                    except Exception:  # pylint: disable=broad-except
                        log.exception("Failed to format warning")
            else:
                try:
                    warnings.showwarning(
                        warning.message,
                        warning.category,
                        warning.filename,
                        warning.lineno,
                        file=warning.file,
                        line=warning.line,
                    )
                except Exception:  # pylint: disable=broad-except
                    log.exception("Failed to show warning")
        return ret

    return wrapper

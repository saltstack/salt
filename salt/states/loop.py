"""
Loop state

Allows for looping over execution modules.

.. versionadded:: 2017.7.0

In both examples below, the execution module function ``boto_elb.get_instance_health``
returns a list of dicts. The condition checks the ``state``-key of the first dict
in the returned list and compares its value to the string `InService`.

.. code-block:: yaml

    wait_for_service_to_be_healthy:
      loop.until:
        - name: boto_elb.get_instance_health
        - condition: m_ret[0]['state'] == 'InService'
        - period: 5
        - timeout: 20
        - m_args:
          - {{ elb }}
        - m_kwargs:
            keyid: {{ access_key }}
            key: {{ secret_key }}
            instances: "{{ instance }}"

.. warning::

    This state allows arbitrary python code to be executed through the condition
    parameter which is literally evaluated within the state. Please use caution.

.. versionchanged:: 3000

A version that does not use eval is now available. It uses either the python ``operator``
to compare the result of the function called in ``name``, which can be one of the
following: lt, le, eq (default), ne, ge, gt.
Alternatively, `compare_operator` can be filled with a function from an execution
module in ``__salt__`` or ``__utils__`` like the example below.
The function :py:func:`data.subdict_match <salt.utils.data.subdict_match>` checks if the
``expected`` expression matches the data returned by calling the ``name`` function
(with passed ``args`` and ``kwargs``).

.. code-block:: yaml

    Wait for service to be healthy:
      loop.until_no_eval:
        - name: boto_elb.get_instance_health
        - expected: '0:state:InService'
        - compare_operator: data.subdict_match
        - period: 5
        - timeout: 20
        - args:
          - {{ elb }}
        - kwargs:
            keyid: {{ access_key }}
            key: {{ secret_key }}
            instances: "{{ instance }}"
"""


import logging
import operator
import sys
import time

# Initialize logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "loop"


def __virtual__():
    return True


def until(name, m_args=None, m_kwargs=None, condition=None, period=1, timeout=60):
    """
    Loop over an execution module until a condition is met.

    :param str name: The name of the execution module
    :param list m_args: The execution module's positional arguments
    :param dict m_kwargs: The execution module's keyword arguments
    :param str condition: The condition which must be met for the loop to break.
        This should contain ``m_ret`` which is the return from the execution module.
    :param period: The number of seconds to wait between executions
    :type period: int or float
    :param timeout: The timeout in seconds
    :type timeout: int or float
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if m_args is None:
        m_args = ()
    if m_kwargs is None:
        m_kwargs = {}

    if name not in __salt__:
        ret["comment"] = "Cannot find module {}".format(name)
    elif condition is None:
        ret["comment"] = "An exit condition must be specified"
    elif not isinstance(period, (int, float)):
        ret["comment"] = "Period must be specified as a float in seconds"
    elif not isinstance(timeout, (int, float)):
        ret["comment"] = "Timeout must be specified as a float in seconds"
    elif __opts__["test"]:
        ret["comment"] = "The execution module {} will be run".format(name)
        ret["result"] = None
    else:
        if m_args is None:
            m_args = []
        if m_kwargs is None:
            m_kwargs = {}

        timeout = time.time() + timeout
        while time.time() < timeout:
            m_ret = __salt__[name](*m_args, **m_kwargs)
            if eval(condition):  # pylint: disable=W0123
                ret["result"] = True
                ret["comment"] = "Condition {} was met".format(condition)
                break
            time.sleep(period)
        else:
            ret["comment"] = "Timed out while waiting for condition {}".format(
                condition
            )
    return ret


def until_no_eval(
    name,
    expected,
    compare_operator="eq",
    timeout=60,
    period=1,
    init_wait=0,
    args=None,
    kwargs=None,
):
    """
    Generic waiter state that waits for a specific salt function to produce an
    expected result.
    The state fails if the function does not exist or raises an exception,
    or does not produce the expected result within the allotted retries.

    :param str name: Name of the module.function to call
    :param expected: Expected return value. This can be almost anything.
    :param str compare_operator: Operator to use to compare the result of the
        module.function call with the expected value. This can be anything present
        in __salt__ or __utils__. Will be called with 2 args: result, expected.
    :param timeout: Abort after this amount of seconds (excluding init_wait).
    :type timeout: int or float
    :param period: Time (in seconds) to wait between attempts.
    :type period: int or float
    :param init_wait: Time (in seconds) to wait before trying anything.
    :type init_wait: int or float
    :param list args: args to pass to the salt module.function.
    :param dict kwargs: kwargs to pass to the salt module.function.

    .. versionadded:: 3000

    """
    ret = {"name": name, "comment": "", "changes": {}, "result": False}
    if name not in __salt__:
        ret["comment"] = 'Module.function "{}" is unavailable.'.format(name)
    elif not isinstance(period, (int, float)):
        ret["comment"] = "Period must be specified as a float in seconds"
    elif not isinstance(timeout, (int, float)):
        ret["comment"] = "Timeout must be specified as a float in seconds"
    elif compare_operator in __salt__:
        comparator = __salt__[compare_operator]
    elif compare_operator in __utils__:
        comparator = __utils__[compare_operator]
    elif not hasattr(operator, compare_operator):
        ret["comment"] = 'Invalid operator "{}" supplied.'.format(compare_operator)
    else:
        comparator = getattr(operator, compare_operator)
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = 'Would have waited for "{}" to produce "{}".'.format(
            name, expected
        )
    if ret["comment"]:
        return ret

    if init_wait:
        time.sleep(init_wait)
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    res_archive = []
    current_attempt = 0
    timeout = time.time() + timeout
    while time.time() < timeout:
        current_attempt += 1
        try:
            res = __salt__[name](*args, **kwargs)
        except Exception:  # pylint: disable=broad-except
            (exc_type, exc_value, _) = sys.exc_info()
            ret["comment"] = "Exception occurred while executing {}: {}:{}".format(
                name, exc_type, exc_value
            )
            break
        res_archive.append(res)
        cmp_res = comparator(res, expected)
        log.debug(
            "%s:until_no_eval:\n"
            "\t\tAttempt %s, result: %s, expected: %s, compare result: %s",
            __name__,
            current_attempt,
            res,
            expected,
            cmp_res,
        )
        if cmp_res:
            ret["result"] = True
            ret["comment"] = "Call provided the expected results in {} attempts".format(
                current_attempt
            )
            break
        time.sleep(period)
    else:
        ret[
            "comment"
        ] = "Call did not produce the expected result after {} attempts".format(
            current_attempt
        )
        log.debug(
            "%s:until_no_eval:\n\t\tResults of all attempts: %s",
            __name__,
            res_archive,
        )
    return ret

"""
State to control Apache modjk
"""

# Python Libs

import logging

log = logging.getLogger(__name__)


def __virtual__():
    """
    Load this state if modjk is loaded
    """
    if "modjk.workers" in __salt__:
        return True
    return (False, "modjk module could not be loaded")


def _bulk_state(saltfunc, lbn, workers, profile):
    """
    Generic function for bulk worker operation
    """
    ret = {"name": lbn, "result": True, "changes": {}, "comment": ""}

    if not isinstance(workers, list):
        ret["result"] = False
        ret["comment"] = f"workers should be a list not a {type(workers)}"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        return ret

    log.info("executing %s to modjk workers %s", saltfunc, workers)
    try:
        cmdret = __salt__[saltfunc](workers, lbn, profile=profile)
    except KeyError:
        ret["result"] = False
        ret["comment"] = f"unsupported function {saltfunc}"
        return ret

    errors = []
    for worker, ok in cmdret.items():
        if not ok:
            errors.append(worker)

    ret["changes"] = {"status": cmdret}
    if errors:
        ret["result"] = False
        ret["comment"] = f"{saltfunc} failed on some workers"

    return ret


def worker_stopped(name, workers=None, profile="default"):
    """
    Stop all the workers in the modjk load balancer

    Example:

    .. code-block:: yaml

        loadbalancer:
          modjk.worker_stopped:
            - workers:
              - app1
              - app2
    """
    if workers is None:
        workers = []
    return _bulk_state("modjk.bulk_stop", name, workers, profile)


def worker_activated(name, workers=None, profile="default"):
    """
    Activate all the workers in the modjk load balancer

    Example:

    .. code-block:: yaml

        loadbalancer:
          modjk.worker_activated:
            - workers:
              - app1
              - app2
    """
    if workers is None:
        workers = []
    return _bulk_state("modjk.bulk_activate", name, workers, profile)


def worker_disabled(name, workers=None, profile="default"):
    """
    Disable all the workers in the modjk load balancer

    Example:

    .. code-block:: yaml

        loadbalancer:
          modjk.worker_disabled:
            - workers:
              - app1
              - app2
    """
    if workers is None:
        workers = []
    return _bulk_state("modjk.bulk_disable", name, workers, profile)


def worker_recover(name, workers=None, profile="default"):
    """
    Recover all the workers in the modjk load balancer

    Example:

    .. code-block:: yaml

        loadbalancer:
          modjk.worker_recover:
            - workers:
              - app1
              - app2
    """
    if workers is None:
        workers = []
    return _bulk_state("modjk.bulk_recover", name, workers, profile)

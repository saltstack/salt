"""
Support for scheduling celery tasks. The worker is independent of salt and thus can run in a different
virtualenv or on a different python version, as long as broker, backend and serializer configurations match.
Also note that celery and packages required by the celery broker, e.g. redis must be installed to load
the salt celery execution module.

.. note::
    A new app (and thus new connections) is created for each task execution
"""

import logging

from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


try:
    from celery import Celery
    from celery.exceptions import TimeoutError  # pylint: disable=no-name-in-module

    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False


def __virtual__():
    """
    Only load if celery libraries exist.
    """
    if not HAS_CELERY:
        return False, "The celery module could not be loaded: celery library not found"
    return True


def run_task(
    task_name,
    args=None,
    kwargs=None,
    broker=None,
    backend=None,
    wait_for_result=False,
    timeout=None,
    propagate=True,
    interval=0.5,
    no_ack=True,
    raise_timeout=True,
    config=None,
):
    """
    Execute celery tasks. For celery specific parameters see celery documentation.

    CLI Example:

    .. code-block:: bash

        salt '*' celery.run_task tasks.sleep args=[4] broker=redis://localhost \\
        backend=redis://localhost wait_for_result=true

    task_name
        The task name, e.g. tasks.sleep

    args
        Task arguments as a list

    kwargs
        Task keyword arguments

    broker
        Broker for celeryapp, see celery documentation

    backend
        Result backend for celeryapp, see celery documentation

    wait_for_result
        Wait until task result is read from result backend and return result, Default: False

    timeout
        Timeout waiting for result from celery, see celery AsyncResult.get documentation

    propagate
        Propagate exceptions from celery task, see celery AsyncResult.get documentation, Default: True

    interval
        Interval to check for task result, see celery AsyncResult.get documentation, Default: 0.5

    no_ack
        see celery AsyncResult.get documentation. Default: True

    raise_timeout
        Raise timeout exception if waiting for task result times out. Default: False

    config
        Config dict for celery app, See celery documentation

    """
    if not broker:
        raise SaltInvocationError("broker parameter is required")

    with Celery(broker=broker, backend=backend, set_as_current=False) as app:
        if config:
            app.conf.update(config)

        with app.connection():
            args = args or []
            kwargs = kwargs or {}
            async_result = app.send_task(task_name, args=args, kwargs=kwargs)

            if wait_for_result:
                try:
                    return async_result.get(
                        timeout=timeout,
                        propagate=propagate,
                        interval=interval,
                        no_ack=no_ack,
                    )
                except TimeoutError as ex:
                    log.error(
                        "Waiting for the result of a celery task execution timed out."
                    )
                    if raise_timeout:
                        raise
                    return False

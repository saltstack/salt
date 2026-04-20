"""
Runner module for managing and inspecting async batch jobs.

Provides commands for checking batch status, listing active batches,
and stopping running batch jobs.

.. code-block:: bash

    # Check status of an async batch job
    salt-run batch.status 20240610120000000000

    # List all active async batch jobs
    salt-run batch.list_active

    # Stop a running async batch job
    salt-run batch.stop 20240610120000000000
"""

import logging

log = logging.getLogger(__name__)


def status(jid):
    """
    Return the current status of an async batch job.

    Reads ``.batch.p`` from the job cache for the given JID and returns
    a summary dict containing:

    - ``fun`` — the function being executed
    - ``tgt`` — the original target expression
    - ``total`` — total number of targeted minions
    - ``completed`` — number of minions that returned successfully
    - ``failed`` — number of minions that timed out or errored
    - ``active`` — number of minions currently executing
    - ``pending`` — number of minions not yet dispatched
    - ``halted`` — whether the batch is done
    - ``halted_reason`` — why it stopped (if applicable)
    - ``created`` — timestamp when the batch was created
    - ``last_progress`` — timestamp of last state change

    Returns ``None`` if the JID does not exist or has no ``.batch.p``.

    CLI Example:

    .. code-block:: bash

        salt-run batch.status 20240610120000000000

    :param str jid: The batch JID to query.
    :returns: Status summary dict or ``None``.
    :rtype: dict or None
    """


def list_active():
    """
    Return a list of all active (non-halted) async batch jobs.

    Reads the ``batch_active.p`` index file and returns a list of dicts,
    each containing a summary of the batch job (JID, function, progress).

    CLI Example:

    .. code-block:: bash

        salt-run batch.list_active

    :returns: List of active batch summary dicts.
    :rtype: list
    """


def stop(jid):
    """
    Stop a running async batch job.

    Sets ``halted=True`` and ``halted_reason="Manually stopped"`` in
    the batch state, and fires a ``salt/batch/<jid>/stop`` event so
    the BatchManager removes it from its active set.

    Does not kill minions that are already executing — they will still
    return, but no further sub-batches will be dispatched.

    CLI Example:

    .. code-block:: bash

        salt-run batch.stop 20240610120000000000

    :param str jid: The batch JID to stop.
    :returns: ``True`` if the batch was stopped, ``False`` if the JID
        was not found or was already halted.
    :rtype: bool
    """

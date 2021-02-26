"""
Heist Salt runner for deploying and managing Salt artifacts

.. versionadded:: 3004

"""


def deploy(
    manager="salt.minion",
    artifact_version=None,
    roster_file=None,
    roster=None,
    roster_data=None,
):
    """
    Deploy the salt heist artifact.
    :depends: heist, pop, asyncio

    **Arguments**

    manager

        The salt heist manager or artifact to deploy to the target.

    artifact_version

        The version of the artifact to use.

    roster_file

        The roster file heist will use

    roster

        The type of heist roster to use. For example: flat, scan, fernet, clustershell

    roster_data

        Pass json data to be used for the roster data

    CLI Example:

    .. code-block:: bash

        salt-run heist_salt.deploy
    """
    __salt__["heist.deploy"](
        manager,
        artifact_version=artifact_version,
        roster_file=roster_file,
        roster=roster,
        roster_data=roster_data,
        sub="salt",
    )

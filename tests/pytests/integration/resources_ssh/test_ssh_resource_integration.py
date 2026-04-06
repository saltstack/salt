"""
End-to-end integration tests for the SSH resource type (``salt/resource/ssh.py``).

Unlike :mod:`tests.pytests.integration.ssh`, which runs **salt-ssh on the master**,
these tests run the **managing minion** path: master publishes to ``T@ssh:…``,
the minion dispatches into the SSH resource loader, which builds
:class:`~salt.client.ssh.Single` from **minion** ``__opts__`` and runs
``cmd_block()`` — the code path that broke with missing ``ext_pillar`` / ``fsclient``.

Requirements:

* ``--ssh-tests`` (transports sshd + roster fixtures; see ``requires_sshd_server``).
* A relenv tarball available (CI artifact or downloaded via
  :func:`salt.utils.relenv.gen_relenv`), copied into the minion cache by
  ``conftest.py``.
"""

import pytest

from tests.pytests.integration.resources_ssh.conftest import SSH_RESOURCE_ID

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.requires_sshd_server,
    pytest.mark.skip_on_windows(reason="SSH resource integration uses Unix sshd"),
]


def test_minion_pillar_lists_ssh_resource(
    salt_minion_ssh_resources, salt_call_ssh_resource
):
    """Pillar must expose ``resources.ssh.hosts`` for the SSH resource ID."""
    ret = salt_call_ssh_resource.run("pillar.get", "resources:ssh:hosts", _timeout=120)
    assert ret.returncode == 0, ret
    hosts = ret.data
    assert isinstance(hosts, dict), hosts
    assert SSH_RESOURCE_ID in hosts, f"missing {SSH_RESOURCE_ID!r}, got {list(hosts)}"
    assert hosts[SSH_RESOURCE_ID].get("host") == "127.0.0.1"


def test_ssh_resource_T_at_test_ping(
    salt_minion_ssh_resources, salt_cli_ssh_resource, relenv_tarball_for_ssh_resource
):
    """
    ``salt --compound T@ssh:… test.ping`` runs ``sshresource_test.ping`` →
    :func:`salt.resource.ssh.ping` (shell to the SSH resource).  The minion
    preloads ``ssh.grains`` for ``__grains__`` in the resource loader; that path
    must have a usable FSClient (``master_opts`` including ``cachedir``).
    """
    if not relenv_tarball_for_ssh_resource:
        pytest.skip("No relenv tarball — cannot run SSH resource against relenv bundle")

    ret = salt_cli_ssh_resource.run(
        "--compound",
        "test.ping",
        minion_tgt=f"T@ssh:{SSH_RESOURCE_ID}",
    )
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), data
    assert data.get(SSH_RESOURCE_ID) is True, data

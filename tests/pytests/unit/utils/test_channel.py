import subprocess
import sys

import salt.utils.channel
from tests.support.paths import CODE_DIR


def test_module_can_be_imported_before_salt_master():
    """
    salt.master imports salt.utils.channel, so salt.utils.channel must not
    depend on salt.master. Run in a new interpreter so that modules imported
    by other tests cannot hide a circular import.
    """
    ret = subprocess.run(
        [sys.executable, "-c", "import salt.utils.channel"],
        cwd=CODE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 0, ret.stderr


def test_iter_transport_opts_attaches_the_given_secrets():
    secrets = {"aes": {"secret": object()}}
    opts = {"transport": "zeromq", "transport_opts": {"tcp": {}}}
    ret = dict(salt.utils.channel.iter_transport_opts(opts, secrets))
    assert set(ret) == {"tcp", "zeromq"}
    for transport_opts in ret.values():
        # The very same object: secrets must not be copied
        assert transport_opts["secrets"] is secrets


def test_iter_transport_opts_keeps_secrets_already_in_opts():
    secrets = {"aes": {}}
    opts = {"transport": "tcp", "secrets": secrets}
    ((transport, transport_opts),) = salt.utils.channel.iter_transport_opts(opts)
    assert transport == "tcp"
    assert transport_opts["secrets"] is secrets

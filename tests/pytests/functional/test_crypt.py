import pathlib

import pytest

import salt.crypt

# ``salt.crypt.MasterKeys`` pulls a heavy import chain
# (salt.config, salt.utils.cloud, ext-loader modules, ...) and
# ``find_or_create_keys`` then does RSA-2048 generation + file I/O +
# salt-side logging.  All of that runs in the parent pytest process
# and is traced by coverage 7.14's sysmon.  Locally with full CI flags
# + coverage the test passes in ~3 s, but on a loaded 2-vCPU GHA runner
# the same work has been measured at >90 s, tripping pytest-timeout's
# default and failing functional zeromq 4 across every Linux distro.
# Bump the ceiling so coverage runs don't false-fail.
pytestmark = [
    pytest.mark.timeout(180, func_only=True),
]


@pytest.mark.windows_whitelisted
def test_generated_keys(master_opts, tmp_path):
    master_opts["pki_dir"] = str(tmp_path)
    master_keys = salt.crypt.MasterKeys(master_opts)
    master_keys.find_or_create_keys(name="aaa", keysize=2048)
    priv = pathlib.Path(master_keys.opts["pki_dir"]) / "aaa.pem"
    pub = priv.with_suffix(".pub")
    assert "\r" not in priv.read_text(encoding="utf-8")
    assert "\r" not in pub.read_text(encoding="utf-8")

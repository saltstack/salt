import pytest

import salt.exceptions
import salt.utils.virt


def test_virt_key(tmp_path):
    opts = {"pki_dir": f"{tmp_path / 'pki'}"}
    salt.utils.virt.VirtKey("asdf", "minion", opts)


def test_virt_key_bad_hyper(tmp_path):
    opts = {"pki_dir": f"{tmp_path / 'pki'}"}
    with pytest.raises(salt.exceptions.SaltValidationError):
        salt.utils.virt.VirtKey("asdf/../../../sdf", "minion", opts)


def test_virt_key_bad_id_(tmp_path):
    opts = {"pki_dir": f"{tmp_path / 'pki'}"}
    with pytest.raises(salt.exceptions.SaltValidationError):
        salt.utils.virt.VirtKey("hyper", "minion/../../", opts)

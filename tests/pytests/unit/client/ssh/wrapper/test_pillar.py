"""
Tests for the salt-ssh ``pillar`` wrapper.
"""

import pytest

import salt.client.ssh.wrapper.pillar as ssh_pillar
import salt.utils.secret as secret
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {ssh_pillar: {"__opts__": {}, "__pillar__": {"pin": 1234}}}


def test_item_returns_real_values_when_masking_is_off():
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": False}):
        assert ssh_pillar.item("pin") == {"pin": 1234}


def test_item_masks_when_masking_is_on():
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": True}):
        assert ssh_pillar.item("pin") == {"pin": secret.REDACT_PLACEHOLDER}

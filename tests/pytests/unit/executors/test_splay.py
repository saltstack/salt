import pytest

import salt.executors.splay as splay_exec


@pytest.fixture
def configure_loader_modules():
    return {splay_exec: {"__grains__": {"id": "foo"}}}


def test__get_hash():
    # We just want to make sure that this function does not result in an
    # error due to passing a unicode value to bytearray()
    assert splay_exec._get_hash()

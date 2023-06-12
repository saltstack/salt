import pytest


@pytest.fixture
def render_context():
    return {
        "opts": {"cachedir": "/D", "__cli": "salt"},
        "saltenv": None,
    }

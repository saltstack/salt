import pytest

import salt.engines
from tests.support.mock import MagicMock, patch


@pytest.fixture
def kwargs():
    opts = {"__role": "minion"}
    name = "foobar"
    fun = "{}.start".format(name)
    config = funcs = runners = proxy = {}
    return dict(
        opts=opts,
        name=name,
        fun=fun,
        config=config,
        funcs=funcs,
        runners=runners,
        proxy=proxy,
    )


def test_engine_module_name(kwargs):
    engine = salt.engines.Engine(**kwargs)
    assert engine.name == kwargs["name"]


def test_engine_title_set(kwargs):
    engine = salt.engines.Engine(**kwargs)
    with patch("salt.utils.process.appendproctitle", MagicMock()) as mm:
        engine.run()
    mm.assert_called_with(kwargs["name"])

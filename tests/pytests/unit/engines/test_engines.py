import salt.engines
from tests.support.mock import MagicMock, patch


def test_engine_module_name():
    engine = salt.engines.Engine({}, "foobar.start", {}, {}, {}, {}, name="foobar")
    assert engine.name == "foobar"


def test_engine_title_set():
    engine = salt.engines.Engine({}, "foobar.start", {}, {}, {}, {}, name="foobar")
    with patch("salt.utils.process.appendproctitle", MagicMock()) as mm:
        engine.run()
    mm.assert_called_with("foobar")

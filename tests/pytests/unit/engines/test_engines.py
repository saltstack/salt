import pytest
import salt.engines
from tests.support.mock import MagicMock, patch


def test_engine_module_name():
    engine = salt.engines.Engine("foobar", {}, "foobar.start", {}, {}, {}, {})
    assert engine.name == "foobar"


def test_engine_title_set():
    engine = salt.engines.Engine("foobar", {}, "foobar.start", {}, {}, {}, {})
    with patch("salt.utils.process.appendproctitle", MagicMock()) as mm:
        with pytest.raises(KeyError):
            # The method does not exist so a KeyError will be raised.
            engine.run()
        mm.assert_called_with("foobar")

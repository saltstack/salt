import salt.engines
import pytest
from tests.support.mock import patch, MagicMock


def test_engine_module_name():
    engine = salt.engines.Engine({}, 'foobar.start', {}, {}, {}, {})
    assert engine.module_name == 'foobar'

def test_engine_title_set():
    engine = salt.engines.Engine({}, 'foobar.start', {}, {}, {}, {})
    with patch('salt.utils.process.appendproctitle', MagicMock()) as mm:
        with pytest.raises(KeyError):
            # The method does not exist so a KeyError will be raised.
            engine.run()
        mm.assert_called_with('Engine: foobar')

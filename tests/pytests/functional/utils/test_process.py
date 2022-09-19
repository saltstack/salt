"""
tests.pytests.functional.utils.test_process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test salt's process utility module
"""
import pytest

import salt.utils.process


class Process(salt.utils.process.SignalHandlingProcess):
    def run(self):
        pass


@pytest.fixture
def process_manager():
    _process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    try:
        yield _process_manager
    finally:
        _process_manager.terminate()


def test_process_manager_60749(process_manager):
    """
    Regression test for issue #60749
    """

    process_manager.add_process(Process)
    process_manager.check_children()

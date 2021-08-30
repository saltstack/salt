"""
tests.pytests.functional.utils.test_process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test salt's process utility module
"""
import salt.utils.process


def test_process_manager_60749():
    """
    Regression test for issue #60749
    """

    class Process(salt.utils.process.SignalHandlingProcess):
        def run(self):
            pass

    process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    process_manager.add_process(Process)
    process_manager.check_children()

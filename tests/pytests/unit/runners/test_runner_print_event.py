"""
Tests that the print_event flag is correctly threaded through the runner call chain.
Regression tests for issue #58203.
"""

import salt.client.mixins
import salt.runner
from tests.support.mock import MagicMock, patch


class TestProcFunctionPrintEvent:
    """
    _proc_function must forward print_event to instance.low().
    """

    def test_proc_function_passes_print_event_false(self):
        """
        _proc_function(print_event=False) must call instance.low(..., print_event=False).
        """
        mock_instance = MagicMock()
        mock_instance.low.return_value = "result"

        salt.client.mixins.AsyncClientMixin._proc_function(
            instance=mock_instance,
            opts={},
            fun="test.ping",
            low={"fun": "test.ping"},
            user="root",
            tag="salt/run/1234/ret",
            jid="1234",
            daemonize=False,
            print_event=False,
        )

        assert mock_instance.low.call_count == 1
        _, low_kwargs = mock_instance.low.call_args
        assert (
            low_kwargs.get("print_event") is False
        ), "_proc_function must forward print_event=False to instance.low()"

    def test_proc_function_passes_print_event_true_by_default(self):
        """
        _proc_function default (no print_event arg) must call instance.low with print_event=True.
        """
        mock_instance = MagicMock()
        mock_instance.low.return_value = "result"

        salt.client.mixins.AsyncClientMixin._proc_function(
            instance=mock_instance,
            opts={},
            fun="test.ping",
            low={"fun": "test.ping"},
            user="root",
            tag="salt/run/1234/ret",
            jid="1234",
            daemonize=False,
        )

        _, low_kwargs = mock_instance.low.call_args
        assert (
            low_kwargs.get("print_event", True) is True
        ), "_proc_function default must keep print_event=True"


class TestRunnerRunPrintEvent:
    """
    Runner.run() must forward print_event to _proc_function.
    """

    def test_runner_run_passes_print_event_false(self, master_opts):
        """
        Runner.run(print_event=False) must pass print_event=False to _proc_function.
        """
        opts = master_opts.copy()
        opts["fun"] = "test.arg"
        opts["arg"] = []
        opts["doc"] = False
        opts["async"] = False
        opts["show_jid"] = False
        opts.pop("eauth", None)

        runner = salt.runner.Runner(opts)

        captured_kwargs = {}

        def fake_proc_function(**kwargs):
            captured_kwargs.update(kwargs)
            return {}

        with patch.object(
            salt.runner.Runner,
            "_proc_function",
            staticmethod(fake_proc_function),
        ), patch.object(
            runner,
            "_gen_async_pub",
            return_value={"jid": "test-jid", "tag": "salt/run/test-jid"},
        ), patch(
            "salt.utils.user.get_specific_user", return_value="root"
        ):
            runner.run(print_event=False)

        assert (
            "print_event" in captured_kwargs
        ), "Runner.run must forward print_event to _proc_function"
        assert captured_kwargs["print_event"] is False


class TestMinionRunnerPrintEvent:
    """
    RemoteFuncs.minion_runner must call runner.run(print_event=False).
    """

    def test_minion_runner_suppresses_print_event(self, master_opts):
        """
        minion_runner must call runner.run(print_event=False) to suppress
        unwanted event output to stdout.
        """
        import salt.daemons.masterapi as masterapi

        opts = master_opts.copy()
        opts["peer_run"] = {"minion-id": ["test.*"]}

        funcs = masterapi.RemoteFuncs(opts)
        load = {
            "fun": "test.arg",
            "arg": [],
            "id": "minion-id",
        }

        run_kwargs = {}

        def fake_run(self, **kwargs):
            run_kwargs.update(kwargs)
            return {}

        with patch.object(salt.runner.Runner, "run", fake_run):
            funcs.minion_runner(load)

        assert (
            "print_event" in run_kwargs
        ), "minion_runner must pass print_event to runner.run"
        assert (
            run_kwargs["print_event"] is False
        ), "minion_runner must suppress event output: runner.run(print_event=False)"

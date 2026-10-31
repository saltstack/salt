"""Native execution-module coroutines return values through job dispatchers."""

import asyncio
from types import SimpleNamespace

import pytest

import salt.cli.caller
import salt.client
import salt.executors.direct_call
import salt.loader.lazy
import salt.minion
from salt.exceptions import SaltInvocationError
from tests.support.mock import patch


def _sync_caller(entry, functions):
    cls = salt.client.ProxyCaller if entry == "proxy" else salt.client.Caller
    caller = object.__new__(cls)
    caller.opts = {}
    caller.sminion = SimpleNamespace(
        functions=functions,
        executors={"direct_call.execute": salt.executors.direct_call.execute},
    )
    return caller.function if entry == "function" else caller.cmd


@pytest.mark.parametrize("entry", ["cmd", "function", "proxy"])
def test_sync_client_resolves_loaded_coroutine_and_preserves_errors(functions, entry):
    call = _sync_caller(entry, functions)
    assert call("native.result") is False
    assert functions.pack["__context__"]["retcode"] == 7
    with pytest.raises(OSError, match="request failed"):
        call("native.fail")


@pytest.mark.parametrize("entry", ["cmd", "function", "proxy"])
async def test_sync_client_from_running_loop_preserves_loader_context(functions, entry):
    loop = asyncio.get_running_loop()
    call = _sync_caller(entry, functions)
    assert call("native.result") is False
    assert functions.pack["__context__"]["retcode"] == 7
    with pytest.raises(OSError, match="request failed"):
        call("native.fail")
    assert asyncio.get_running_loop() is loop


@pytest.mark.parametrize("entry", ["_thread_return", "_thread_multi_return"])
@pytest.mark.parametrize("native", [False, True])
def test_proxy_worker_accepts_sync_and_async_metaproxy_hooks(entry, native):
    calls = []

    def sync_hook(cls, instance, opts, data):
        calls.append((instance, opts, data))
        return None

    async def async_hook(*args):
        await asyncio.sleep(0)
        return sync_hook(*args)

    with patch(
        "salt.minion._metaproxy_call", return_value=async_hook if native else sync_hook
    ):
        assert (
            getattr(salt.minion.ProxyMinion, entry)(None, {"id": "proxy"}, {"jid": "1"})
            is None
        )
    assert calls == [(None, {"id": "proxy"}, {"jid": "1"})]


@pytest.mark.parametrize("result", [False, 0, {}])
async def test_executor_chain_awaits_none_then_stops_at_a_false_result(result):
    calls = []

    async def first(*args):
        await asyncio.sleep(0)
        calls.append("first")
        return None

    def second(*args):
        calls.append("second")
        return result

    def last(*args):
        pytest.fail("Executors after a non-None result must not run")

    loader = {"first.execute": first, "second.execute": second, "last.execute": last}
    actual = await salt.utils.minion.run_executors(
        loader, ["first", "second", "last"], {}, {}, None, [], {}
    )
    assert actual is result
    assert calls == ["first", "second"]


@pytest.mark.parametrize("missing", [False, True])
async def test_executor_chain_propagates_errors_without_trying_the_next_executor(
    missing,
):
    async def first(*args):
        raise OSError("executor failed")

    def last(*args):
        pytest.fail("Executor failures must propagate")

    loader = {"last.execute": last}
    if not missing:
        loader["first.execute"] = first
    expected = SaltInvocationError if missing else OSError
    with pytest.raises(expected):
        await salt.utils.minion.run_executors(
            loader, ["first", "last"], {}, {}, None, [], {}
        )


@pytest.fixture
def functions(tmp_path, minion_opts):
    (tmp_path / "native.py").write_text(
        "import asyncio\n"
        "async def result():\n"
        "    await asyncio.sleep(0)\n"
        "    __context__['retcode'] = 7\n"
        "    return False\n"
        "async def fail():\n"
        "    await asyncio.sleep(0)\n"
        "    raise OSError('request failed')\n"
    )
    return salt.loader.lazy.LazyLoader([str(tmp_path)], minion_opts)


async def test_minion_worker_resolves_coroutine_before_reading_retcode(functions):
    minion = salt.minion.Minion.__new__(salt.minion.Minion)
    minion.connected = False
    minion.opts = {"grains": {}}
    result = await minion._execute_job_function(
        "native.result",
        [],
        ["direct_call"],
        {},
        {},
        functions=functions,
        executor_loader={"direct_call.execute": salt.executors.direct_call.execute},
    )
    assert result is False
    assert functions.pack["__context__"]["retcode"] == 7
    with pytest.raises(OSError, match="request failed"):
        await minion._execute_job_function(
            "native.fail",
            [],
            ["direct_call"],
            {},
            {},
            functions=functions,
            executor_loader={"direct_call.execute": salt.executors.direct_call.execute},
        )


async def test_salt_call_resolves_coroutine_before_output(functions, minion_opts):
    caller = salt.cli.caller.BaseCaller.__new__(salt.cli.caller.BaseCaller)
    caller.opts = dict(
        minion_opts, fun="native.result", arg=[], local=True, cache_jobs=False
    )
    executors = {"direct_call.execute": salt.executors.direct_call.execute}

    class Executors(dict):
        pack = {"__context__": functions.pack["__context__"]}

    caller.minion = SimpleNamespace(functions=functions, executors=Executors(executors))
    with patch("salt.utils.files.fopen"), patch("os.remove"):
        result = await caller.call()
    assert result["return"] is False
    assert result["retcode"] == 7

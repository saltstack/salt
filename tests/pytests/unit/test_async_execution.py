"""Native execution-module coroutines return values through job dispatchers."""

import asyncio
from types import SimpleNamespace

import pytest

import salt.cli.caller
import salt.executors.direct_call
import salt.loader.lazy
import salt.minion
from tests.support.mock import patch


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


def test_minion_worker_resolves_coroutine_before_reading_retcode(functions):
    minion = salt.minion.Minion.__new__(salt.minion.Minion)
    minion.connected = False
    minion.opts = {"grains": {}}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = minion._execute_job_function(
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
            minion._execute_job_function(
                "native.fail",
                [],
                ["direct_call"],
                {},
                {},
                functions=functions,
                executor_loader={
                    "direct_call.execute": salt.executors.direct_call.execute
                },
            )
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def test_salt_call_resolves_coroutine_before_output(functions, minion_opts):
    caller = salt.cli.caller.BaseCaller.__new__(salt.cli.caller.BaseCaller)
    caller.opts = dict(
        minion_opts, fun="native.result", arg=[], local=True, cache_jobs=False
    )
    executors = {"direct_call.execute": salt.executors.direct_call.execute}

    class Executors(dict):
        pack = {"__context__": functions.pack["__context__"]}

    caller.minion = SimpleNamespace(functions=functions, executors=Executors(executors))
    with patch("salt.utils.files.fopen"), patch("os.remove"):
        result = caller.call()
    assert result["return"] is False
    assert result["retcode"] == 7

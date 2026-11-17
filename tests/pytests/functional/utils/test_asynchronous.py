"""
Functional tests for salt.utils.asynchronous.SyncWrapper.
"""

import pathlib
import socket
import subprocess
import sys
import textwrap

import pytest

import salt.utils.asynchronous

pytestmark = [
    pytest.mark.skip_unless_on_linux(
        reason="The #70353 wedge has only been reproduced on Linux"
    ),
]


@pytest.fixture
def refused_port():
    """
    A local TCP port that refuses connections: bound so nothing else can
    take it, but never listening.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        yield sock.getsockname()[1]


def test_req_channel_closed_from_running_loop_does_not_wedge_gc_70353(
    tmp_path, refused_port
):
    """
    #70353: with the master down, ``Minion.handle_event`` called the
    synchronous ``_mine_send``, whose ``ReqChannel`` gave up when
    authentication timed out and was closed while the minion's loop was
    running.  ``AsyncAuth._authenticate`` and ``RequestClient._send_recv``
    were left pending on the closed wrapper loop with their ZMQ sockets
    open, and the next GC pass blocked the minion in ``zmq_ctx_term()``.

    Runs in a subprocess so a regression fails instead of hanging the test
    run.  Only Python 3.12+ strands the tasks; on older versions
    ``_target``'s orphan reaper cancels them first.
    """
    # Make the subprocess import the same salt package as this test.
    code_dir = pathlib.Path(salt.utils.asynchronous.__file__).resolve().parents[2]
    script = tmp_path / "close_from_running_loop.py"
    script.write_text(
        textwrap.dedent(
            f"""\
            import asyncio
            import faulthandler
            import gc
            import os
            import sys

            sys.path.insert(0, {str(code_dir)!r})

            import salt.channel.client
            import salt.config
            import salt.exceptions

            workdir = {str(tmp_path)!r}
            opts = salt.config.minion_config(None, minion_id="test-70353")
            opts.update(
                {{
                    "transport": "zeromq",
                    "master": "127.0.0.1",
                    "master_ip": "127.0.0.1",
                    "master_port": {refused_port},
                    "master_uri": "tcp://127.0.0.1:{refused_port}",
                    "pki_dir": os.path.join(workdir, "pki"),
                    "cachedir": os.path.join(workdir, "cache"),
                    "sock_dir": os.path.join(workdir, "sock"),
                    "extension_modules": os.path.join(workdir, "extmods"),
                    "auth_tries": 1,
                    "auth_timeout": 2,
                }}
            )
            for key in ("pki_dir", "cachedir", "sock_dir", "extension_modules"):
                os.makedirs(opts[key], exist_ok=True)


            async def main():
                loop = asyncio.get_running_loop()
                # The body of the synchronous Minion._mine_send, called from
                # a coroutine as Minion.handle_event does.
                with salt.channel.client.ReqChannel.factory(opts) as channel:
                    try:
                        channel.send({{"cmd": "_mine"}}, timeout=2, tries=1)
                    except salt.exceptions.SaltClientError:
                        pass
                stranded = sorted(
                    obj.get_coro().__qualname__
                    for obj in gc.get_objects()
                    if isinstance(obj, asyncio.Task)
                    and not obj.done()
                    and obj.get_loop() is not loop
                )
                print(f"stranded tasks: {{stranded}}", flush=True)
                faulthandler.dump_traceback_later(20, exit=True)
                gc.collect()
                faulthandler.cancel_dump_traceback_later()
                print("gc.collect() returned", flush=True)


            asyncio.run(main())
            """
        )
    )
    try:
        ret = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            cwd=str(tmp_path),
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"subprocess did not finish: {exc}")
    output = f"stdout:\n{ret.stdout}\nstderr:\n{ret.stderr}"
    assert "stranded tasks: []" in ret.stdout, output
    assert ret.returncode == 0, output
    assert "gc.collect() returned" in ret.stdout, output

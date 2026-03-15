from __future__ import annotations

import asyncio.events
import asyncio.streams
import asyncio.subprocess
import contextlib
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import TYPE_CHECKING, TextIO, cast

from . import logs

log = logging.getLogger(__name__)


class Process(asyncio.subprocess.Process):  # noqa: D101
    def __init__(
        self,
        *args,
        timeout_secs: int | timedelta | None = None,
        no_output_timeout_secs: int | timedelta | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        timeout_task = None
        if isinstance(timeout_secs, int):
            assert timeout_secs >= 1  # noqa: S101
            timeout_secs = timedelta(seconds=timeout_secs)
        elif isinstance(timeout_secs, timedelta):
            assert timeout_secs >= timedelta(seconds=1)  # noqa: S101
        if timeout_secs is not None:
            timeout_task = self._loop.create_task(  # type: ignore[attr-defined]
                self._check_timeout()
            )
        self._timeout_secs = timeout_secs
        self._timeout_task = timeout_task
        no_output_timeout_task = None
        if isinstance(no_output_timeout_secs, int):
            assert no_output_timeout_secs >= 1  # noqa: S101
            no_output_timeout_secs = timedelta(seconds=no_output_timeout_secs)
        elif isinstance(no_output_timeout_secs, timedelta):
            assert no_output_timeout_secs >= timedelta(seconds=1)  # noqa: S101
        if no_output_timeout_secs is not None:
            no_output_timeout_task = self._loop.create_task(  # type: ignore[attr-defined]
                self._check_no_output_timeout()
            )
        self._no_output_timeout_secs = no_output_timeout_secs
        self._no_output_timeout_task = no_output_timeout_task

    async def _check_timeout(self) -> None:
        try:
            if TYPE_CHECKING:
                assert self._timeout_secs
            await asyncio.sleep(self._timeout_secs.seconds)
            try:
                self.terminate()
                log.warning(
                    "The command has been running for more than %s second(s). "
                    "Terminating process.",
                    self._timeout_secs.seconds,
                )
            except ProcessLookupError:
                pass
        except asyncio.CancelledError:
            pass

    async def _cancel_timeout_task(self) -> None:
        task = self._timeout_task
        if task is None:
            return
        self._timeout_task = None
        if task.done():
            return
        if not task.cancelled():
            task.cancel()
        await task

    async def _check_no_output_timeout(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self._protocol._last_write = now  # type: ignore[attr-defined]
        try:
            while self.returncode is None:
                await asyncio.sleep(1)
                last_write = self._protocol._last_write  # type: ignore[attr-defined]
                if TYPE_CHECKING:
                    assert self._no_output_timeout_secs
                if last_write + self._no_output_timeout_secs < now:
                    try:
                        self.terminate()
                        log.warning(
                            "No output on has been seen for over %s second(s). "
                            "Terminating process.",
                            self._no_output_timeout_secs.seconds,
                        )
                    except ProcessLookupError:
                        pass
                    break
        except asyncio.CancelledError:
            pass

    async def _cancel_no_output_timeout_task(self) -> None:
        task = self._no_output_timeout_task
        if task is None:
            return
        self._no_output_timeout_task = None
        if task.done():
            return
        if not task.cancelled():
            task.cancel()
        await task

    async def wait(self) -> int:
        """
        Wait until the process exit and return the process return code.
        """
        retcode = await super().wait()
        await self._cancel_timeout_task()
        await self._cancel_no_output_timeout_task()
        return retcode


class SubprocessStreamProtocol(
    asyncio.subprocess.SubprocessStreamProtocol
):  # noqa: D101
    def __init__(self, *args, capture: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._capture: bool = capture
        self._last_write: datetime | None = None

    def pipe_data_received(
        self, fd: int, data: bytes | bytearray | str
    ) -> None:  # noqa: D102
        self._last_write = datetime.now(tz=timezone.utc)
        if self._capture:
            super().pipe_data_received(fd, data)
            return
        if isinstance(data, (bytes, bytearray)):
            decoded_data = data.decode("utf-8")
        else:
            decoded_data = data
        if logs.include_timestamps() or "CI" in os.environ:
            if not decoded_data.strip():
                return
            if fd == 1:
                log.stdout(decoded_data)  # type: ignore[attr-defined]
            else:
                log.stderr(decoded_data)  # type: ignore[attr-defined]
        else:
            if fd == 1:  # noqa: PLR5501
                sys.stdout.write(decoded_data)
                sys.stdout.flush()
            else:
                sys.stderr.write(decoded_data)
                sys.stderr.flush()


async def _create_subprocess_exec(
    program: str,
    *args: str,
    stdin: TextIO | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
    limit: int = asyncio.streams._DEFAULT_LIMIT,  # type: ignore[attr-defined]
    timeout_secs: int | None = None,
    no_output_timeout_secs: int | None = None,
    capture: bool = False,
    **kwds,
) -> Process:
    def protocol_factory() -> SubprocessStreamProtocol:
        return SubprocessStreamProtocol(limit=limit, loop=loop, capture=capture)

    loop = asyncio.events.get_running_loop()
    transport, protocol = await loop.subprocess_exec(
        protocol_factory,
        program,
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        **kwds,
    )
    return Process(
        transport,
        protocol,
        loop,
        timeout_secs=timeout_secs,
        no_output_timeout_secs=no_output_timeout_secs,
    )


def _handle_signal(proc: Process, sig: signal.Signals) -> None:
    if sig in proc._handled_signals:  # type: ignore[attr-defined]
        log.info("\nCaught %s again, killing the process ...", sig.name)
        proc.kill()
        return
    log.info(
        "\nCaught %(signame)s, terminating process ....\n"
        "Send %(signame)s again to kill the process.",
        extra={"signame": sig.name},
    )
    proc._handled_signals.append(sig)  # type: ignore[attr-defined]
    proc.terminate()


async def _subprocess_run(
    future: asyncio.Future[subprocess.CompletedProcess[bytes]],
    cmdline: list[str] | tuple[str, ...],
    timeout_secs: int | None = None,
    no_output_timeout_secs: int | None = None,
    capture: bool = False,
    interactive: bool = False,
    **kwargs,
) -> None:
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE
    if interactive is False:
        # Run in a separate program group
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["preexec_fn"] = os.setpgrp
    proc = await _create_subprocess_exec(
        *cmdline,
        stdout=stdout,
        stderr=stderr,
        stdin=sys.stdin,
        limit=1,
        timeout_secs=timeout_secs,
        no_output_timeout_secs=no_output_timeout_secs,
        capture=capture,
        **kwargs,
    )
    proc._handled_signals = []  # type: ignore[attr-defined]
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, signame)
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, partial(_handle_signal, proc, sig))

    proc_stdout, proc_stderr = await asyncio.shield(proc.communicate())
    if TYPE_CHECKING:
        assert proc.returncode
    returncode: int = proc.returncode
    result: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=cmdline,
        stdout=proc_stdout,
        stderr=proc_stderr,
        returncode=returncode,
    )
    future.set_result(result)


def run(
    *cmdline: str,
    check: bool = True,
    timeout_secs: int | None = None,
    no_output_timeout_secs: int | None = None,
    capture: bool = False,
    interactive: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess[bytes]:
    """
    Run a command.
    """
    loop = asyncio.new_event_loop()
    future = loop.create_future()
    try:
        loop.run_until_complete(
            _subprocess_run(
                future=future,
                cmdline=cmdline,
                timeout_secs=timeout_secs,
                no_output_timeout_secs=no_output_timeout_secs,
                capture=capture,
                interactive=interactive,
                **kwargs,
            )
        )
        result = future.result()
        if check is True:
            result.check_returncode()
        return cast(subprocess.CompletedProcess[bytes], result)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

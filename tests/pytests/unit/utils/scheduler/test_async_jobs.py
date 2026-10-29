"""Scheduled coroutine results must be awaited before reporting the job."""

import asyncio
import queue

import pytest

from tests.support.mock import MagicMock, patch


@pytest.fixture
def async_job(schedule):
    schedule.opts.update(transport="tcp", __role="minion")
    functions = MagicMock()
    functions._dunder_salt = None
    functions.pack = {"__context__": {}}
    schedule.functions = functions
    event = MagicMock()
    with patch("salt.loader.minion_mods", return_value=functions), patch(
        "salt.loader.utils"
    ), patch("salt.loader.returners", return_value={}), patch(
        "salt.utils.event.get_event", return_value=event
    ), patch(
        "salt.utils.files.fopen"
    ), patch(
        "os.unlink"
    ):
        yield schedule, functions, event


@pytest.mark.parametrize("fails", [False, True])
async def test_scheduled_coroutine_is_awaited_before_return_event(async_job, fails):
    schedule, functions, event = async_job
    finished = []

    async def execute():
        await asyncio.sleep(0)
        finished.append(True)
        if fails:
            raise OSError("request failed")
        functions.pack["__context__"]["retcode"] = 7
        return False

    functions.__contains__.return_value = True
    functions.__getitem__.return_value = execute
    await schedule.handle_func(False, "test.async_job", {"name": "async_job"})

    assert finished == [True]
    load, tag = event.fire_event.call_args.args
    assert tag == "__schedule_return"
    assert load["retcode"] == (254 if fails else 7)
    assert load["success"] is (not fails)
    assert load["return"] == (
        "Unhandled exception running test.async_job" if fails else False
    )


async def test_inline_scheduled_job_runs_on_the_existing_loop(async_job):
    schedule, functions, _ = async_job
    schedule.opts["run_schedule_jobs_in_background"] = False
    started = asyncio.Event()
    release = asyncio.Event()
    loops = []

    async def execute():
        loops.append(asyncio.get_running_loop())
        started.set()
        await release.wait()
        return True

    functions.__contains__.return_value = True
    functions.__getitem__.return_value = execute
    task = asyncio.create_task(
        schedule._run_job("test.async_job", {"name": "async_job", "return_job": False})
    )
    try:
        await started.wait()
        assert loops == [asyncio.get_running_loop()]
        assert not task.done()
        release.set()
        await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_scheduled_worker_runs_native_coroutines(async_job):
    schedule, functions, event = async_job

    async def execute():
        await asyncio.sleep(0)
        return True

    functions.__contains__.return_value = True
    functions.__getitem__.return_value = execute
    schedule._run_job_in_worker(False, "test.async_job", {"name": "async_job"})
    assert event.fire_event.call_args.args[0]["return"] is True


async def test_background_thread_finishes_coroutine_before_reporting_result(async_job):
    schedule, functions, event = async_job
    schedule.opts.update(multiprocessing=False, run_schedule_jobs_in_background=True)
    results = queue.Queue()

    async def execute():
        await asyncio.sleep(0)
        results.put(False)
        return False

    functions.__contains__.return_value = True
    functions.__getitem__.return_value = execute
    await schedule._run_job("test.async_job", {"name": "async_job"})
    thread = schedule._subprocess_list.processes[0]
    await asyncio.to_thread(thread.join, 5)
    assert not thread.is_alive()
    assert results.get_nowait() is False
    assert event.fire_event.call_args.args[0]["return"] is False

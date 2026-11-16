"""
Sub-second dispatch variants of the #70580 regression test.

The PR author attributes failures at sub-ms dispatch spacing to the
``Minion.__init__`` queue-lock stomp. On Linux (fork) that code only runs
at daemon startup -- per-job subprocesses inherit the Minion instance
via ``instance=self`` (salt/minion.py:3216-3227), so Minion.__init__ does
NOT re-run per job. This variant file drives the same three-run scenario
at 50ms and 1ms spacing to observe what, if anything, breaks.
"""

import os
import sys
import time

import pytest

import salt.utils.files
import salt.utils.state


@pytest.fixture(scope="module")
def stamp_script(tmp_path_factory):
    base = tmp_path_factory.mktemp("queue_int_subsec")
    script = base / "stamp.py"
    with salt.utils.files.fopen(script, "w", encoding="utf-8") as fp_:
        fp_.write(
            "import sys, time\n"
            "log, label, hold = sys.argv[1], sys.argv[2], float(sys.argv[3])\n"
            "def stamp(tag):\n"
            "    with open(log, 'a') as fp:\n"
            "        fp.write(f'{label} {tag} {time.time()}\\n')\n"
            "stamp('start')\n"
            "time.sleep(hold)\n"
            "stamp('end')\n"
        )
    return script, base / "stamp.log"


def _read_stamps(log):
    stamps = {}
    if not log.exists():
        return stamps
    with salt.utils.files.fopen(log, "r") as fp_:
        for line in fp_:
            parts = line.split()
            if len(parts) != 3:
                continue
            label, tag, when = parts
            stamps.setdefault(label, {})[tag] = float(when)
    return stamps


def _assert_no_overlap(intervals):
    assert (
        intervals and len(intervals) > 1
    ), "Overlap cannot be determined. Less than 2 tuples are available for comparison."
    sorted_intervals = sorted(intervals)
    for i in range(len(sorted_intervals) - 1):
        curr_end = sorted_intervals[i][1]
        next_start = sorted_intervals[i + 1][0]
        assert (
            curr_end <= next_start
        ), f"Two state runs overlapped. Job 1 interval: {i}. Job 2 interval: {i + 1}"


@pytest.mark.slow_test
@pytest.mark.parametrize("dispatch_sleep", [0.05, 0.001])
def test_queue_int_three_concurrent_runs_subsec(
    salt_cli, salt_minion, stamp_script, dispatch_sleep
):
    """
    Same scenario as test_queue_int_three_concurrent_runs_do_not_deadlock_70580
    but with sub-second inter-dispatch spacing (50ms, 1ms).
    """
    script, log = stamp_script
    labels = (
        f"a{int(dispatch_sleep*1000)}",
        f"b{int(dispatch_sleep*1000)}",
        f"c{int(dispatch_sleep*1000)}",
    )
    state_queue_dir = salt.utils.state.state_queue_dir(salt_minion.config)
    if log.exists():
        log.unlink()
    # Clean any residue from previous parametrize iteration
    if os.path.exists(state_queue_dir):
        for fn in os.listdir(state_queue_dir):
            try:
                os.remove(os.path.join(state_queue_dir, fn))
            except OSError:
                pass

    jids = []
    try:
        for label in labels:
            ret = salt_cli.run(
                "state.single",
                "cmd.run",
                f"name={sys.executable} {script} {log} {label} 6",
                "queue=10",
                "--async",
                minion_tgt=salt_minion.id,
            )
            assert ret.returncode == 0, f"async dispatch failed: {ret}"
            jid = ret.stdout.strip().split()[-1]
            assert jid.isdigit(), f"unexpected async stdout: {ret.stdout!r}"
            jids.append(jid)
            time.sleep(dispatch_sleep)

        deadline = time.time() + 60
        completed = False
        while time.time() < deadline:
            stamps = _read_stamps(log)
            if len(stamps) == len(labels) and all("end" in s for s in stamps.values()):
                completed = True
                break
            time.sleep(1)

        stamps = _read_stamps(log)
        if not completed:
            running = salt_cli.run("saltutil.running", minion_tgt=salt_minion.id)
            leftover = []
            if os.path.exists(state_queue_dir):
                leftover = os.listdir(state_queue_dir)
            pytest.fail(
                f"queue=<int> runs did not all complete at spacing={dispatch_sleep}s.\n"
                f"  dispatched jids={jids}\n"
                f"  stamps={stamps}\n"
                f"  running={running.stdout}\n"
                f"  state_queue_dir leftover={leftover}\n"
            )

        _assert_no_overlap([(s["start"], s["end"]) for s in stamps.values()])

        if os.path.exists(state_queue_dir):
            leftover = [f for f in os.listdir(state_queue_dir) if f.isdigit()]
            assert not leftover, f"queue flag files left behind: {leftover}"
    finally:
        for jid in jids:
            salt_cli.run("saltutil.kill_job", jid, minion_tgt=salt_minion.id)
        if os.path.exists(state_queue_dir):
            for fn in os.listdir(state_queue_dir):
                try:
                    os.remove(os.path.join(state_queue_dir, fn))
                except OSError:
                    pass

"""
Unit tests for the threaded job runners in ``salt.metaproxy.proxy`` and
``salt.metaproxy.deltaproxy`` (``thread_return`` and ``thread_multi_return``).

#61830: with ``multiprocessing: False`` every job thread shares one
``minion_instance``. A concurrent module reload (``sys.reload_modules``,
``saltutil.refresh_modules``, a sync) rebinds ``minion_instance.functions`` to
a new loader generation whose ``__context__`` is a fresh dict. A job function
writes its retcode into the ``__context__`` of the loader it ran under, so a
job runner that re-reads the shared ``minion_instance.functions`` attribute
for the retcode after such a rebind reads the wrong context: a failed job is
reported as success, or a sibling's retcode leaks into this job.

These tests call the real metaproxy functions with a minimal stand-in for the
proxy minion instance (only the attributes the functions read), a real
execution-module loader and the real ``test.retcode`` function. The sibling
reload is forced into the job's write->read window:

- ``thread_return`` runs the function through ``minion_instance.executors``,
  so an injected executor runs the real ``direct_call`` executor and then
  rebinds ``minion_instance.functions`` before returning;
- ``thread_multi_return`` calls the function directly and never consults the
  executors, so the job loader's ``test.retcode`` entry is replaced with a
  wrapper that runs the real function (still called through, and so writing
  into, the job's loader) and then rebinds ``minion_instance.functions``.

An executor can write the retcode itself: with ``sudo_user`` set, the sudo
executor runs ``sudo -u <user> salt-call ...`` and writes the retcode into the
``__context__`` of the loader generation the executor belongs to. So
``thread_return`` must also capture ``minion_instance.executors`` at job
start, together with the functions loader it reads the retcode from. The
executor-ownership test rebinds both attributes to a new generation after the
job has started but before its executor lookup.
"""

import functools
import types

import pytest

import salt.defaults.exitcodes
import salt.loader
import salt.metaproxy.deltaproxy
import salt.metaproxy.proxy
import salt.minion
import salt.utils.json
import salt.utils.path
from tests.support.mock import patch

METAPROXIES = pytest.mark.parametrize(
    "metaproxy",
    [salt.metaproxy.proxy, salt.metaproxy.deltaproxy],
    ids=["proxy", "deltaproxy"],
)

# (this job's retcode, retcode a sibling job writes into the reloaded loader
# or None when nothing ran there yet, expected delivered retcode)
RETCODE_CASES = pytest.mark.parametrize(
    "code,sibling_code,expected",
    [
        # A failed job must be delivered as failed. Pre-fix the read landed on
        # the reloaded loader's empty __context__ and reported EX_OK.
        (42, None, 42),
        # Inverse must-not: a passing job stays passing.
        (0, None, salt.defaults.exitcodes.EX_OK),
        # Inverse must-not: a failing sibling's retcode written into the
        # reloaded loader must not leak into this passing job.
        (0, 7, salt.defaults.exitcodes.EX_OK),
    ],
    ids=["failed-job-stays-failed", "passing-job-stays-passing", "no-sibling-leak"],
)


def _sudo_stdout(retcode):
    # What ``salt-call --out json --metadata -- test.retcode <n>`` prints.
    return salt.utils.json.dumps(
        {"local": {"fun": "test.retcode", "return": True, "retcode": retcode}}
    )


# (this job's test.retcode argument, what cmd.run_all returns for the
# ``sudo -u <user> salt-call ...`` command, expected delivered retcode,
# expected delivered return)
SUDO_CASES = pytest.mark.parametrize(
    "code,cmd_ret,expected_retcode,expected_return",
    [
        # salt-call ran the job under sudo and the job failed; the sudo
        # executor takes the retcode from salt-call's metadata.
        (
            42,
            {"pid": 4242, "retcode": 0, "stdout": _sudo_stdout(42), "stderr": ""},
            42,
            True,
        ),
        # sudo itself failed, salt-call never ran; the sudo executor takes
        # sudo's exit code.
        (
            42,
            {
                "pid": 4242,
                "retcode": 1,
                "stdout": "",
                "stderr": "sudo: a password is required",
            },
            1,
            "sudo: a password is required",
        ),
        # Inverse must-not: a job that passed under sudo stays passing.
        (
            0,
            {"pid": 4242, "retcode": 0, "stdout": _sudo_stdout(0), "stderr": ""},
            salt.defaults.exitcodes.EX_OK,
            True,
        ),
    ],
    ids=["job-failed-under-sudo", "sudo-failed", "passing-job-stays-passing"],
)


@pytest.fixture
def proxy_opts(minion_opts):
    minion_opts["multiprocessing"] = False
    minion_opts["grains"] = {}
    minion_opts["pillar"] = {}
    return minion_opts


@pytest.fixture
def proc_dir(tmp_path):
    path = tmp_path / "proc"
    path.mkdir()
    return str(path)


@pytest.fixture(autouse=True)
def _keep_proctitle():
    # The job runners append to the process title; keep the test runner's
    # title untouched.
    with patch("salt.utils.process.appendproctitle"):
        yield


def _minion_instance(opts, proc_dir, functions, executors, delivered):
    """
    Only the attributes thread_return / thread_multi_return read from the
    proxy minion instance.
    """
    return types.SimpleNamespace(
        opts=opts,
        proc_dir=proc_dir,
        functions=functions,
        executors=executors,
        module_executors=[],
        function_errors={},
        returners={},
        connected=True,
        _return_pub=lambda ret, timeout=None: delivered.append(ret),
        _return_retry_timer=lambda: 1,
    )


def _sibling_reload(opts, minion_instance, sibling_code, state):
    """
    A concurrent module reload: rebind minion_instance.functions to a new
    loader generation, optionally with a sibling job having already run (and
    written its retcode) on it.
    """
    sibling_loader = salt.loader.minion_mods(opts)
    if sibling_code is not None:
        sibling_loader["test.retcode"](sibling_code)
    minion_instance.functions = sibling_loader
    state["sibling_loader"] = sibling_loader


def _assert_distinct_loaders(job_loader, state):
    # The reload really produced a loader that does not share this job's
    # __context__; otherwise the test would prove nothing.
    assert state.get("sibling_loader") is not None, "sibling reload never fired"
    assert state["sibling_loader"] is not job_loader
    assert (
        state["sibling_loader"].pack["__context__"]
        is not job_loader.pack["__context__"]
    )


@METAPROXIES
@RETCODE_CASES
def test_metaproxy_thread_return_retcode_owns_captured_loader_61830(
    metaproxy, proxy_opts, proc_dir, code, sibling_code, expected
):
    """
    #61830: thread_return must read the retcode from the loader the job's
    function ran under, not from minion_instance.functions after a concurrent
    reload rebound it.
    """
    job_loader = salt.loader.minion_mods(proxy_opts)
    real_executors = salt.loader.executors(proxy_opts, functions=job_loader)
    delivered = []
    state = {}

    def racing_direct_call(opts, data, func, args, kwargs):
        # The real executor runs the real function (which writes its retcode
        # into job_loader's __context__); the sibling reload lands before the
        # executor hands the result back to thread_return.
        result = real_executors["direct_call.execute"](opts, data, func, args, kwargs)
        _sibling_reload(proxy_opts, minion_instance, sibling_code, state)
        return result

    minion_instance = _minion_instance(
        proxy_opts,
        proc_dir,
        job_loader,
        {"direct_call.execute": racing_direct_call},
        delivered,
    )
    data = {
        "jid": f"20260101000000{code:06d}",
        "fun": "test.retcode",
        "arg": [code],
        "ret": "",
    }

    metaproxy.thread_return(salt.minion.ProxyMinion, minion_instance, proxy_opts, data)

    _assert_distinct_loaders(job_loader, state)
    # The job's function wrote its retcode into the loader it ran under.
    assert job_loader.pack["__context__"]["retcode"] == code
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["retcode"] == expected
    assert ret["success"] is (expected == salt.defaults.exitcodes.EX_OK)


@METAPROXIES
@RETCODE_CASES
def test_metaproxy_thread_multi_return_retcode_owns_captured_loader_61830(
    metaproxy, proxy_opts, proc_dir, code, sibling_code, expected
):
    """
    #61830, multi-function path: thread_multi_return must read each
    function's retcode from the loader that function ran under, not from
    minion_instance.functions after a concurrent reload rebound it.
    """
    job_loader = salt.loader.minion_mods(proxy_opts)
    # The loader's call wrapper looks its target up by name on every call, so
    # the replacement entry below must call the raw module function.
    real_retcode = job_loader["test.retcode"].func
    delivered = []
    state = {}

    @functools.wraps(real_retcode)
    def racing_retcode(*args, **kwargs):
        # Called through job_loader, so the real test.retcode writes the
        # retcode into job_loader's __context__; the sibling reload lands
        # before thread_multi_return reads it back.
        result = real_retcode(*args, **kwargs)
        _sibling_reload(proxy_opts, minion_instance, sibling_code, state)
        return result

    job_loader["test.retcode"] = racing_retcode
    minion_instance = _minion_instance(proxy_opts, proc_dir, job_loader, {}, delivered)
    data = {
        "jid": f"20260101000000{code:06d}",
        "fun": ["test.retcode"],
        "arg": [[code]],
        "ret": "",
    }

    metaproxy.thread_multi_return(
        salt.minion.ProxyMinion, minion_instance, proxy_opts, data
    )

    _assert_distinct_loaders(job_loader, state)
    # The job's function wrote its retcode into the loader it ran under.
    assert job_loader.pack["__context__"]["retcode"] == code
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["retcode"]["test.retcode"] == expected
    assert ret["success"]["test.retcode"] is (expected == salt.defaults.exitcodes.EX_OK)


def _sudo_generation(opts, cmd_ret, calls):
    """
    One loader generation the way gen_modules() builds it: an execution-module
    loader and an executor loader sharing one __context__ dict. cmd.run_all is
    faked for the ``sudo -u <user> salt-call ...`` command the sudo executor
    runs through ``__salt__["cmd.run_all"]``.
    """
    context = {}
    functions = salt.loader.minion_mods(opts, context=context)

    def run_all(cmd, **kwargs):
        calls.append(cmd)
        return dict(cmd_ret)

    functions["cmd.run_all"] = run_all
    executors = salt.loader.executors(opts, functions=functions, context=context)
    return functions, executors


@METAPROXIES
@SUDO_CASES
def test_metaproxy_thread_return_executor_owns_captured_generation_61830(
    metaproxy, proxy_opts, proc_dir, code, cmd_ret, expected_retcode, expected_return
):
    """
    #61830, executor ownership: thread_return reads the retcode from the
    functions loader it captured at job start, so it must also run the job
    through the executors of that same generation. With ``sudo_user`` set the
    sudo executor writes the retcode into the __context__ of the generation
    the executor belongs to.

    A concurrent reload rebinding minion_instance.functions and
    minion_instance.executors after the job has started but before its
    executor lookup (forced here from the job's own "Executors list ..." log
    call, ``log.trace`` in proxy and ``log.debug`` in deltaproxy) made a
    runner that captured only the functions loader (the first version of
    this fix) run the new
    generation's sudo executor: the retcode went into that generation's
    __context__ and the job read its own, freshly reset one, so a failed job
    was reported as success.

    Stock 3008.x passes this by design: it looks the executors up and reads
    the retcode back through minion_instance at the time of use, so after
    the rebind its write and its read both land in the new generation. Its
    own gap is covered by
    test_metaproxy_thread_return_retcode_owns_captured_loader_61830.
    """
    proxy_opts["sudo_user"] = "saltdev"
    calls = []
    job_loader, job_executors = _sudo_generation(proxy_opts, cmd_ret, calls)
    new_loader, new_executors = _sudo_generation(proxy_opts, cmd_ret, calls)
    delivered = []
    state = {}
    minion_instance = _minion_instance(
        proxy_opts, proc_dir, job_loader, job_executors, delivered
    )
    real_which = salt.utils.path.which

    def reload_before_executor_lookup(real_log):
        def log_then_reload(msg, *args, **kwargs):
            if str(msg).startswith("Executors list") and not state:
                minion_instance.functions = new_loader
                minion_instance.executors = new_executors
                state["sibling_loader"] = new_loader
            return real_log(msg, *args, **kwargs)

        return log_then_reload

    def which(exe):
        # The sudo executor's __virtual__ needs sudo on the PATH as well as
        # sudo_user.
        if exe == "sudo":
            return "/usr/bin/sudo"
        return real_which(exe)

    data = {
        "jid": f"20260101000000{code:06d}",
        "fun": "test.retcode",
        "arg": [code],
        "ret": "",
    }

    with patch.object(
        metaproxy.log, "trace", reload_before_executor_lookup(metaproxy.log.trace)
    ), patch.object(
        metaproxy.log, "debug", reload_before_executor_lookup(metaproxy.log.debug)
    ), patch(
        "salt.utils.path.which", which
    ):
        metaproxy.thread_return(
            salt.minion.ProxyMinion, minion_instance, proxy_opts, data
        )

    _assert_distinct_loaders(job_loader, state)
    # The job really ran through the sudo executor, exactly once, with this
    # job's argument.
    assert len(calls) == 1
    assert calls[0][:3] == ["sudo", "-u", "saltdev"]
    assert calls[0][-1] == str(code)
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["return"] == expected_return
    assert ret["retcode"] == expected_retcode
    assert ret["success"] is (expected_retcode == salt.defaults.exitcodes.EX_OK)

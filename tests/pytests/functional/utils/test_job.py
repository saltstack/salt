import pathlib
from types import SimpleNamespace

import pytest

import salt.exceptions
import salt.returners.local_cache as local_cache
import salt.returners.multi_returner as multi_returner
import salt.utils.jid
import salt.utils.job
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def real_multi_cache(minion_opts, tmp_path):
    opts = dict(
        minion_opts,
        cachedir=str(tmp_path / "cache"),
        master_job_cache="multi_returner",
        multi_returner=["local_cache", "elasticsearch"],
        job_cache=True,
        ext_job_cache="",
        job_cache_store_endtime=True,
    )
    local_save = MagicMock(wraps=local_cache.save_load)
    local_get = MagicMock(wraps=local_cache.get_load)
    es_save = MagicMock()
    es_return = MagicMock()
    forbidden_query = MagicMock(
        side_effect=AssertionError("unexpected ES/merged query")
    )
    returners = {
        "local_cache.prep_jid": local_cache.prep_jid,
        "local_cache.save_load": local_save,
        "local_cache.get_load": local_get,
        "local_cache.returner": local_cache.returner,
        "local_cache.update_endtime": local_cache.update_endtime,
        "elasticsearch.save_load": es_save,
        "elasticsearch.returner": es_return,
        "elasticsearch.get_load": forbidden_query,
        "multi_returner.prep_jid": local_cache.prep_jid,
        "multi_returner.save_load": multi_returner.save_load,
        "multi_returner.get_load": forbidden_query,
        "multi_returner.returner": multi_returner.returner,
        "multi_returner.update_endtime": multi_returner.update_endtime,
    }
    mminion = SimpleNamespace(returners=returners)
    with patch.dict(local_cache.__dict__, {"__opts__": opts}), patch.dict(
        multi_returner.__dict__, {"__opts__": opts}
    ), patch.object(multi_returner, "MMINION", mminion):
        yield opts, mminion, local_save, local_get, es_save, es_return, forbidden_query


@pytest.mark.parametrize("existing", ["absent", "empty", "dispatch", "req"])
def test_store_job_real_multi_load_guard(real_multi_cache, existing):
    opts, mminion, local_save, local_get, es_save, es_return, query = real_multi_cache
    jid = "20261023000000000003"
    dispatch = {
        "jid": jid,
        "fun": "test.ping",
        "arg": [],
        "user": "root",
        "tgt": "minion-1",
        "tgt_type": "glob",
    }
    if existing != "req":
        local_cache.prep_jid(passed_jid=jid)
    if existing == "dispatch":
        local_cache.save_load(jid, dispatch, minions=[])
    elif existing == "empty":
        # An empty load needs independently stored targeting metadata to be
        # readable by this backend. An empty minion list keeps get_load falsey.
        local_cache.save_load(jid, {})
        local_cache.save_minions(jid, [])
    if existing != "req":
        assert local_cache.get_load(jid) == (dispatch if existing == "dispatch" else {})
    load = {
        "jid": "req" if existing == "req" else jid,
        "id": "minion-1",
        "fun": "test.echo",
        "fun_args": ["ok"],
        "return": "ok",
        "retcode": 0,
        "success": True,
    }
    if existing != "req":
        # Match the targeted runner return in test_store_job_save_load below;
        # save_load can compute and persist its minion list without a mock.
        load.update(tgt="minion-1", tgt_type="glob")
    load["cmd"] = "_return"
    salt.utils.job.store_job(opts, load, mminion=mminion)
    assert isinstance(load["jid"], str)
    jid = load["jid"]
    assert local_cache.get_load(jid) == (dispatch if existing == "dispatch" else load)
    assert local_get.call_args_list == [call(jid)] * (2 if existing == "req" else 1)
    if existing == "dispatch":
        local_save.assert_not_called()
    else:
        local_save.assert_called_once_with(jid, load, None)
    assert es_save.call_count == (2 if existing == "req" else 1)
    for saved in es_save.call_args_list:
        assert saved.args == (jid, load, None)
    if existing == "req":
        assert load["arg"] == ["ok"]
        assert load["tgt_type"] == "glob"
        assert load["tgt"] == "minion-1"
        assert salt.utils.jid.is_jid(jid)
    assert local_cache.get_jid(jid)["minion-1"] == {
        "return": "ok",
        "retcode": 0,
        "success": True,
    }
    assert local_cache.get_endtime(jid)
    es_return.assert_called_once_with(load)
    query.assert_not_called()
    job_dir = pathlib.Path(
        salt.utils.jid.jid_dir(
            jid, str(pathlib.Path(opts["cachedir"]) / "jobs"), opts["hash_type"]
        )
    )
    assert (job_dir / ".load.p").is_file()
    assert (job_dir / ".minions.p").is_file()
    assert (job_dir / "minion-1" / "return.p").is_file()
    assert (job_dir / "jid").is_file()


@pytest.mark.parametrize("existing", [False, True])
def test_store_job_direct_local_load_guard(real_multi_cache, existing):
    opts, mminion, local_save, local_get, es_save, es_return, query = real_multi_cache
    opts["master_job_cache"] = "local_cache"
    jid = "20261023000000000004"
    dispatch = {
        "jid": jid,
        "fun": "test.ping",
        "arg": [],
        "tgt": "minion-1",
        "tgt_type": "glob",
    }
    local_cache.prep_jid(passed_jid=jid)
    if existing:
        local_cache.save_load(jid, dispatch, minions=[])
    load = {
        "jid": jid,
        "id": "minion-1",
        "return": "ok",
        "cmd": "_return",
        "tgt": "minion-1",
        "tgt_type": "glob",
    }
    salt.utils.job.store_job(opts, load, mminion=mminion)
    assert local_cache.get_load(jid) == (dispatch if existing else load)
    local_get.assert_called_once_with(jid)
    if existing:
        local_save.assert_not_called()
    else:
        local_save.assert_called_once_with(jid, load)
    assert local_cache.get_jid(jid)["minion-1"] == {"return": "ok"}
    assert local_cache.get_endtime(jid)
    es_save.assert_not_called()
    es_return.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize("backend", ["local_cache", "multi_returner"])
def test_store_job_incomplete_local_cache_exception_boundary(
    real_multi_cache, backend, caplog
):
    opts, mminion, local_save, local_get, es_save, es_return, query = real_multi_cache
    opts["master_job_cache"] = backend
    jid = "20261023000000000005"
    local_cache.prep_jid(passed_jid=jid)
    # This deliberately incomplete cache is not a successful dispatch fixture:
    # without a target save_load does not persist .minions.p.
    local_cache.save_load(jid, {"jid": jid, "fun": "test.ping", "arg": []})
    load = {"jid": jid, "id": "minion-1", "return": "ok", "cmd": "_return"}
    if backend == "local_cache":
        with pytest.raises(
            salt.exceptions.CommandExecutionError, match=r"\.minions\.p does not exist$"
        ):
            salt.utils.job.store_job(opts, load, mminion=mminion)
        es_return.assert_not_called()
        assert local_cache.get_jid(jid) == {}
        assert local_cache.get_endtime(jid) is False
    else:
        with caplog.at_level("CRITICAL", logger="salt.utils.job"):
            salt.utils.job.store_job(opts, load, mminion=mminion)
        assert (
            "The specified 'multi_returner' returner threw a stack trace" in caplog.text
        )
        assert ".minions.p does not exist" in caplog.text
        assert local_cache.get_jid(jid)["minion-1"] == {"return": "ok"}
        assert local_cache.get_endtime(jid)
        es_return.assert_called_once_with(load)
    local_get.assert_called_once_with(jid)
    local_save.assert_not_called()
    es_save.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize("nocache", [False, True])
@pytest.mark.parametrize("disabled", ["job_cache", "ext_job_cache"])
def test_store_job_req_cache_disabled_keeps_real_first_load(
    real_multi_cache, nocache, disabled
):
    opts, mminion, local_save, local_get, es_save, es_return, query = real_multi_cache
    opts["job_cache"] = disabled != "job_cache"
    opts["ext_job_cache"] = "external" if disabled == "ext_job_cache" else ""
    load = {
        "jid": "req",
        "id": "minion-1",
        "return": "ok",
        "cmd": "_return",
        "nocache": nocache,
    }
    salt.utils.job.store_job(opts, load, mminion=mminion)
    assert local_cache.get_load(load["jid"]) == load
    local_save.assert_called_once_with(load["jid"], load, None)
    es_save.assert_called_once_with(load["jid"], load, None)
    local_get.assert_called_once_with(load["jid"])
    es_return.assert_not_called()
    assert local_cache.get_jid(load["jid"]) == {}
    assert local_cache.get_endtime(load["jid"]) is False
    query.assert_not_called()


def test_store_job_multi_without_local_uses_generic_save(real_multi_cache):
    opts, mminion, local_save, local_get, es_save, es_return, query = real_multi_cache
    opts["multi_returner"] = ["elasticsearch"]
    generic_save = MagicMock(wraps=multi_returner.save_load)
    mminion.returners["multi_returner.save_load"] = generic_save
    load = {
        "jid": "20261023000000000006",
        "id": "minion-1",
        "return": "ok",
        "cmd": "_return",
    }
    salt.utils.job.store_job(opts, load, mminion=mminion)
    generic_save.assert_called_once_with(load["jid"], load)
    es_save.assert_called_once_with(load["jid"], load, None)
    es_return.assert_called_once_with(load)
    local_get.assert_not_called()
    local_save.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize(
    "jid, disabled",
    [
        ("20261023000000000007", "job_cache"),
        ("20261023000000000007", "ext_job_cache"),
        ("nocache", "job_cache"),
        ("nocache", "ext_job_cache"),
        ("nocache", None),
    ],
)
def test_store_job_multi_cache_exit_does_not_write(real_multi_cache, jid, disabled):
    opts, mminion, local_save, local_get, es_save, es_return, query = real_multi_cache
    opts["job_cache"] = disabled != "job_cache"
    opts["ext_job_cache"] = "external" if disabled == "ext_job_cache" else ""
    load = {"jid": jid, "id": "minion-1", "return": "ok", "cmd": "_return"}
    salt.utils.job.store_job(opts, load, mminion=mminion)
    local_get.assert_not_called()
    local_save.assert_not_called()
    es_save.assert_not_called()
    es_return.assert_not_called()
    query.assert_not_called()
    assert local_cache.get_jid(jid) == {}
    assert local_cache.get_endtime(jid) is False


def test_store_job_save_load(minion_opts, tmp_path):
    """
    Test to ensure we create the correct files when we
    store a job in the local cache
    """
    opts = minion_opts.copy()
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    opts["ext_job_cache"] = ""
    cache_dir = pathlib.Path(opts["cachedir"], "jobs")
    master_minion = "test_master"
    load = {
        "id": master_minion,
        "tgt": master_minion,
        "jid": "20230822145508520090",
        "return": {
            "fun": "runner.test.arg",
            "jid": "20230822145508520090",
            "user": "sudo_ch3ll",
            "fun_args": ["go", "home"],
            "_stamp": "2023-08-22T14:55:08.796680",
            "return": {"args": ("go", "home"), "kwargs": {}},
            "success": True,
        },
    }
    salt.utils.job.store_job(opts, load)
    job_dir = list(list(cache_dir.iterdir())[0].iterdir())[0]
    return_p = job_dir / master_minion / "return.p"
    load_p = job_dir / ".load.p"
    jid = job_dir / "jid"
    assert return_p.is_file()
    assert load_p.is_file()
    assert jid.is_file()

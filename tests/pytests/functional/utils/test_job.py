import pathlib

import salt.utils.job


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

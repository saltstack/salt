import time

import salt.master
from tests.support.mock import MagicMock, patch


def test_fileserver_duration():
    with patch("salt.master.FileserverUpdate._do_update") as update:
        start = time.time()
        salt.master.FileserverUpdate.update(1, {}, 1)
        end = time.time()
        # Interval is equal to timeout so the _do_update method will be called
        # one time.
        update.called_once()
        # Timeout is 1 second
        assert 2 > end - start > 1


def test_mworker_pass_context():
    """
    Test of passing the __context__ to pillar ext module loader
    """
    req_channel_mock = MagicMock()
    local_client_mock = MagicMock()

    opts = {
        "req_server_niceness": None,
        "mworker_niceness": None,
        "sock_dir": "/tmp",
        "conf_file": "/tmp/fake_conf",
        "transport": "zeromq",
        "fileserver_backend": ["roots"],
        "file_client": "local",
        "pillar_cache": False,
        "state_top": "top.sls",
        "pillar_roots": {},
    }

    data = {
        "id": "MINION_ID",
        "grains": {},
        "saltenv": None,
        "pillarenv": None,
        "pillar_override": {},
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }

    test_context = {"testing": 123}

    def mworker_bind_mock():
        mworker.aes_funcs.run_func(data["cmd"], data)

    with patch("salt.client.get_local_client", local_client_mock), patch(
        "salt.master.ClearFuncs", MagicMock()
    ), patch("salt.minion.MasterMinion", MagicMock()), patch(
        "salt.utils.verify.valid_id", return_value=True
    ), patch(
        "salt.loader.matchers", MagicMock()
    ), patch(
        "salt.loader.render", MagicMock()
    ), patch(
        "salt.loader.utils", MagicMock()
    ), patch(
        "salt.loader.fileserver", MagicMock()
    ), patch(
        "salt.loader.minion_mods", MagicMock()
    ), patch(
        "salt.loader.LazyLoader", MagicMock()
    ) as loadler_pillars_mock:
        mworker = salt.master.MWorker(opts, {}, {}, [req_channel_mock])

        with patch.object(mworker, "_MWorker__bind", mworker_bind_mock), patch.dict(
            mworker.context, test_context
        ):
            mworker.run()
            assert (
                loadler_pillars_mock.call_args_list[0][1].get("pack").get("__context__")
                == test_context
            )

        loadler_pillars_mock.reset_mock()

        opts.update(
            {
                "pillar_cache": True,
                "pillar_cache_backend": "file",
                "pillar_cache_ttl": 1000,
                "cachedir": "/tmp",
            }
        )

        mworker = salt.master.MWorker(opts, {}, {}, [req_channel_mock])

        with patch.object(mworker, "_MWorker__bind", mworker_bind_mock), patch.dict(
            mworker.context, test_context
        ), patch("salt.utils.cache.CacheFactory.factory", MagicMock()):
            mworker.run()
            assert (
                loadler_pillars_mock.call_args_list[0][1].get("pack").get("__context__")
                == test_context
            )

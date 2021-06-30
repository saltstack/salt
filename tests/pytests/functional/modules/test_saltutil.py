import salt.config
import salt.loader
import salt.modules.saltutil
import salt.state
from tests.support.mock import patch


def test__get_top_file_envs(tmpdir):
    opts = salt.config.minion_config("")
    opts["master_uri"] = "tcp://127.0.0.1:11111"
    opts["pki_dir"] = tmpdir
    modules = salt.loader.minion_mods(opts, context={})
    with patch.object(
        salt.state.BaseHighState, "_BaseHighState__gen_opts"
    ) as __gen_opts:
        __gen_opts.return_value = opts
        with patch.object(salt.state.State, "_gather_pillar") as _gather_pillar:
            _gather_pillar.return_value = {}
            with patch.object(salt.state.HighState, "destroy") as mock:
                try:
                    modules["saltutil.sync_all"]()
                except Exception:
                    pass
                assert mock.called

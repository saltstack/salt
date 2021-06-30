import salt.config
import salt.loader
import salt.modules.saltutil
import salt.state
from tests.support.mock import patch


def test__get_top_file_envs(tmpdir):
    """
    Ensure we cleanup objects created by saltutil._get_top_file_envs #60449
    """
    opts = salt.config.minion_config("")
    opts["master_uri"] = "tcp://127.0.0.1:11111"
    opts["pki_dir"] = tmpdir
    modules = salt.loader.minion_mods(opts, context={})
    # Mock the __gen_opts method of HighState so it doesn't try to auth to master.
    with patch.object(
        salt.state.BaseHighState, "_BaseHighState__gen_opts"
    ) as __gen_opts:
        __gen_opts.return_value = opts
        # Mock the _gather_pillar method of State so it doesn't try to auth to master.
        with patch.object(salt.state.State, "_gather_pillar") as _gather_pillar:
            _gather_pillar.return_value = {}
            # Mock HighState.destroy to ensure it's getting called
            with patch.object(salt.state.HighState, "destroy") as mock:
                try:
                    modules["saltutil.sync_all"]()
                except Exception:
                    pass
                assert mock.called

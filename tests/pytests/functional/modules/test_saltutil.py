import salt.config
import salt.loader
import salt.modules.saltutil
import salt.state
from tests.support.mock import patch


@patch.object(salt.state.HighState, "destroy")
@patch.object(salt.state.HighState, "top_matches")
@patch.object(salt.state.HighState, "get_top")
@patch.object(salt.state.State, "_gather_pillar")
@patch("salt.utils.extmods.sync")
@patch.object(salt.state.BaseHighState, "_BaseHighState__gen_opts")
def test__get_top_file_envs(
    gen_opts, sync, gather_pillar, get_top, top_matches, destroy, tmpdir
):
    """
    Ensure we cleanup objects created by saltutil._get_top_file_envs #60449
    """
    opts = salt.config.minion_config("")
    opts["master_uri"] = "tcp://127.0.0.1:11111"
    opts["pki_dir"] = tmpdir
    modules = salt.loader.minion_mods(opts, context={})
    sync.return_value = (None, None)
    # Mock the __gen_opts method of HighState so it doesn't try to auth to master.
    gen_opts.return_value = opts
    # Mock the _gather_pillar method of State so it doesn't try to auth to master.
    gather_pillar.return_value = {}
    top_matches.return_value = {}
    modules["saltutil.sync_clouds"]()
    assert get_top.called
    # Ensure destroy is getting called
    assert destroy.called

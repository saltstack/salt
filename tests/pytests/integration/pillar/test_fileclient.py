def test_pillar_using_cp_module(salt_master, salt_minion, salt_cli, tmp_path):
    pillar_top = """
    base:
      "*":
        - my_pillar
    """
    my_pillar = """
    {{% set file_content = salt.cp.get_file_str("{}") %}}
    """.format(
        str(tmp_path / "myfile.txt")
    )
    my_file = """
    foobar
    """
    (tmp_path / "myfile.txt").write_text(my_file)
    with salt_master.pillar_tree.base.temp_file("top.sls", pillar_top):
        with salt_master.pillar_tree.base.temp_file("my_pillar.sls", my_pillar):
            with salt_master.pillar_tree.base.temp_file("my_pillar.sls", my_pillar):
                ret = salt_cli.run("state.apply", minion_tgt=salt_minion.id)
                assert ret.returncode == 1
                assert (
                    ret.json["no_|-states_|-states_|-None"]["comment"]
                    == "No states found for this minion"
                )

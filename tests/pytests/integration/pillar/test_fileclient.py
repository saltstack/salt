def test_pillar_using_cp_module(salt_master, salt_minion, salt_cli, tmp_path):
    pillar_top = """
    base:
      "*":
        - my_pillar
    """
    my_file = tmp_path / "my_file.txt"
    my_file.write_text("foobar")
    my_pillar = f"""
    {{%- set something = salt['cp.get_file_str']("{str(my_file)}") %}}
    file_content: {{{{ something }}}}
    """
    with salt_master.pillar_tree.base.temp_file("top.sls", pillar_top):
        with salt_master.pillar_tree.base.temp_file("my_pillar.sls", my_pillar):

            ret = salt_cli.run("saltutil.pillar_refresh", minion_tgt=salt_minion.id)
            assert ret.returncode == 0

            pillar_ret = salt_cli.run(
                "pillar.item", "file_content", minion_tgt=salt_minion.id
            )
            assert pillar_ret.returncode == 0
            assert '"file_content": "foobar"' in pillar_ret.stdout

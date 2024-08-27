def test_pillar_using_http_query(salt_master, salt_minion, salt_cli, tmp_path):
    pillar_top = """
    base:
      "*":
        - http_pillar_test
    """
    my_pillar = """
    {%- set something = salt['http.query']('https://raw.githubusercontent.com/saltstack/salt/master/.pre-commit-config.yaml', raise_error=False, verify_ssl=False, status=True, timeout=5).status %}
    http_query_test: {{ something }}
    """

    with salt_master.pillar_tree.base.temp_file("top.sls", pillar_top):
        with salt_master.pillar_tree.base.temp_file("http_pillar_test.sls", my_pillar):
            with salt_master.pillar_tree.base.temp_file(
                "http_pillar_test.sls", my_pillar
            ):
                ret = salt_cli.run("state.apply", minion_tgt=salt_minion.id)
                assert ret.returncode == 1
                assert (
                    ret.data["no_|-states_|-states_|-None"]["comment"]
                    == "No states found for this minion"
                )

                pillar_ret = salt_cli.run(
                    "pillar.item", "http_query_test", minion_tgt=salt_minion.id
                )
                assert pillar_ret.returncode == 0

                assert '"http_query_test": 200' in pillar_ret.stdout

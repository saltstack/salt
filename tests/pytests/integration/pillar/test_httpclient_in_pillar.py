def test_pillar_using_http_query(salt_master, salt_minion, salt_cli):
    pillar_top = """
    base:
      "*":
        - http_pillar_test
    """
    my_pillar = """
    {%- set something = salt['http.query']('https://raw.githubusercontent.com/saltstack/salt/master/.pre-commit-config.yaml', raise_error=False, verify_ssl=False, status=True, timeout=15).status %}
    http_query_test: {{ something }}
    """

    with salt_master.pillar_tree.base.temp_file("top.sls", pillar_top):
        with salt_master.pillar_tree.base.temp_file("http_pillar_test.sls", my_pillar):

            # We may need this for the following pillar.item to work
            ret = salt_cli.run("saltutil.pillar_refresh", minion_tgt=salt_minion.id)
            assert ret.returncode == 0

            pillar_ret = salt_cli.run(
                "pillar.item", "http_query_test", minion_tgt=salt_minion.id
            )
            assert pillar_ret.returncode == 0
            assert '"http_query_test": 200' in pillar_ret.stdout

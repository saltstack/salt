import time


def test_reauth(salt_master_factory, event_listener):
    """
    Validate non of our platform need to re-authenticate when runing a job with
    multiprocessing=True.
    """
    sls_name = "issue-64941"
    sls_contents = """
    custom_test_state:
      test.configurable_test_state:
        - name: example
        - changes: True
        - result: True
        - comment: "Nothing has actually been changed"
    """
    events = []

    def handler(data):
        events.append(data)

    event_listener.register_auth_event_handler("test_reauth-master", handler)
    master = salt_master_factory.salt_master_daemon(
        "test_reauth-master",
        overrides={"log_level": "info"},
    )
    sls_tempfile = master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    minion = master.salt_minion_daemon(
        "test_reauth-minion",
        overrides={"log_level": "info"},
    )
    cli = master.salt_cli()
    start_time = time.time()
    with master.started(), minion.started():
        events = event_listener.get_events(
            [(master.id, "salt/auth")],
            after_time=start_time,
        )
        num_auth = len(events)
        proc = cli.run("state.sls", sls_name, minion_tgt="*")
        assert proc.returncode == 1
        events = event_listener.get_events(
            [(master.id, "salt/auth")],
            after_time=start_time,
        )
        assert num_auth == len(events)

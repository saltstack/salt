import time

from tests.conftest import FIPS_TESTRUN


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
        overrides={
            "log_level": "info",
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    sls_tempfile = master.state_tree.base.temp_file(f"{sls_name}.sls", sls_contents)
    minion = master.salt_minion_daemon(
        "test_reauth-minion",
        overrides={
            "log_level": "info",
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
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

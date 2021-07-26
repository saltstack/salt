import logging

log = logging.getLogger(__name__)


def test_noop_return(caplog, salt_cli, salt_minion):
    # This test relies on the customer noop returner found at
    # tests/integartion/files/returners/noop_returner.py. The path to the
    # returner must be in the master's config and 'rutests_noop' should be in
    # the master's event_return setting. The master's log level must also be
    # set to DEBUG. These config settings are found in
    # tests/pytests/conftest.py::master_factory
    with caplog.at_level(logging.DEBUG):
        salt_cli.run("test.ping", minion_tgt=salt_minion.id)
        assert "NOOP_RETURN" in caplog.text

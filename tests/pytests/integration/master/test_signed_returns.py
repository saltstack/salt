"""
Regression test for https://github.com/saltstack/salt/issues/68181.

With ``minion_sign_messages`` enabled the master must verify the minion's
return signature successfully. Previously the minion signed the return load
before ``AsyncReqChannel._package_load`` attached transport metadata
(``nonce``, ``ts``, ``tok``, ``id``), so the bytes the master re-serialized
to verify never matched what was signed and every signed return was dropped
under ``drop_messages_signature_fail``.
"""

from tests.conftest import FIPS_TESTRUN


def test_signed_minion_return_is_verified(salt_master_factory):
    """
    A signed ``test.ping`` return must be accepted by the master when
    ``drop_messages_signature_fail`` is set. If signature verification fails
    the master drops the return and the CLI never gets a result.
    """
    master = salt_master_factory.salt_master_daemon(
        "test-68181-master",
        overrides={
            "log_level": "info",
            "drop_messages_signature_fail": True,
            "require_minion_sign_messages": True,
            "fips_mode": FIPS_TESTRUN,
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    minion = master.salt_minion_daemon(
        "test-68181-minion",
        overrides={
            "log_level": "info",
            "minion_sign_messages": True,
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    cli = master.salt_cli(timeout=60)
    with master.started(), minion.started():
        ret = cli.run("--timeout=30", "test.ping", minion_tgt=minion.id)
    assert ret.returncode == 0, ret
    assert ret.data is True

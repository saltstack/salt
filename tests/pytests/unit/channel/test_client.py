import pytest

import salt.channel.client
import salt.crypt
import salt.exceptions


def test_async_methods():
    "Validate all defined async_methods and close_methods are present"
    async_classes = [
        salt.channel.client.AsyncReqChannel,
        salt.channel.client.AsyncPubChannel,
    ]
    method_attrs = [
        "async_methods",
        "close_methods",
    ]
    for cls in async_classes:
        for attr in method_attrs:
            assert hasattr(cls, attr)
            assert isinstance(getattr(cls, attr), list)
            for name in getattr(cls, attr):
                assert hasattr(cls, name)


def test_async_pub_channel_key_overwritten_by_bad_data(minion_opts, tmp_path):
    """
    Ensure AsyncPubChannel raises a SaltClientError when it encounters a bad key.

    This bug is a bit nuanced because of how the auth module uses singletons.
    We're validating an error from salt.crypt.AsyncAuth.gen_token because of
    bad key data results in a SaltClientError. This error is handled by
    Minion._connect_minion resulting error message explaining the minion
    connection failed due to bad key data.

    https://github.com/saltstack/salt/issues/68190
    """
    minion_opts["pki_dir"] = str(tmp_path)
    minion_opts["id"] = "minion"
    minion_opts["master_ip"] = "127.0.0.1"

    # This will initialize the singleton with a valid key.
    salt.channel.client.AsyncPubChannel.factory(minion_opts, crypt="aes")

    # Now we need to overwrite the bad key with the new one. When gen_token
    # gets called a SaltClientError will ge traised
    key_path = tmp_path / "minion.pem"
    key_path.chmod(0o660)
    key_path.write_text(
        "asdfiosjaoiasdfjooaisjdfo902j0ianosdifn091091jw0edw09jcr89eq79vr"
    )
    with pytest.raises(salt.exceptions.SaltClientError):
        salt.channel.client.AsyncPubChannel.factory(minion_opts, crypt="aes")


@pytest.mark.asyncio
async def test_async_pub_channel_decode_payload_drops_undecrypted_payload():
    """
    When a payload cannot be decrypted even after re-authenticating the master it
    should be discarded instead of surfacing bytes to the minion handler.
    """

    class DummyCrypticle:
        def loads(self, payload):  # pylint: disable=unused-argument
            raise salt.crypt.AuthenticationError()

    class DummyAuth:
        def __init__(self):
            self.crypticle = DummyCrypticle()
            self.authenticated = True

        async def authenticate(self):
            raise salt.crypt.AuthenticationError()

    channel = object.__new__(salt.channel.client.AsyncPubChannel)
    channel.opts = {"master_ip": "127.0.0.1"}
    channel.auth = DummyAuth()

    payload = {"enc": "aes", "load": b"ciphertext"}

    assert await channel._decode_payload(payload) is None

import pytest

import salt.states.gpg as gpg
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {gpg: {"__opts__": {"test": False}}}


@pytest.fixture
def keys_list():
    return [
        {
            "keyid": "A",
            "fingerprint": "A",
            "uids": ["Key A"],
            "created": "2010-04-01",
            "keyLength": "4096",
            "ownerTrust": "Ultimately Trusted",
            "trust": "Ultimately Trusted",
        },
        {
            "keyid": "B",
            "fingerprint": "B",
            "uids": ["Key B"],
            "created": "2017-03-06",
            "keyLength": "4096",
            "ownerTrust": "Unknown",
            "trust": "Fully Trusted",
        },
        {
            "keyid": "C",
            "fingerprint": "C",
            "uids": ["Key C"],
            "expires": "2022-06-24",
            "created": "2018-06-24",
            "keyLength": "4096",
            "ownerTrust": "Unknown",
            "trust": "Expired",
        },
        {
            "keyid": "D",
            "fingerprint": "D",
            "uids": ["Key D"],
            "created": "2018-01-18",
            "keyLength": "3072",
            "ownerTrust": "Unknown",
            "trust": "Unknown",
        },
        {
            "keyid": "E",
            "fingerprint": "E",
            "uids": ["Key E"],
            "expires": "2222-11-18",
            "created": "2019-11-20",
            "keyLength": "4096",
            "ownerTrust": "Unknown",
            "trust": "Unknown",
        },
    ]


@pytest.fixture
def gpg_list_keys(request, keys_list):
    list_ = Mock(spec="salt.modules.gpg.list_keys")
    list_.return_value = getattr(request, "param", keys_list)
    with patch.dict(gpg.__salt__, {"gpg.list_keys": list_}):
        yield list_


@pytest.fixture
def gpg_trust(request):
    trust = Mock(spec="salt.modules.gpg.trust_key")
    trust.return_value = getattr(
        request,
        "param",
        {"res": True, "message": "Setting ownership trust to Marginally"},
    )
    with patch.dict(gpg.__salt__, {"gpg.trust_key": trust}):
        yield trust


@pytest.fixture()
def gpg_receive(request):
    recv = Mock(spec="salt.modules.gpg.receive_keys")
    recv.return_value = getattr(
        request, "param", {"res": True, "message": ["Key new added to keychain"]}
    )
    with patch.dict(gpg.__salt__, {"gpg.receive_keys": recv}):
        yield recv


@pytest.mark.usefixtures("gpg_list_keys")
@pytest.mark.parametrize(
    "gpg_trust,expected",
    [
        ({"res": True, "message": "Setting ownership trust to Marginally"}, True),
        ({"res": False, "message": "KeyID A not in GPG keychain"}, False),
    ],
    indirect=["gpg_trust"],
)
def test_gpg_present_trust_change(gpg_receive, gpg_trust, expected):
    ret = gpg.present("A", trust="marginally")
    assert ret["result"] is expected
    assert bool(ret["changes"]) is expected
    gpg_trust.assert_called_once()
    gpg_receive.assert_not_called()


@pytest.mark.usefixtures("gpg_list_keys")
@pytest.mark.parametrize(
    "gpg_receive,expected",
    [
        ({"res": True, "message": ["Key new added to keychain"]}, True),
        (
            {
                "res": False,
                "message": [
                    "Something went wrong during gpg call: gpg: key new: no user ID"
                ],
            },
            False,
        ),
    ],
    indirect=["gpg_receive"],
)
def test_gpg_present_new_key(gpg_receive, gpg_trust, expected):
    ret = gpg.present("new")
    assert ret["result"] is expected
    assert bool(ret["changes"]) is expected
    gpg_receive.assert_called_once()
    gpg_trust.assert_not_called()


@pytest.mark.usefixtures("gpg_list_keys")
@pytest.mark.parametrize(
    "gpg_trust,expected",
    [
        ({"res": True, "message": "Setting ownership trust to Marginally"}, True),
        ({"res": False, "message": "KeyID A not in GPG keychain"}, False),
    ],
    indirect=["gpg_trust"],
)
@pytest.mark.usefixtures("gpg_list_keys")
def test_gpg_present_new_key_and_trust(gpg_receive, gpg_trust, expected):
    ret = gpg.present("new", trust="marginally")
    assert ret["result"] is expected
    # the key is always marked as added
    assert ret["changes"]
    gpg_receive.assert_called_once()
    gpg_trust.assert_called_once()


@pytest.mark.usefixtures("gpg_list_keys")
@pytest.mark.parametrize("key,trust", [("new", None), ("A", "marginally")])
def test_gpg_present_test_mode_no_changes(gpg_receive, gpg_trust, key, trust):
    with patch.dict(gpg.__opts__, {"test": True}):
        ret = gpg.present(key, trust=trust)
        gpg_receive.assert_not_called()
        gpg_trust.assert_not_called()
        assert ret["result"] is None
        assert ret["changes"]


@pytest.mark.usefixtures("gpg_list_keys")
def test_gpg_absent_no_changes(gpg_delete):
    ret = gpg.absent("nonexistent")
    assert ret["result"]
    assert not ret["changes"]
    gpg_delete.assert_not_called()


@pytest.mark.usefixtures("gpg_list_keys")
@pytest.mark.parametrize(
    "gpg_delete,expected",
    [
        ({"res": True, "message": ["Public key for A deleted"]}, True),
        (
            {
                "res": False,
                "message": [
                    "Secret key exists, delete first or pass delete_secret=True."
                ],
            },
            False,
        ),
    ],
    indirect=["gpg_delete"],
)
def test_gpg_absent_delete_key(gpg_delete, expected, keys_list):
    list_ = Mock(spec="salt.modules.gpg.list_keys")
    list_.side_effect = (keys_list, [x for x in keys_list if x["keyid"] != "A"])
    with patch.dict(gpg.__salt__, {"gpg.list_keys": list_}):
        ret = gpg.absent("A")
        assert ret["result"] == expected
        assert bool(ret["changes"]) == expected
        gpg_delete.assert_called_once()


@pytest.mark.usefixtures("gpg_list_keys")
def test_gpg_absent_test_mode_no_changes(gpg_delete):
    with patch.dict(gpg.__opts__, {"test": True}):
        ret = gpg.absent("A")
        gpg_delete.assert_not_called()
        assert ret["result"] is None
        assert bool(ret["changes"])


def test_gpg_absent_list_keys_with_gnupghome_and_user(gpg_list_keys):
    gnupghome = "/pls_respect_me"
    user = "imthereaswell"
    gpg.absent("nonexistent", gnupghome=gnupghome, user=user)
    gpg_list_keys.assert_called_with(gnupghome=gnupghome, user=user, keyring=None)


@pytest.mark.usefixtures("gpg_list_keys")
def test_gpg_absent_delete_key_called_with_correct_kwargs(gpg_delete):
    key = "A"
    user = "hellothere"
    gnupghome = "/pls_sir"
    gpg.absent(key, user=user, gnupghome=gnupghome)
    gpg_delete.assert_called_with(
        keyid=key, gnupghome=gnupghome, user=user, keyring=None, use_passphrase=False
    )

"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.redismod as redismod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {redismod: {}}


def test_string():
    """
    Test to ensure that the key exists in redis with the value specified.
    """
    name = "key_in_redis"
    value = "string data"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Key already set to defined value",
    }

    mock = MagicMock(return_value=value)
    with patch.dict(redismod.__salt__, {"redis.get_key": mock}):
        assert redismod.string(name, value) == ret


def test_absent():
    """
    Test to ensure key absent from redis.
    """
    name = "key_in_redis"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[False, True, True])
    mock_t = MagicMock(return_value=False)
    with patch.dict(redismod.__salt__, {"redis.exists": mock, "redis.delete": mock_t}):
        comt = "`keys` not formed as a list type"
        ret.update({"comment": comt, "result": False})
        assert redismod.absent(name, "key") == ret

        comt = "Key(s) specified already absent"
        ret.update({"comment": comt, "result": True})
        assert redismod.absent(name, ["key"]) == ret

        comt = "Keys deleted"
        ret.update({"comment": comt, "changes": {"deleted": ["key"]}})
        assert redismod.absent(name, ["key"]) == ret

        comt = "Key deleted"
        ret.update({"comment": comt, "changes": {"deleted": ["key_in_redis"]}})
        assert redismod.absent(name) == ret

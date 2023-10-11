import salt.utils.user
from salt import auth


def test_user_is_sudo():
    assert auth.AuthUser("bob").is_sudo() is False
    assert auth.AuthUser("sudo_bob").is_sudo() is True

def test_user_is_running_user():
    current_user = salt.utils.user.get_user()
    assert auth.AuthUser(salt.utils.user.get_user() + "1").is_running_user() is False
    assert auth.AuthUser(current_user).is_running_user() is True


def test_user_sudo_name():
    assert auth.AuthUser("sudo_bob").sudo_name() == "bob"

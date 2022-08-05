import salt.modules.ldap3 as ldap3
from tests.support.mock import patch


def test_change_add_value():
    with patch.object(ldap3, "modify", autospec=True):
        ldap3.change(
            "connect_spec",
            "dn",
            {"attr": ["val before"]},
            {"attr": ["val before", "val after"]},
        )
        ldap3.modify.assert_called_once_with(
            "connect_spec",
            "dn",
            [("add", "attr", ["val after"])],
        )

import salt.pillar.pillar_ldap as pillar_ldap
import salt.utils.stringutils


def test__config_returns_str():
    conf = {"foo": "bar"}
    assert pillar_ldap._config("foo", conf) == salt.utils.stringutils.to_str("bar")


def test__conf_defaults_to_none():
    conf = {"foo": "bar"}
    assert pillar_ldap._config("bang", conf) is None


def test__conf_returns_str_from_unicode_default():
    conf = {"foo": "bar"}
    default = salt.utils.stringutils.to_unicode("bam")
    assert pillar_ldap._config("bang", conf, default) == salt.utils.stringutils.to_str(
        "bam"
    )

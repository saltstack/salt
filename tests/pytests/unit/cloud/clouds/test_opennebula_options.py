"""
Documentation-tracking tests for the OpenNebula driver.

Backed by issue #64520, the docstring on ``opennebula.create`` previously
documented a ``salt-cloud -p`` invocation with trailing ``key=value`` pairs.
``salt-cloud -p`` does not parse those into per-VM overrides; it creates one
VM per positional argument. The note in the docstring must remain so the
generated docs are not misleading again.
"""

from salt.cloud.clouds import opennebula


def test_create_docstring_drops_kwarg_cli_example():
    """
    The misleading ``salt-cloud -p ... memory=... cpu=... vcpu=...`` example
    must not reappear in the create() docstring.
    """
    doc = opennebula.create.__doc__ or ""
    assert "memory=16384 cpu=2.5 vcpu=16" not in doc


def test_create_docstring_documents_override_workaround():
    """
    The replacement docstring must explain that profile-overriding kwargs
    cannot be passed to ``salt-cloud -p`` and recommend a separate profile
    or cloud map instead.
    """
    doc = opennebula.create.__doc__ or ""
    assert "trailing positional arguments are interpreted as additional" in doc
    assert "salt-cloud -p my-opennebula-profile vm_name" in doc


def test_create_docstring_documents_supported_overrides():
    """
    The supported ``vm_`` keys (``region_id``, ``memory``, ``cpu``,
    ``vcpu``) must remain documented so the driver reference page lists
    them.
    """
    doc = opennebula.create.__doc__ or ""
    for option in ("region_id", "memory", "cpu", "vcpu"):
        assert f"{option}\n" in doc, f"{option} no longer documented on create()"

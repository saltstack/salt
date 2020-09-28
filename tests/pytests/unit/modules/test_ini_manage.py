import salt.modules.ini_manage


def test_section_req():
    """
    Test the __repr__ in the _Section class
    """
    assert repr(salt.modules.ini_manage._Section("test")) == "_Section()\n{}"

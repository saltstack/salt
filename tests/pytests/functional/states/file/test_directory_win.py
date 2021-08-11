import os

import pytest
import salt.modules.win_file as win_file
import salt.states.file as file
import salt.utils.win_dacl as win_dacl
import salt.utils.win_functions as win_functions

try:
    CURRENT_USER = win_functions.get_current_user(with_domain=False)
except NameError:
    # Not a Windows Machine
    pass

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module")
def configure_loader_modules():
    return {
        file: {
            "__opts__": {"test": False},
            "__salt__": {
                "file.mkdir": win_file.mkdir,
                "file.check_perms": win_file.check_perms,
            },
        },
        win_file: {
            "__utils__": {
                "dacl.check_perms": win_dacl.check_perms,
                "dacl.set_owner": win_dacl.set_owner,
                "dacl.set_perms": win_dacl.set_perms,
            },
        },
        win_dacl: {"__opts__": {"test": False}},
    }


def test_directory_new(tmp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = os.path.join(tmp_path, "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_new_no_inherit(tmp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = os.path.join(tmp_path, "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_inheritance=False,
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    assert not win_dacl.get_inheritance(path)
    permissions = win_dacl.get_permissions(path)
    assert permissions["Inherited"] == {}


def test_directory_new_reset(tmp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = os.path.join(tmp_path, "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_perms_reset=True,
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_new_reset_no_inherit(tmp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = os.path.join(tmp_path, "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_inheritance=False,
        win_perms_reset=True,
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {},
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing(tmp_path):
    path = str(tmp_path)
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
    )
    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
    }
    # We are checking these individually because sometimes it will return an
    # owner if it is running under the Administrator account
    assert ret["changes"]["deny_perms"] == expected["deny_perms"]
    assert ret["changes"]["grant_perms"] == expected["grant_perms"]
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing_existing_user(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Everyone",
        permissions=["write_data", "write_attributes"],
        access_mode="grant",
        reset_perms=True,
    )
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
    )
    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
    }
    # We are checking these individually because sometimes it will return an
    # owner if it is running under the Administrator account
    assert ret["changes"]["deny_perms"] == expected["deny_perms"]
    assert ret["changes"]["grant_perms"] == expected["grant_perms"]
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing_no_inherit(tmp_path):
    path = str(tmp_path)
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
        win_inheritance=False,
    )
    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
        "inheritance": False,
    }
    # We are checking these individually because sometimes it will return an
    # owner if it is running under the Administrator account
    assert ret["changes"]["deny_perms"] == expected["deny_perms"]
    assert ret["changes"]["grant_perms"] == expected["grant_perms"]
    assert ret["changes"]["inheritance"] == expected["inheritance"]
    assert not win_dacl.get_inheritance(path)
    permissions = win_dacl.get_permissions(path)
    assert permissions["Inherited"] == {}


def test_directory_existing_reset(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions=["write_data", "write_attributes"],
        access_mode="deny",
        reset_perms=True,
    )
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_perms_reset=True,
    )
    expected = {
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
        "remove_perms": {
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            }
        },
    }
    # We are checking these individually because sometimes it will return an
    # owner if it is running under the Administrator account
    assert ret["changes"]["grant_perms"] == expected["grant_perms"]
    assert ret["changes"]["remove_perms"] == expected["remove_perms"]
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing_reset_no_inherit(tmp_path):
    path = str(tmp_path)
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
        win_perms_reset=True,
        win_inheritance=False,
    )

    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
        "inheritance": False,
        "remove_perms": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                },
            },
            "SYSTEM": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                },
            },
            CURRENT_USER: {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                },
            },
        },
    }
    # We are checking these individually because sometimes it will return an
    # owner if it is running under the Administrator account
    assert ret["changes"]["deny_perms"] == expected["deny_perms"]
    assert ret["changes"]["grant_perms"] == expected["grant_perms"]
    assert ret["changes"]["inheritance"] == expected["inheritance"]
    assert ret["changes"]["remove_perms"] == expected["remove_perms"]
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {},
        "Not Inherited": {
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            },
        },
    }
    assert permissions == expected

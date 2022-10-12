import os
import shutil

import pytest

try:
    import pythoncom
    from win32com.shell import shell

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries"),
]


@pytest.fixture(scope="module")
def shortcut(states):
    return states.shortcut


@pytest.fixture(scope="module")
def shortcut_mod(modules):
    return modules.shortcut


@pytest.fixture(scope="function")
def tmp_dir(tmp_path_factory):
    test_dir = tmp_path_factory.mktemp("test_dir")
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(str(test_dir))


@pytest.fixture(scope="function")
def tmp_shortcut(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("test_dir")
    tmp_shortcut = tmp_dir / "test.lnk"
    # https://docs.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw
    # http://timgolden.me.uk/python/win32_how_do_i/create-a-shortcut.html
    short_cut = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink,
        None,
        pythoncom.CLSCTX_INPROC_SERVER,
        shell.IID_IShellLink,
    )
    program = r"C:\Windows\notepad.exe"
    short_cut.SetArguments("existing arguments")
    short_cut.SetDescription("existing description")
    short_cut.SetIconLocation(program, 0)
    short_cut.SetHotkey(1601)
    short_cut.SetPath(program)
    short_cut.SetShowCmd(1)
    short_cut.SetWorkingDirectory(os.path.dirname(program))

    persist_file = short_cut.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Save(str(tmp_shortcut), 0)

    yield tmp_shortcut

    if tmp_dir.exists():
        shutil.rmtree(str(tmp_dir))


def test_present(shortcut, shortcut_mod, tmp_dir):
    file_shortcut = tmp_dir / "test.lnk"
    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
    )
    assert ret.name == str(file_shortcut)
    assert ret.changes == {}
    assert "Shortcut created" in ret.comment
    assert ret.result is True

    expected = {
        "arguments": "present arguments",
        "description": "present description",
        "hot_key": "Ctrl+Shift+D",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(file_shortcut),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Maximized",
        "working_dir": r"C:\Windows",
    }
    results = shortcut_mod.get(path=str(file_shortcut))
    assert results == expected


def test_present_existing_same(shortcut, tmp_shortcut):
    file_shortcut = str(tmp_shortcut)

    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="existing arguments",
        description="existing description",
        hot_key="Alt+Ctrl+A",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Normal",
        working_dir=r"C:\Windows",
    )

    assert ret.name == str(file_shortcut)
    assert ret.changes == {}
    assert "Shortcut already present and configured" in ret.comment
    assert ret.result is True


def test_present_existing(shortcut, tmp_shortcut):
    file_shortcut = str(tmp_shortcut)

    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
    )

    assert ret.name == str(file_shortcut)
    assert ret.changes == {}
    assert "Found existing shortcut" in ret.comment
    assert ret.result is False


def test_present_existing_force(shortcut, shortcut_mod, tmp_shortcut):
    file_shortcut = str(tmp_shortcut)

    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
        force=True,
    )

    changes = {
        "arguments": {"new": "present arguments", "old": "existing arguments"},
        "description": {"new": "present description", "old": "existing description"},
        "hot_key": {"new": "Ctrl+Shift+D", "old": "Alt+Ctrl+A"},
        "window_style": {"new": "Maximized", "old": "Normal"},
    }

    assert ret.name == str(file_shortcut)
    assert ret.changes == changes
    assert "Shortcut modified" in ret.comment
    assert ret.result is True

    expected = {
        "arguments": "present arguments",
        "description": "present description",
        "hot_key": "Ctrl+Shift+D",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(file_shortcut),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Maximized",
        "working_dir": r"C:\Windows",
    }
    results = shortcut_mod.get(path=str(file_shortcut))
    assert results == expected


def test_present_existing_backup(shortcut, shortcut_mod, tmp_shortcut):
    file_shortcut = str(tmp_shortcut)

    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
        backup=True,
    )

    changes = {
        "arguments": {"new": "present arguments", "old": "existing arguments"},
        "description": {"new": "present description", "old": "existing description"},
        "hot_key": {"new": "Ctrl+Shift+D", "old": "Alt+Ctrl+A"},
        "window_style": {"new": "Maximized", "old": "Normal"},
    }
    assert ret.name == str(file_shortcut)
    assert ret.changes == changes
    assert "Shortcut modified" in ret.comment
    assert ret.result is True

    expected = {
        "arguments": "present arguments",
        "description": "present description",
        "hot_key": "Ctrl+Shift+D",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(file_shortcut),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Maximized",
        "working_dir": r"C:\Windows",
    }
    results = shortcut_mod.get(path=str(file_shortcut))
    assert results == expected


def test_present_existing_subdir(shortcut, tmp_dir):
    file_shortcut = tmp_dir / "subdir" / "test.lnk"
    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
    )
    assert ret.name == str(file_shortcut)
    assert ret.changes == {}
    assert "Failed to create the shortcut" in ret.comment
    assert ret.result is False


def test_present_existing_subdir_make_dirs(shortcut, shortcut_mod, tmp_dir):
    file_shortcut = tmp_dir / "subdir" / "test.lnk"
    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
        make_dirs=True,
    )
    assert ret.name == str(file_shortcut)
    assert ret.changes == {}
    assert "Shortcut created" in ret.comment
    assert ret.result is True

    expected = {
        "arguments": "present arguments",
        "description": "present description",
        "hot_key": "Ctrl+Shift+D",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(file_shortcut),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Maximized",
        "working_dir": r"C:\Windows",
    }
    results = shortcut_mod.get(path=str(file_shortcut))
    assert results == expected


def test_present_test_true(shortcut, tmp_dir):
    file_shortcut = tmp_dir / "test.lnk"
    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
        test=True,
    )
    assert ret.name == str(file_shortcut)
    assert ret.changes == {}
    assert "Shortcut will be created" in ret.comment
    assert ret.result is None


def test_present_existing_test_true(shortcut, tmp_shortcut):
    file_shortcut = tmp_shortcut
    ret = shortcut.present(
        name=str(file_shortcut),
        arguments="present arguments",
        description="present description",
        hot_key="Ctrl+Shift+D",
        icon_location=r"C:\Windows\notepad.exe",
        icon_index=0,
        target=r"C:\Windows\notepad.exe",
        window_style="Maximized",
        working_dir=r"C:\Windows",
        test=True,
    )
    changes = {
        "arguments": {"new": "present arguments", "old": "existing arguments"},
        "description": {"new": "present description", "old": "existing description"},
        "hot_key": {"new": "Ctrl+Shift+D", "old": "Alt+Ctrl+A"},
        "window_style": {"new": "Maximized", "old": "Normal"},
    }
    assert ret.name == str(file_shortcut)
    assert ret.changes == changes
    assert "Shortcut will be modified" in ret.comment
    assert ret.result is None

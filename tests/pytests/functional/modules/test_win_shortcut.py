"""
Tests for win_shortcut execution module
"""
import os
import pythoncom
import shutil
import subprocess
from win32com.shell import shell

import pytest
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module")
def shortcut(modules):
    return modules.shortcut


@pytest.fixture(scope="function")
def tmp_dir(tmp_path_factory):
    test_dir = tmp_path_factory.mktemp("test_dir")
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(str(test_dir))


@pytest.fixture(scope="function")
def tmp_lnk(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("test_dir")
    tmp_lnk = tmp_dir / "test.lnk"
    # https://docs.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw
    # http://timgolden.me.uk/python/win32_how_do_i/create-a-shortcut.html
    shortcut = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink,
        None,
        pythoncom.CLSCTX_INPROC_SERVER,
        shell.IID_IShellLink,
    )
    program = r"C:\Windows\notepad.exe"
    shortcut.SetArguments("some args")
    shortcut.SetDescription("Test description")
    shortcut.SetIconLocation(program, 0)
    shortcut.SetHotkey(1601)
    shortcut.SetPath(program)
    shortcut.SetShowCmd(1)
    shortcut.SetWorkingDirectory(os.path.dirname(program))

    persist_file = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Save(str(tmp_lnk), 0)

    yield tmp_lnk

    if tmp_dir.exists():
        shutil.rmtree(str(tmp_dir))


@pytest.fixture(scope="function")
def tmp_url(shortcut, tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("test_dir")
    tmp_url = tmp_dir / "test.url"
    shortcut.create(
        path=str(tmp_url),
        target="http://www.google.com",
        window_style="",
    )
    yield tmp_url

    if tmp_dir.exists():
        shutil.rmtree(str(tmp_dir))


@pytest.fixture(scope="function")
def tmp_share():
    share_dir = r"C:\Windows\Temp"
    share_name = "TmpShare"
    create_cmd = [
        "powershell",
        "-command",
        '"New-SmbShare -Name {} -Path {}" | Out-Null'.format(
            share_name, str(share_dir)
        ),
    ]
    remove_cmd = [
        "powershell",
        "-command",
        '"Remove-SmbShare -Name {} -Force" | Out-Null'.format(share_name),
    ]
    subprocess.run(create_cmd)

    yield share_name

    subprocess.run(remove_cmd)


def test_get_missing(shortcut, tmp_dir):
    """
    Make sure that a CommandExecutionError is raised if the shortcut does NOT
    exist
    """
    fake_shortcut = tmp_dir / "fake.lnk"
    with pytest.raises(CommandExecutionError):
        shortcut.get(path=str(fake_shortcut))


def test_get_lnk(shortcut, tmp_lnk):
    expected = {
        "arguments": "some args",
        "description": "Test description",
        "hot_key": "Alt+Ctrl+A",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(tmp_lnk),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Normal",
        "working_dir": r"C:\Windows",
    }
    assert shortcut.get(path=str(tmp_lnk)) == expected


def test_get_url(shortcut, tmp_url):
    expected = {
        "arguments": "",
        "description": "",
        "hot_key": "",
        "icon_index": 0,
        "icon_location": "",
        "path": str(tmp_url),
        "target": "http://www.google.com/",
        "window_style": "",
        "working_dir": "",
    }
    assert shortcut.get(path=str(tmp_url)) == expected


def test_modify_missing(shortcut, tmp_dir):
    """
    Make sure that a CommandExecutionError is raised if the shortcut does NOT
    exist
    """
    fake_shortcut = tmp_dir / "fake.lnk"
    with pytest.raises(CommandExecutionError):
        shortcut.modify(path=str(fake_shortcut), target=r"C:\fake\path.lnk")


def test_modify_lnk(shortcut, tmp_lnk):
    expected = {
        "arguments": "different args",
        "description": "different description",
        "hot_key": "Ctrl+Shift+B",
        "icon_index": 1,
        "icon_location": r"C:\Windows\System32\calc.exe",
        "path": str(tmp_lnk),
        "target": r"C:\Windows\System32\calc.exe",
        "window_style": "Minimized",
        "working_dir": r"C:\Windows\System32",
    }
    shortcut.modify(
        path=str(tmp_lnk),
        arguments="different args",
        description="different description",
        hot_key="Ctrl+Shift+B",
        icon_index=1,
        icon_location=r"C:\Windows\System32\calc.exe",
        target=r"C:\Windows\System32\calc.exe",
        window_style="Minimized",
        working_dir=r"C:\Windows\System32",
    )
    result = shortcut.get(path=str(tmp_lnk))
    assert result == expected


def test_modify_url(shortcut, tmp_url):
    expected = {
        "arguments": "",
        "description": "",
        "hot_key": "",
        "icon_index": 0,
        "icon_location": "",
        "path": str(tmp_url),
        "target": "http://www.python.org/",
        "window_style": "",
        "working_dir": "",
    }
    shortcut.modify(
        path=str(tmp_url),
        target=r"www.python.org",
    )
    result = shortcut.get(path=str(tmp_url))
    assert result == expected


def test_create_existing(shortcut, tmp_lnk):
    with pytest.raises(CommandExecutionError):
        shortcut.create(path=str(tmp_lnk), target=r"C:\fake\path.lnk")


def test_create_lnk(shortcut, tmp_dir):
    test_link = str(os.path.join(str(tmp_dir / "test_link.lnk")))
    shortcut.create(
        path=test_link,
        arguments="create args",
        description="create description",
        hot_key="Alt+Ctrl+C",
        icon_index=0,
        icon_location=r"C:\Windows\notepad.exe",
        target=r"C:\Windows\notepad.exe",
        window_style="Normal",
        working_dir=r"C:\Windows",
    )

    expected = {
        "arguments": "create args",
        "description": "create description",
        "hot_key": "Alt+Ctrl+C",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": test_link,
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Normal",
        "working_dir": r"C:\Windows",
    }
    result = shortcut.get(path=test_link)
    assert result == expected


def test_create_lnk_dfs_issue_61170(shortcut, tmp_dir, tmp_share):
    test_link = str(os.path.join(str(tmp_dir / "test_link.lnk")))
    shortcut.create(
        path=test_link,
        arguments="create args",
        description="create description",
        hot_key="Alt+Ctrl+C",
        icon_index=0,
        icon_location=r"C:\Windows\notepad.exe",
        target=r"\\localhost\{}".format(tmp_share),
        window_style="Normal",
        working_dir=r"C:\Windows",
    )

    expected = {
        "arguments": "create args",
        "description": "create description",
        "hot_key": "Alt+Ctrl+C",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": test_link,
        "target": r"\\localhost\{}".format(tmp_share),
        "window_style": "Normal",
        "working_dir": r"C:\Windows",
    }
    result = shortcut.get(path=test_link)
    assert result == expected


def test_create_url(shortcut, tmp_dir):
    test_link = str(os.path.join(str(tmp_dir / "test_link.url")))
    shortcut.create(
        path=test_link,
        target="www.google.com",
    )

    expected = {
        "arguments": "",
        "description": "",
        "hot_key": "",
        "icon_index": 0,
        "icon_location": "",
        "path": test_link,
        "target": "http://www.google.com/",
        "window_style": "",
        "working_dir": "",
    }
    result = shortcut.get(path=test_link)
    assert result == expected


def test_create_force(shortcut, tmp_lnk):
    shortcut.create(
        path=str(tmp_lnk),
        arguments="create args",
        description="create description",
        hot_key="Alt+Ctrl+C",
        icon_index=0,
        icon_location=r"C:\Windows\notepad.exe",
        target=r"C:\Windows\notepad.exe",
        window_style="Normal",
        working_dir=r"C:\Windows",
        force=True,
    )

    expected = {
        "arguments": "create args",
        "description": "create description",
        "hot_key": "Alt+Ctrl+C",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(tmp_lnk),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Normal",
        "working_dir": r"C:\Windows",
    }
    result = shortcut.get(path=str(tmp_lnk))
    assert result == expected


def test_create_backup(shortcut, tmp_lnk):
    shortcut.create(
        path=str(tmp_lnk),
        arguments="create args",
        description="create description",
        hot_key="Alt+Ctrl+C",
        icon_index=0,
        icon_location=r"C:\Windows\notepad.exe",
        target=r"C:\Windows\notepad.exe",
        window_style="Normal",
        working_dir=r"C:\Windows",
        backup=True,
    )

    expected = {
        "arguments": "create args",
        "description": "create description",
        "hot_key": "Alt+Ctrl+C",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(tmp_lnk),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Normal",
        "working_dir": r"C:\Windows",
    }
    result = shortcut.get(path=str(tmp_lnk))
    assert result == expected
    assert len(list(tmp_lnk.parent.glob("{}-*.lnk".format(tmp_lnk.stem)))) == 1


def test_create_make_dirs(shortcut, tmp_dir):
    file_shortcut = tmp_dir / "subdir" / "test.lnk"
    shortcut.create(
        path=str(file_shortcut),
        arguments="create args",
        description="create description",
        hot_key="Alt+Ctrl+C",
        icon_index=0,
        icon_location=r"C:\Windows\notepad.exe",
        target=r"C:\Windows\notepad.exe",
        window_style="Normal",
        working_dir=r"C:\Windows",
        make_dirs=True,
    )

    expected = {
        "arguments": "create args",
        "description": "create description",
        "hot_key": "Alt+Ctrl+C",
        "icon_index": 0,
        "icon_location": r"C:\Windows\notepad.exe",
        "path": str(file_shortcut),
        "target": r"C:\Windows\notepad.exe",
        "window_style": "Normal",
        "working_dir": r"C:\Windows",
    }
    result = shortcut.get(path=str(file_shortcut))
    assert result == expected

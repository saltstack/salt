"""
Tests for win_shortcut execution module
"""
import os
import shutil
import subprocess

import pytest

from salt.exceptions import CommandExecutionError

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
def shortcut(modules):
    return modules.shortcut


@pytest.fixture(scope="function")
def tmp_dir(tmp_path_factory):
    """
    Create a temp testing directory
    """
    test_dir = tmp_path_factory.mktemp("test_dir")
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(str(test_dir))


@pytest.fixture(scope="function")
def tmp_lnk(tmp_path_factory):
    """
    Create an lnk shortcut for testing
    """
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
    """
    Create a url shortcut for testing
    """
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
def non_lnk():
    """
    Create a file with the correct extension, but is not an actual shortcut
    """
    with pytest.helpers.temp_file("non.lnk", contents="some text") as file:
        yield file


@pytest.fixture(scope="function")
def bad_ext():
    """
    Create a temporary file with a bad file extension
    """
    with pytest.helpers.temp_file("bad.ext", contents="some text") as file:
        yield file


@pytest.fixture(scope="function")
def tmp_share():
    """
    Create a Samba Share for testing. For some reason, this is really slow...
    """
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
    subprocess.run(create_cmd, check=True)

    yield share_name

    subprocess.run(remove_cmd, check=True)


def test_get_missing(shortcut, tmp_dir):
    """
    Make sure that a CommandExecutionError is raised if the shortcut does NOT
    exist
    """
    fake_shortcut = tmp_dir / "fake.lnk"
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.get(path=str(fake_shortcut))
    assert "Shortcut not found" in exc.value.message


def test_get_invalid_file_extension(shortcut, bad_ext):
    """
    Make sure that a CommandExecutionError is raised if the shortcut has a non
    shortcut file extension
    """
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.get(path=str(bad_ext))
    assert exc.value.message == "Invalid file extension: .ext"


def test_get_invalid_shortcut(shortcut, non_lnk):
    """
    Make sure that a CommandExecutionError is raised if the shortcut isn't
    actually a shortcut
    """
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.get(path=str(non_lnk))
    assert "Not a valid shortcut" in exc.value.message


def test_get_lnk(shortcut, tmp_lnk):
    """
    Make sure that we return information about a valid lnk shortcut
    """
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
    """
    Make sure that we return information about a valid url shortcut
    """
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
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.modify(path=str(fake_shortcut), target=r"C:\fake\path.txt")
    assert "Shortcut not found" in exc.value.message


def test_modify_invalid_file_extension(shortcut, bad_ext):
    """
    Make sure that a CommandExecutionError is raised if the shortcut has an
    invalid file extension
    """
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.modify(path=str(bad_ext), target=r"C:\fake\path.txt")
    assert exc.value.message == "Invalid file extension: .ext"


def test_modify_lnk(shortcut, tmp_lnk):
    """
    Make sure that we are able to modify an lnk shortcut
    """
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
    """
    Make sure that we are able to modify a url shortcut
    """
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


def test_create_invalid_file_extension(shortcut, bad_ext):
    """
    Make sure that a CommandExecutionError is raised if the shortcut file
    extension is invalid
    """
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.create(path=str(bad_ext), target=r"C:\fake\path.txt")
    assert exc.value.message == "Invalid file extension: .ext"


def test_create_existing(shortcut, tmp_lnk):
    """
    Make sure that a CommandExecutionError is raised if there is an existing
    shortcut with the same name and neither backup nor force is True
    """
    with pytest.raises(CommandExecutionError) as exc:
        shortcut.create(path=str(tmp_lnk), target=r"C:\fake\path.txt")
    assert "Found existing shortcut" in exc.value.message


def test_create_lnk(shortcut, tmp_dir):
    """
    Make sure we can create lnk type shortcut
    """
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


@pytest.mark.slow_test
def test_create_lnk_smb_issue_61170(shortcut, tmp_dir, tmp_share):
    """
    Make sure we can create shortcuts to Samba shares
    """
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
    """
    Make sure we can create url type shortcuts
    """
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
    """
    Make sure we can "force" create a shortcut if it already exists
    """
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
    """
    Make sure we can backup a shortcut if it already exists
    """
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
    """
    Make sure we can create the parent directories of a shortcut if they do not
    already exist
    """
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

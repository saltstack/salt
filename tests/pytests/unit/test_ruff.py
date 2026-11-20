"""Exercise incremental linting against real Git revisions and real Ruff output."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "tools" / "precommit" / "ruff.py"
CONFIG = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def environment() -> dict[str, str]:
    """Keep fixture repositories independent of the calling Git hook."""
    return {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }


def git(repo: Path, *args: str) -> str:
    """Run Git within a disposable repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=environment(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write(repo: Path, name: str, contents: str) -> None:
    """Write a fixture, including its parent directories."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def commit(repo: Path) -> str:
    """Create a local fixture revision without running user hooks or signing."""
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=.git/no-hooks",
        "commit",
        "--quiet",
        "-m",
        "test revision",
    )
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a baseline containing an existing unused import."""
    pytest.importorskip("ruff")
    git(tmp_path, "init", "--quiet")
    git(tmp_path, "config", "user.name", "Ruff test")
    git(tmp_path, "config", "user.email", "ruff-test@example.invalid")
    write(tmp_path, "pyproject.toml", CONFIG)
    write(tmp_path, "sample.py", "import os\n\nvalue = 1\n")
    commit(tmp_path)
    return tmp_path


def check(
    repo: Path, *args: str, base_env: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the hook as contributors and CI do, with an explicit environment."""
    env = environment()
    env.pop("RUFF_BASE_REF", None)
    if base_env is not None:
        env["RUFF_BASE_REF"] = base_env
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_existing_violation_survives_line_shifts(repo: Path) -> None:
    write(repo, "sample.py", "# New documentation\n\nimport os\n\nvalue = 2\n")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "0 new violation(s)" in result.stdout


def test_new_violation_in_existing_file_is_blocking(repo: Path) -> None:
    write(repo, "sample.py", "import os\nimport sys\n\nvalue = 1\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "F401 `sys` imported but unused" in result.stdout
    assert "F401 `os`" not in result.stdout


def test_removing_last_use_reports_unchanged_import_line(repo: Path) -> None:
    write(repo, "sample.py", "import os\n\nvalue = os.name\n")
    commit(repo)
    write(repo, "sample.py", "import os\n\nvalue = 'changed'\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "sample.py:1:8: F401" in result.stdout


def test_new_file_and_filename_with_spaces(repo: Path) -> None:
    write(repo, "new module.py", "import sys\n")
    result = check(repo, "new module.py")
    assert result.returncode == 1, result.stderr + result.stdout
    assert "new module.py:1:8: F401" in result.stdout


def test_identical_new_violation_is_not_hidden(repo: Path) -> None:
    write(repo, "sample.py", "def old():\n    import os\n")
    commit(repo)
    write(repo, "sample.py", "def old():\n    import os\n\ndef new():\n    import os\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert result.stdout.count("F401") == 1


def test_rename_preserves_baseline(repo: Path) -> None:
    git(repo, "mv", "sample.py", "renamed.py")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_rename_with_new_violation(repo: Path) -> None:
    # Keep enough original content for Git's similarity-based rename detection.
    original = "import os\n\nvalue = 1\n" + "# Existing documentation\n" * 10
    write(repo, "sample.py", original)
    commit(repo)
    git(repo, "mv", "sample.py", "renamed.py")
    write(
        repo,
        "renamed.py",
        original + "\ndef new(items=[]):\n    return items\n",
    )
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "B006" in result.stdout
    assert "F401" not in result.stdout


def test_deleted_file_is_skipped(repo: Path) -> None:
    (repo / "sample.py").unlink()
    result = check(repo, "sample.py")
    assert result.returncode == 0, result.stderr + result.stdout


def test_missing_base_fails_closed(repo: Path) -> None:
    result = check(repo, "--base-ref", "missing-branch")
    assert result.returncode == 2
    assert "Ruff incremental check failed" in result.stderr


def test_explicit_filenames_restrict_check(repo: Path) -> None:
    write(repo, "clean.py", "value = 1\n")
    write(repo, "broken.py", "import sys\n")
    result = check(repo, "clean.py")
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize("directory", ["salt/ext", "templates"])
def test_vendored_and_template_files_are_excluded(repo: Path, directory: str) -> None:
    filename = f"{directory}/new.py"
    write(repo, filename, "import sys\n")
    result = check(repo, filename)
    assert result.returncode == 0, result.stderr + result.stdout


def test_ci_base_catches_committed_violations(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    write(repo, "sample.py", "import os\nimport sys\n\nvalue = 1\n")
    commit(repo)
    assert check(repo).returncode == 0
    result = check(repo, base_env=base)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "F401 `sys`" in result.stdout


def test_command_line_base_overrides_environment(repo: Path) -> None:
    result = check(repo, "--base-ref", "HEAD", base_env="missing-branch")
    assert result.returncode == 0, result.stderr + result.stdout


def test_staged_addition_is_checked(repo: Path) -> None:
    write(repo, "added.py", "import sys\n")
    git(repo, "add", "added.py")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "added.py:1:8: F401" in result.stdout


def test_never_autofixes_files(repo: Path) -> None:
    write(
        repo,
        "pyproject.toml",
        CONFIG.replace("target-version", "fix = true\ntarget-version"),
    )
    source = "import sys\n"
    write(repo, "new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert (repo / "new.py").read_text(encoding="utf-8") == source


def test_invalid_ruff_config_fails_closed(repo: Path) -> None:
    write(repo, "pyproject.toml", '[tool.ruff.lint]\nselect = ["INVALID"]\n')
    write(repo, "new.py", "value = 1\n")
    result = check(repo)
    assert result.returncode == 2
    assert "Ruff incremental check failed" in result.stderr


def test_inherited_git_hook_environment_is_isolated(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use invalid foreign paths so a regression fails without touching another repo.
    monkeypatch.setenv("GIT_DIR", str(repo / "foreign-git-dir"))
    monkeypatch.setenv("GIT_WORK_TREE", str(repo / "foreign-work-tree"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(repo / "foreign-index"))
    monkeypatch.setenv("GIT_CONFIG", str(repo / "foreign-config"))
    assert Path(git(repo, "rev-parse", "--show-toplevel")) == repo
    write(repo, "new.py", "import sys\n")
    base = git(repo, "rev-parse", "HEAD")
    commit(repo)
    result = check(repo, "--base-ref", base)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "new.py:1:8: F401" in result.stdout


@pytest.mark.parametrize(
    "source, code",
    [
        ('message = f"plain text"\n', "F541"),
        ("assert (True, False)\n", "F631"),
        ("if (False, False):\n    pass\n", "F634"),
        (
            "callbacks = []\nfor index in range(3):\n    callbacks.append(lambda: index)\n",
            "B023",
        ),
        ("print(missing_name)\n", "F821"),
        ("def f():\n    pass\n\n\ndef f():\n    pass\n", "F811"),
        ("try:\n    pass\nexcept:\n    pass\n", "E722"),
        ("def f(x):\n    return x == None\n", "E711"),
        ("def f(x, y):\n    return not x in y\n", "E713"),
        ("def f(a, b):\n    return type(a) == type(b)\n", "E721"),
        ("import asyncio\n\n\nasync def f(c):\n    asyncio.create_task(c)\n", "RUF006"),
        ("def f():\n    raise\n", "PLE0704"),
        ("import pytest\n\nwith pytest.raises(Exception):\n    pass\n", "B017"),
    ],
)
def test_additional_rules_are_enforced(repo: Path, source: str, code: str) -> None:
    write(repo, "new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout


def test_salt_injected_globals_are_not_undefined(repo: Path) -> None:
    write(repo, "new.py", "def f():\n    return __salt__, __opts__, __context__\n")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_unused_local_variable_is_reported_outside_tests(repo: Path) -> None:
    write(repo, "salt/new.py", "def f(g):\n    ret = g()\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "F841" in result.stdout


def test_underscore_is_allowed_for_unused_values(repo: Path) -> None:
    write(repo, "salt/new.py", "def f(g):\n    _ = g()\n")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_unused_local_variable_is_allowed_in_tests(repo: Path) -> None:
    write(repo, "tests/test_new.py", "def test_f(g):\n    ret = g()\n")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_assert_false_is_allowed_in_tests(repo: Path) -> None:
    write(repo, "tests/test_new.py", "def test_f():\n    assert False\n")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_assert_false_is_reported_outside_tests(repo: Path) -> None:
    write(repo, "salt/new.py", "def f():\n    assert False\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "B011" in result.stdout


# One example per rule that has no violation in the code base today.
NEW_RULE_CASES = [
    ("B002", "def f(n):\n    return ++n\n"),
    ("B003", "import os\n\nos.environ = {}\n"),
    ("B012", "def f():\n    try:\n        pass\n    finally:\n        return 1\n"),
    ("B013", "try:\n    pass\nexcept (ValueError,):\n    pass\n"),
    ("B014", "try:\n    pass\nexcept (ValueError, ValueError):\n    pass\n"),
    ("B016", 'def f():\n    raise "error"\n'),
    (
        "B019",
        "import functools\n\n\nclass A:\n    @functools.lru_cache\n    def m(self):\n        return 1\n",
    ),
    ("B021", 'def f(x):\n    f"""doc {x}"""\n'),
    ("B022", "import contextlib\n\nwith contextlib.suppress():\n    pass\n"),
    ("B029", "try:\n    pass\nexcept ():\n    pass\n"),
    ("B030", "try:\n    pass\nexcept 1:\n    pass\n"),
    (
        "B031",
        "import itertools\n\nfor _, g in itertools.groupby([1, 2]):\n    a = list(g)\n    b = list(g)\n    print(a, b)\n",
    ),
    ("B032", 'd = {}\nd["a"]: 1\n'),
    ("B033", "s = {1, 2, 1}\n"),
    ("B035", 'd = {"k": v for v in range(3)}\n'),
    ("PLW0127", "def f(x):\n    x = x\n    return x\n"),
    ("PLW0128", "a, a = 1, 2\n"),
    ("PLW0131", "(a := 1)\n"),
    ("PLW0133", 'def f():\n    ValueError("x")\n'),
    ("PLW0177", 'def f(x):\n    return x == float("nan")\n'),
    ("PLW0211", "class A:\n    @staticmethod\n    def m(self):\n        pass\n"),
    ("PLW0245", "class A:\n    def m(self):\n        super.m()\n"),
    ("PLW0604", "global x\nx = 1\n"),
    ("PLW0642", "class A:\n    def m(self):\n        self = 1\n"),
    ("PLW0711", "try:\n    pass\nexcept ValueError or TypeError:\n    pass\n"),
    ("PLW1501", 'def f(p):\n    return open(p, "rz")\n'),
    ("PLW1507", "import copy\nimport os\n\nenv = copy.copy(os.environ)\n"),
    ("PLW2101", "import threading\n\nwith threading.Lock():\n    pass\n"),
    ("PGH003", "x = 1  # type: ignore\n"),
    ("PGH005", "def test_f(m):\n    assert m.called_once_with(1)\n"),
    ("PT002", 'import pytest\n\n\n@pytest.fixture("module")\ndef f():\n    pass\n'),
    ("PT008", 'from unittest import mock\n\nmock.patch("os.getcwd", lambda: "/tmp")\n'),
    ("PT020", "import pytest\n\n\n@pytest.yield_fixture\ndef f():\n    yield 1\n"),
    (
        "PT024",
        "import pytest\n\n\n@pytest.mark.asyncio\n@pytest.fixture\nasync def f():\n    pass\n",
    ),
    (
        "PT025",
        'import pytest\n\n\n@pytest.mark.usefixtures("a")\n@pytest.fixture\ndef f():\n    pass\n',
    ),
    (
        "PT026",
        "import pytest\n\n\n@pytest.mark.usefixtures()\ndef test_f():\n    pass\n",
    ),
    ("LOG001", 'import logging\n\nlog = logging.Logger("x")\n'),
    (
        "LOG007",
        'import logging\n\nlog = logging.getLogger()\ntry:\n    pass\nexcept Exception:\n    log.exception("x", exc_info=False)\n',
    ),
    (
        "LOG014",
        'import logging\n\nlog = logging.getLogger()\nlog.warning("x", exc_info=True)\n',
    ),
    (
        "G101",
        'import logging\n\nlog = logging.getLogger()\nlog.info("x", extra={"name": 1})\n',
    ),
    ("YTT101", "import sys\n\nv = sys.version[:3]\n"),
    ("YTT102", "import sys\n\nv = sys.version[2]\n"),
    ("YTT103", 'import sys\n\nv = sys.version > "3.9"\n'),
    ("YTT201", "import sys\n\nv = sys.version_info[0] == 3\n"),
    ("YTT202", "import six\n\nv = six.PY3\n"),
    ("YTT301", "import sys\n\nv = sys.version[0]\n"),
    ("YTT302", 'import sys\n\nv = sys.version >= "3"\n'),
    ("YTT303", "import sys\n\nv = sys.version[:1]\n"),
    (
        "RUF008",
        "from dataclasses import dataclass\n\n\n@dataclass\nclass A:\n    x: list = []\n",
    ),
    (
        "RUF009",
        "from dataclasses import dataclass\n\n\ndef make():\n    return []\n\n\n@dataclass\nclass A:\n    x: list = make()\n",
    ),
    ("RUF016", 'def f():\n    return [1, 2, 3]["a"]\n'),
    ("RUF018", "def f(g):\n    assert (x := g())\n    return x\n"),
    ("RUF024", 'd = dict.fromkeys(["a"], [])\n'),
    (
        "RUF026",
        "from collections import defaultdict\n\nd = defaultdict(default_factory=list)\n",
    ),
    (
        "RUF033",
        "from dataclasses import dataclass\n\n\n@dataclass\nclass A:\n    x: int\n\n    def __post_init__(self, y=1):\n        pass\n",
    ),
    ("RUF060", "x = 1 in []\n"),
    ("RUF068", '__all__ = ["a", "a"]\n'),
    ("T100", "breakpoint()\n"),
    ("B024", "import abc\n\n\nclass A(abc.ABC):\n    def f(self):\n        return 1\n"),
    ("B027", "import abc\n\n\nclass A(abc.ABC):\n    def f(self):\n        pass\n"),
    ("RUF028", "# fmt: skip\nx = 1\n"),
    (
        "RUF049",
        "from dataclasses import dataclass\nfrom enum import Enum\n\n\n@dataclass\nclass E(Enum):\n    A = 1\n",
    ),
    (
        "RUF058",
        "import itertools\n\nx = list(itertools.starmap(lambda a, b: a + b, zip([1], [2])))\n",
    ),
    ("RUF104", "# ruff: disable[F401]\nimport sys\n"),
    (
        "ASYNC210",
        'import requests\n\n\nasync def f():\n    requests.get("https://x")\n',
    ),
    (
        "ASYNC220",
        'import subprocess\n\n\nasync def f():\n    subprocess.Popen(["ls"])\n',
    ),
    ("ASYNC222", "import os\n\n\nasync def f():\n    os.wait()\n"),
    ("ASYNC230", 'async def f():\n    open("x")\n'),
    ("ASYNC250", 'async def f():\n    input("x")\n'),
    ("S313", 'from xml.etree.cElementTree import parse\n\nparse("x")\n'),
    (
        "S315",
        "from xml.sax.expatreader import create_parser\n\nparser = create_parser()\n",
    ),
    ("S316", 'from xml.dom.expatbuilder import parse\n\nparse("x")\n'),
    ("S317", 'import xml.sax\n\nxml.sax.parse("x")\n'),
    ("S319", 'from xml.dom.pulldom import parse\n\nparse("x")\n'),
    (
        "S304",
        'from cryptography.hazmat.primitives.ciphers import Cipher, algorithms\n\ncipher = Cipher(algorithms.ARC4(b"k"), mode=None)\n',
    ),
    (
        "S305",
        'from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes\n\nCipher(algorithms.AES(b"k"), modes.ECB())\n',
    ),
    ("S302", 'import marshal\n\nmarshal.loads(b"x")\n'),
    ("S501", 'import requests\n\nrequests.get("https://x", verify=False)\n'),
    ("S502", "import ssl\n\nssl.wrap_socket(None, ssl_version=ssl.PROTOCOL_SSLv3)\n"),
    ("S503", "import ssl\n\n\ndef f(ctx=ssl.PROTOCOL_SSLv2):\n    pass\n"),
    (
        "S505",
        "from cryptography.hazmat.primitives.asymmetric import dsa\n\ndsa.generate_private_key(key_size=512)\n",
    ),
    ("S609", 'import subprocess\n\nsubprocess.Popen("chmod 600 *", shell=True)\n'),
    ("S612", "import logging.config\n\nlogging.config.listen(9999)\n"),
    ("S201", "from flask import Flask\n\napp = Flask(__name__)\napp.run(debug=True)\n"),
    (
        "S308",
        "from django.utils.safestring import mark_safe\n\n\ndef f(text):\n    return mark_safe(text)\n",
    ),
    (
        "S508",
        'from pysnmp.hlapi import CommunityData\n\nCommunityData("public", mpModel=0)\n',
    ),
    (
        "S509",
        'from pysnmp.hlapi import UsmUserData\n\nUsmUserData("user", "authkey")\n',
    ),
    (
        "S610",
        'from django.contrib.auth.models import User\n\n\ndef f(q):\n    return User.objects.all().extra(select={"a": q})\n',
    ),
    (
        "S611",
        "from django.db.models.expressions import RawSQL\n\n\ndef f(q):\n    return RawSQL(q, [])\n",
    ),
    (
        "SIM107",
        "def f():\n    try:\n        return 1\n    finally:\n        return 2\n",
    ),
    ("SIM220", "def f(a):\n    return a and not a\n"),
    ("SIM221", "def f(a):\n    return a or not a\n"),
    ("SIM223", "def f(x, y):\n    return x and [] and y\n"),
    ("PIE794", "class A:\n    x = 1\n    x = 2\n"),
    ("PIE796", "import enum\n\n\nclass E(enum.Enum):\n    A = 1\n    B = 1\n"),
    ("PLC0205", 'class A:\n    __slots__ = "a"\n'),
    ("PLC0208", "for x in {1, 2, 3}:\n    print(x)\n"),
    ("PLC3002", "x = (lambda: 1)()\n"),
    ("PLR0133", "x = 1 < 2\n"),
    ("PLR1708", "def f():\n    raise StopIteration\n    yield 1\n"),
    ("RUF030", 'def f(x):\n    assert x, print("bad")\n'),
    ("RUF032", "from decimal import Decimal\n\nx = Decimal(0.1)\n"),
    ("RUF048", 'v = tuple(map(int, __version__.split(".")))\n'),
    ("RUF101", "import os  # noqa: PGH001\n"),
    ("RUF103", "# ruff: disable\nx = 1\n"),
    ("S601", 'import paramiko\n\nparamiko.exec_command("ls")\n'),
    ("S606", 'import os\n\nos.execl("/bin/ls", "ls")\n'),
    (
        "S704",
        'from markupsafe import Markup\n\n\ndef f(text):\n    return Markup("<b>" + text + "</b>")\n',
    ),
    ("S312", 'import telnetlib\n\ntelnetlib.Telnet("host")\n'),
    (
        "G002",
        'import logging\n\nlog = logging.getLogger(__name__)\nlog.info("%s" % "x")\n',
    ),
    ("SIM202", "def f(a, b):\n    return not a != b\n"),
    ("RUF034", "def f(x):\n    return 1 if x else 1\n"),
    ("RUF057", "a = round(1, 0)\n"),
    ("PIE790", 'def f():\n    """Doc."""\n    pass\n'),
    ("E742", "class l:\n    pass\n"),
    ("E743", "def l():\n    pass\n"),
    (
        "PT010",
        "import pytest\n\n\ndef test_f():\n    with pytest.raises():\n        pass\n",
    ),
    ("PT016", "import pytest\n\n\ndef test_f():\n    pytest.fail()\n"),
    (
        "PT031",
        "import pytest\n\n\ndef test_f():\n    with pytest.warns(UserWarning):\n        a = 1\n        b = 2\n",
    ),
]


@pytest.mark.parametrize(("code", "source"), NEW_RULE_CASES, ids=lambda v: v[:8])
def test_rules_without_existing_violations(repo: Path, code: str, source: str) -> None:
    write(repo, "salt/new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout


def test_module_importing_itself_is_reported(repo: Path) -> None:
    write(repo, "pkg/__init__.py", "")
    write(repo, "pkg/mod.py", "import pkg.mod\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "PLW0406" in result.stdout


# One example per rule that reports some existing violations.
RULES_WITH_EXISTING_VIOLATIONS = [
    ("PLW0129", 'def f(x):\n    assert "x must be set"\n'),
    (
        "PLW0120",
        'def f(items):\n    for i in items:\n        print(i)\n    else:\n        print("done")\n',
    ),
    ("PLW1641", "class A:\n    def __eq__(self, other):\n        return True\n"),
    ("LOG002", "import logging\n\nlog = logging.getLogger(__file__)\n"),
    (
        "LOG004",
        'import logging\n\nlog = logging.getLogger(__name__)\n\n\ndef f():\n    log.exception("failed")\n',
    ),
    ("G010", 'import logging\n\nlog = logging.getLogger(__name__)\nlog.warn("x")\n'),
    (
        "G202",
        'import logging\n\nlog = logging.getLogger(__name__)\n\n\ndef f():\n    try:\n        pass\n    except Exception:\n        log.exception("x", exc_info=True)\n',
    ),
    ("RUF064", 'import os\n\nos.chmod("/tmp/x", 644)\n'),
    ("RUF040", "def f(result):\n    assert result, None\n"),
    ("DTZ003", "import datetime\n\nnow = datetime.datetime.utcnow()\n"),
    ("DTZ004", "import datetime\n\nt = datetime.datetime.utcfromtimestamp(0)\n"),
    ("ASYNC251", "import time\n\n\nasync def f():\n    time.sleep(1)\n"),
    ("PGH004", "import os  # noqa\n"),
    (
        "RUF043",
        'import pytest\n\n\ndef test_f():\n    with pytest.raises(ValueError, match="a.b"):\n        pass\n',
    ),
    (
        "PT030",
        "import pytest\n\n\ndef test_f():\n    with pytest.warns(DeprecationWarning):\n        pass\n",
    ),
    (
        "PT017",
        "def test_f():\n    try:\n        pass\n    except ValueError as exc:\n        assert exc.args\n",
    ),
    (
        "PT014",
        'import pytest\n\n\n@pytest.mark.parametrize("a", [1, 1])\ndef test_f(a):\n    pass\n',
    ),
    ("B011", "def test_f():\n    assert False\n"),
]


@pytest.mark.parametrize(
    ("code", "source"), RULES_WITH_EXISTING_VIOLATIONS, ids=lambda v: v[:8]
)
def test_rules_with_existing_violations(repo: Path, code: str, source: str) -> None:
    write(repo, "salt/new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout

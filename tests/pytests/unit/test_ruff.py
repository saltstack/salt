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
    write(tmp_path, "salt/__init__.py", "")
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
        CONFIG.replace("\ntarget-version", "\nfix = true\ntarget-version", 1),
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
    # Rules enabled in the first wave: nothing in the code reported them.
    ("A006", "f = lambda print: print\n"),
    (
        "ASYNC100",
        "import asyncio\n\n\nasync def func():\n    async with asyncio.timeout(2):\n        do_something()\n",
    ),
    (
        "ASYNC105",
        "import trio\n\n\nasync def double_sleep(x):\n    trio.sleep(2 * x)\n",
    ),
    ("ASYNC115", "import trio\n\n\nasync def func():\n    await trio.sleep(0)\n"),
    ("ASYNC116", "import trio\n\n\nasync def func():\n    await trio.sleep(86401)\n"),
    (
        "ASYNC212",
        "import httpx\n\n\nasync def fetch():\n    client = httpx.Client()\n    response = client.get(...)\n",
    ),
    ("ASYNC221", "import subprocess\n\n\nasync def foo():\n    subprocess.run(cmd)\n"),
    (
        "B024",
        'from abc import ABC\nfrom typing import ClassVar\n\n\nclass Foo(ABC):\n    class_var: ClassVar[str] = "assigned"\n\n    def method(self):\n        bar()\n',
    ),
    ("B027", "from abc import ABC\n\n\nclass Foo(ABC):\n    def method(self): ...\n"),
    ("C401", "set(f(x) for x in foo)\nset(x for x in foo)\nset((x for x in foo))\n"),
    ("C402", "dict((x, f(x)) for x in foo)\n"),
    ("C403", "set([f(x) for x in foo])\n"),
    ("C404", "dict([(x, f(x)) for x in foo])\n"),
    ("C405", "set([1, 2])\nset((1, 2))\nset([])\n"),
    ("C410", "list([1, 2])\nlist((1, 2))\n"),
    ("C411", "list([f(x) for x in foo])\n"),
    ("C415", "sorted(iterable[::-1])\nset(iterable[::-1])\nreversed(iterable[::-1])\n"),
    ("DTZ901", "import datetime\n\ndatetime.datetime.max\n"),
    ("E401", "import sys, os\n"),
    ("E701", 'if foo == "blah": do_blah_thing()\n'),
    ("E702", "do_one(); do_two(); do_three()\n"),
    ("E703", "do_four();  # useless semicolon\n"),
    ("E731", "f = lambda x: 2 * x\n"),
    ("EXE003", "#!/usr/bin/env bash\n"),
    ("EXE004", " #!/usr/bin/env python3\n"),
    ("EXE005", "foo = 1\n#!/usr/bin/env python3\n"),
    (
        "FURB163",
        "import math\n\nmath.log(4, math.e)\nmath.log(4, 2)\nmath.log(4, 10)\n",
    ),
    (
        "FURB164",
        'from decimal import Decimal\nfrom fractions import Fraction\n\nDecimal.from_float(4.2)\nDecimal.from_float(float("inf"))\nFraction.from_float(4.2)\nFraction.from_decimal(Decimal("4.2"))\n',
    ),
    (
        "FURB166",
        'num = "0xABC"\n\nif num.startswith("0b"):\n    i = int(num[2:], 2)\nelif num.startswith("0o"):\n    i = int(num[2:], 8)\nelif num.startswith("0x"):\n    i = int(num[2:], 16)\n\nprint(i)\n',
    ),
    ("FURB168", "isinstance(obj, type(None))\n"),
    ("FURB169", "type(obj) is type(None)\n"),
    (
        "FURB181",
        'from hashlib import sha512\n\nhashed = sha512(b"some data").digest().hex()\n',
    ),
    (
        "FURB187",
        "l = [1, 2, 3]\nl = reversed(l)\n\nl = [1, 2, 3]\nl = list(reversed(l))\n\nl = [1, 2, 3]\nl = l[::-1]\n",
    ),
    (
        "G003",
        'import logging\n\nlogging.basicConfig(format="%(message)s", level=logging.INFO)\n\nuser = "Maria"\n\nlogging.info(user + " - Something happened")\n',
    ),
    (
        "PLC0105",
        'from typing import TypeVar\n\nT = TypeVar("T", covariant=True)\nU = TypeVar("U", contravariant=True)\nV_co = TypeVar("V_co")\n',
    ),
    (
        "PLC0131",
        'from typing import TypeVar\n\nT = TypeVar("T", covariant=True, contravariant=True)\n',
    ),
    ("PLC0132", 'from typing import TypeVar\n\nT = TypeVar("U")\n'),
    ("PLC0414", "import numpy as numpy\n"),
    (
        "PLC1802",
        'fruits = ["orange", "apple"]\nvegetables = []\n\nif len(fruits):\n    print(fruits)\n\nif not len(vegetables):\n    print(vegetables)\n',
    ),
    ("PLC2401", "ápple_count: int\n"),
    ("PLC2403", "import bár\n"),
    (
        "PLW1510",
        'import subprocess\n\nsubprocess.run(["ls", "nonexistent"])  # No exception raised.\n',
    ),
    (
        "PLW3301",
        "minimum = min(1, 2, min(3, 4, 5))\nmaximum = max(1, 2, max(3, 4, 5))\ndiff = maximum - minimum\n",
    ),
    ("PT002", 'import pytest\n\n\n@pytest.fixture("module")\ndef my_fixture(): ...\n'),
    (
        "PT008",
        'def test_foo(mocker):\n    mocker.patch("module.target", lambda x, y: 7)\n',
    ),
    (
        "PT020",
        "import pytest\n\n\n@pytest.yield_fixture()\ndef my_fixture():\n    obj = SomeClass()\n    yield obj\n    obj.cleanup()\n",
    ),
    (
        "PT024",
        "import pytest\n\n\n@pytest.mark.asyncio()\n@pytest.fixture()\nasync def my_fixture():\n    return 0\n",
    ),
    (
        "PT025",
        'import pytest\n\n\n@pytest.fixture()\ndef a():\n    pass\n\n\n@pytest.mark.usefixtures("a")\n@pytest.fixture()\ndef b(a):\n    pass\n',
    ),
    (
        "PT026",
        "import pytest\n\n\n@pytest.mark.usefixtures()\ndef test_something(): ...\n",
    ),
    ("PTH124", 'import py.path\n\np = py.path.local("/foo/bar").join("baz/qux")\n'),
    ("PTH201", 'from pathlib import Path\n\n_ = Path(".")\n'),
    ("PTH203", "import os\n\nos.path.getatime(__file__)\n"),
    ("PTH210", 'from pathlib import Path\n\npath = Path()\n\npath.with_suffix("py")\n'),
    ("RUF020", "from typing import Never\n\n\ndef func() -> Never | int: ...\n"),
    (
        "RUF028",
        "def decorator():\n    pass\n\n\n@decorator\n# fmt: off\ndef example():\n    if True:\n        # fmt: skip\n        expression = [\n            # fmt: off\n            1,\n            2,\n        ]\n        # yapf: disable\n    # fmt: on\n    # yapf: enable\n",
    ),
    ("RUF036", "def func(arg: None | int): ...\n"),
    (
        "RUF037",
        "from collections import deque\n\nqueue = deque(set())\nqueue = deque([], 10)\n",
    ),
    ("RUF041", "from typing import Literal\n\nx: Literal[Literal[1], 2]\n"),
    (
        "RUF049",
        "from dataclasses import dataclass\nfrom enum import Enum\n\n\n@dataclass\nclass E(Enum): ...\n",
    ),
    (
        "RUF058",
        "from itertools import starmap\n\n\nstarmap(func, zip(a, b))\nstarmap(func, zip(a, b, strict=True))\n",
    ),
    (
        "RUF063",
        'foo.__dict__.get("__annotations__", {})\n# or\nfoo.__dict__["__annotations__"]\n',
    ),
    ("RUF104", "# ruff: disable[F401]\nimport sys\n"),
    (
        "SIM911",
        'flag_stars = {"USA": 50, "Slovenia": 3, "Panama": 2, "Australia": 6}\n\nfor country, stars in zip(flag_stars.keys(), flag_stars.values()):\n    print(f"{country}\'s flag has {stars} stars.")\n',
    ),
    ("T100", "def foo():\n    breakpoint()\n"),
    (
        "TC004",
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import foo\n\n\ndef bar() -> None:\n    foo.bar()  # raises NameError: name 'foo' is not defined\n",
    ),
    (
        "TC005",
        'from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    pass\n\nprint("Hello, world!")\n',
    ),
    ("TID252", "from .. import foo\n"),
    ("W291", "x = 1 \n"),
    ("W292", "x = 1"),
    ("W293", "class A:\n    \n    x = 1\n"),
    # Rules of the second wave that nothing in the code breaks any more.
    ("C417", "map(lambda x: x + 1, iterable)\n"),
    ("LOG009", "import logging\n\n\nlogging.basicConfig(level=logging.WARN)\n"),
    ("PLR0206", "class Cat:\n    @property\n    def purr(self, volume): ...\n"),
    (
        "PLW0602",
        'DEBUG = True\n\n\ndef foo():\n    global DEBUG\n    if DEBUG:\n        print("foo() called")\n    ...\n',
    ),
    ("PLW1508", 'import os\n\nint(os.getenv("FOO", 1))\n'),
    (
        "PLW1509",
        "import os, subprocess\n\nsubprocess.Popen(foo, preexec_fn=os.setsid)\nsubprocess.Popen(bar, preexec_fn=os.setpgid(0, 0))\n",
    ),
    (
        "YTT203",
        'import sys\n\nif sys.version_info[1] < 7:\n    print("Python 3.6 or earlier.")  # This will be printed on Python 4.0.\n',
    ),
    (
        "YTT204",
        'import sys\n\nif sys.version_info.minor < 7:\n    print("Python 3.6 or earlier.")  # This will be printed on Python 4.0.\n',
    ),
    # Rules of the third wave that nothing in the code breaks.
    ("SIM101", "if isinstance(obj, int) or isinstance(obj, float):\n    pass\n"),
    # Security rules enabled that nothing in the code breaks.
    ("S113", 'import requests\n\nrequests.get("https://www.example.com/")\n'),
    ("S201", "from flask import Flask\n\napp = Flask()\n\napp.run(debug=True)\n"),
    (
        "S308",
        'from django.utils.safestring import mark_safe\n\n\ndef render_username(username):\n    return mark_safe(f"<i>{username}</i>")  # Dangerous if username is user-provided.\n',
    ),
    ("S321", 'import ftplib\n\nftp = ftplib.FTP("example.com")\n'),
    (
        "S508",
        'from pysnmp.hlapi import CommunityData\n\nCommunityData("public", mpModel=0)\n',
    ),
    ("S509", 'from pysnmp.hlapi import UsmUserData\n\nUsmUserData("user")\n'),
    (
        "S605",
        'import os\n\n# Safe usage (literal string)\ncommand = "ls -l"\nos.system(command)\n\n# Potentially unsafe usage (expression)\ncmd = get_user_input()\nos.system(cmd)\n',
    ),
    (
        "S610",
        'from django.contrib.auth.models import User\n\n# String interpolation creates a security loophole that could be used\n# for SQL injection:\nUser.objects.all().extra(select={"test": "%secure" % "nos"})\n',
    ),
    (
        "S611",
        'from django.db.models.expressions import RawSQL\nfrom django.contrib.auth.models import User\n\nUser.objects.annotate(val=RawSQL("%s" % input_param, []))\n',
    ),
    (
        "S702",
        'from mako.template import Template\n\nTemplate("${ data }")  # Unescaped: vulnerable to XSS.\n',
    ),
    # Rules for libraries Salt does not use (Airflow, Django, FastAPI, gettext, NumPy,
    # pandas, type stubs). Nothing in the code breaks them.
    (
        "AIR001",
        'from airflow.operators import PythonOperator\n\n\nincorrect_name = PythonOperator(task_id="my_task")\n',
    ),
    (
        "AIR002",
        'from airflow import DAG\n\n\n# Using the implicit default schedule.\ndag = DAG(dag_id="my_dag")\n',
    ),
    (
        "AIR301",
        "from airflow.utils.dates import days_ago\n\n\nyesterday = days_ago(today, 1)\n",
    ),
    (
        "AIR302",
        "from airflow.auth.managers.fab.fab_auth_manager import FabAuthManager\n\nfab_auth_manager_app = FabAuthManager().get_fastapi_app()\n",
    ),
    (
        "AIR303",
        'from airflow.lineage.hook import HookLineageCollector\n\ncollector = HookLineageCollector()\n# Passing positional arguments will raise a runtime error in Airflow 3.0\ncollector.create_asset("s3://bucket/key")\n',
    ),
    ("AIR311", 'from airflow import Dataset\n\n\nDataset(uri="test://test/")\n'),
    (
        "AIR312",
        'from airflow.operators.python import PythonOperator\n\n\ndef print_context(ds=None, **kwargs):\n    print(kwargs)\n    print(ds)\n\n\nprint_the_context = PythonOperator(\n    task_id="print_the_context", python_callable=print_context\n)\n',
    ),
    (
        "DJ001",
        "from django.db import models\n\n\nclass MyModel(models.Model):\n    field = models.CharField(max_length=255, null=True)\n",
    ),
    (
        "DJ003",
        'from django.shortcuts import render\n\n\ndef index(request):\n    posts = Post.objects.all()\n    return render(request, "app/index.html", locals())\n',
    ),
    (
        "DJ006",
        'from django.forms import ModelForm\n\n\nclass PostForm(ModelForm):\n    class Meta:\n        model = Post\n        exclude = ["author"]\n',
    ),
    (
        "DJ007",
        'from django.forms import ModelForm\n\n\nclass PostForm(ModelForm):\n    class Meta:\n        model = Post\n        fields = "__all__"\n',
    ),
    (
        "DJ008",
        "from django.db import models\n\n\nclass MyModel(models.Model):\n    field = models.CharField(max_length=255)\n",
    ),
    (
        "DJ012",
        'from django.db import models\n\n\nclass StrBeforeFieldModel(models.Model):\n    class Meta:\n        verbose_name = "test"\n        verbose_name_plural = "tests"\n\n    def __str__(self):\n        return "foobar"\n\n    first_name = models.CharField(max_length=32)\n    last_name = models.CharField(max_length=40)\n',
    ),
    (
        "DJ013",
        "from django.dispatch import receiver\nfrom django.db.models.signals import post_save\n\n\n@transaction.atomic\n@receiver(post_save, sender=MyModel)\ndef my_handler(sender, instance, created, **kwargs):\n    pass\n",
    ),
    (
        "FAST002",
        'from fastapi import Depends, FastAPI\n\napp = FastAPI()\n\n\nasync def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):\n    return {"q": q, "skip": skip, "limit": limit}\n\n\n@app.get("/items/")\nasync def read_items(commons: dict = Depends(common_parameters)):\n    return commons\n',
    ),
    (
        "FAST003",
        'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/things/{thing_id}")\nasync def read_thing(query: str): ...\n',
    ),
    (
        "INT001",
        'from gettext import gettext as _\n\nname = "Maria"\n_(f"Hello, {name}!")  # Looks for "Hello, Maria!".\n',
    ),
    (
        "INT002",
        'from gettext import gettext as _\n\nname = "Maria"\n_("Hello, {}!".format(name))  # Looks for "Hello, Maria!".\n',
    ),
    (
        "INT003",
        'from gettext import gettext as _\n\nname = "Maria"\n_("Hello, %s!" % name)  # Looks for "Hello, Maria!".\n',
    ),
    ("NPY001", "import numpy as np\n\nnp.int\n"),
    ("NPY002", "import numpy as np\n\nnp.random.seed(1337)\nnp.random.normal()\n"),
    ("NPY003", "import numpy as np\n\nnp.alltrue([True, False])\n"),
    (
        "NPY201",
        "import numpy as np\n\narr1 = [np.Infinity, np.NaN, np.nan, np.PINF, np.inf]\narr2 = [np.float_(1.5), np.float64(5.1)]\nnp.round_(arr2)\n",
    ),
    (
        "PD002",
        'import pandas as pd\n\nstudents = pd.read_csv("students.csv")\nstudents.sort_values("name", inplace=True)\n',
    ),
    (
        "PD003",
        'import pandas as pd\n\nanimals_df = pd.read_csv("animals.csv")\npd.isnull(animals_df)\n',
    ),
    (
        "PD004",
        'import pandas as pd\n\nanimals_df = pd.read_csv("animals.csv")\npd.notnull(animals_df)\n',
    ),
    (
        "PD007",
        'import pandas as pd\n\nstudents_df = pd.read_csv("students.csv")\nstudents_df.ix[0]  # 0th row or row with label 0?\n',
    ),
    (
        "PD008",
        'import pandas as pd\n\nstudents_df = pd.read_csv("students.csv")\nstudents_df.at["Maria"]\n',
    ),
    (
        "PD009",
        'import pandas as pd\n\nstudents_df = pd.read_csv("students.csv")\nstudents_df.iat[0]\n',
    ),
    (
        "PD010",
        'import pandas as pd\n\ndf = pd.read_csv("cities.csv")\ndf.pivot(index="city", columns="year", values="population")\n',
    ),
    (
        "PD011",
        'import pandas as pd\n\nanimals = pd.read_csv("animals.csv").values  # Ambiguous.\n',
    ),
    (
        "PD012",
        'import pandas as pd\n\ncities_df = pd.read_table("cities.csv", sep=",")\n',
    ),
    (
        "PD013",
        'import pandas as pd\n\ncities_df = pd.read_csv("cities.csv")\ncities_df.set_index("city").stack()\n',
    ),
    (
        "PD015",
        'import pandas as pd\n\ncats_df = pd.read_csv("cats.csv")\ndogs_df = pd.read_csv("dogs.csv")\nrabbits_df = pd.read_csv("rabbits.csv")\npets_df = pd.merge(pd.merge(cats_df, dogs_df), rabbits_df)  # Hard to read.\n',
    ),
    (
        "PD101",
        'import pandas as pd\n\ndata = pd.Series(range(1000))\nif data.nunique() <= 1:\n    print("Series is constant")\n',
    ),
    ("PYI013", "class Foo:\n    ...\n    value: int\n"),
    ("PYI016", "foo: str | str\n"),
    (
        "PYI018",
        'import typing\nimport typing_extensions\n\n_T = typing.TypeVar("_T")\n_Ts = typing_extensions.TypeVarTuple("_Ts")\n',
    ),
    (
        "PYI019",
        'from typing import TypeVar\n\n_S = TypeVar("_S", bound="Foo")\n\nclass Foo:\n    def __new__(cls: type[_S], *args: str, **kwargs: int) -> _S: ...\n    def foo(self: _S, arg: bytes) -> _S: ...\n    @classmethod\n    def bar(cls: type[_S], arg: int) -> _S: ...\n',
    ),
    ("PYI030", "from typing import Literal\n\nfield: Literal[1] | Literal[2] | str\n"),
    (
        "PYI032",
        "from typing import Any\n\nclass Foo:\n    def __eq__(self, obj: Any) -> bool: ...\n",
    ),
    ("PYI041", "def foo(x: float | int | str) -> None: ...\n"),
    ("PYI042", "from typing import TypeAlias\n\ntype_alias_name: TypeAlias = int\n"),
    ("PYI043", "from typing import TypeAlias\n\n_MyTypeT: TypeAlias = int\n"),
    (
        "PYI045",
        "import collections.abc\n\n\nclass Klass:\n    def __iter__(self) -> collections.abc.Iterable[str]: ...\n",
    ),
    (
        "PYI046",
        "import typing\n\nclass _PrivateProtocol(typing.Protocol):\n    foo: int\n",
    ),
    ("PYI047", "import typing\n\n_UnusedTypeAlias: typing.TypeAlias = int\n"),
    (
        "PYI049",
        "import typing\n\nclass _UnusedPrivateTypedDict(typing.TypedDict):\n    foo: list[int]\n",
    ),
    ("PYI051", 'from typing import Literal\n\nx: Literal["A", b"B"] | str\n'),
    (
        "PYI056",
        'import sys\n\n__all__ = ["A", "B"]\n\nif sys.version_info >= (3, 10):\n    __all__.append("C")\n\nif sys.version_info >= (3, 11):\n    __all__.remove("B")\n',
    ),
    ("PYI057", "from typing import ByteString\n"),
    (
        "PYI059",
        'from typing import Generic, TypeVar\n\nT = TypeVar("T")\n\nclass Foo(Generic[T], list[T]): ...\n',
    ),
    (
        "PYI061",
        'from typing import Literal\n\nLiteral[None]\nLiteral[1, 2, 3, "foo", 5, None]\n',
    ),
    ("PYI062", 'from typing import Literal\n\nfoo: Literal["a", "b", "a"]\n'),
    ("PYI063", "def foo(__x: int) -> None: ...\n"),
    (
        "PYI064",
        "from typing import Final, Literal\n\nx: Final[Literal[42]]\ny: Final[Literal[42]] = 42\n",
    ),
    # Rules of families that are not enabled (formatter, docstrings, naming), which nothing in the code breaks.
    ("COM819", "foo = (1, 2, 3,)\n"),
    (
        "D106",
        'class Foo:\n    """Class Foo."""\n\n    class Bar: ...\n\n\nbar = Foo.Bar()\nbar.__doc__  # None\n',
    ),
    (
        "D201",
        'def average(values: list[float]) -> float:\n\n    """Return the mean of the given values."""\n',
    ),
    (
        "D204",
        'class PhotoMetadata:\n    """Metadata about a photo."""\n    def __init__(self, file: Path):\n        ...\n',
    ),
    (
        "D206",
        'def sort_list(l: list[int]) -> list[int]:\n    """Return a sorted copy of the list.\n\n\tSort the list in ascending order and return a copy of the result using the bubble\n\tsort algorithm.\n    """\n',
    ),
    (
        "D207",
        'def sort_list(l: list[int]) -> list[int]:\n    """Return a sorted copy of the list.\n\nSort the list in ascending order and return a copy of the result using the bubble sort\nalgorithm.\n    """\n',
    ),
    ("D210", 'def factorial(n: int) -> int:\n    """ Return the factorial of n. """\n'),
    ("D211", 'class PhotoMetadata:\n\n    """Metadata about a photo."""\n'),
    (
        "D215",
        'def calculate_speed(distance: float, time: float) -> float:\n    """Calculate speed as distance divided by time.\n\n    Parameters\n        ----------\n    distance : float\n        Distance traveled.\n    time : float\n        Time spent traveling.\n\n    Returns\n          -------\n    float\n        Speed as distance divided by time.\n\n    Raises\n      ------\n    FasterThanLightError\n        If speed is greater than the speed of light.\n    """\n    try:\n        return distance / time\n    except ZeroDivisionError as exc:\n        raise FasterThanLightError from exc\n',
    ),
    (
        "D408",
        'def calculate_speed(distance: float, time: float) -> float:\n    """Calculate speed as distance divided by time.\n\n    Parameters\n\n    ----------\n    distance : float\n        Distance traveled.\n    time : float\n        Time spent traveling.\n\n    Returns\n\n    -------\n    float\n        Speed as distance divided by time.\n\n    Raises\n\n    ------\n    FasterThanLightError\n        If speed is greater than the speed of light.\n    """\n    try:\n        return distance / time\n    except ZeroDivisionError as exc:\n        raise FasterThanLightError from exc\n',
    ),
    (
        "D418",
        'from typing import overload\n\n\n@overload\ndef factorial(n: int) -> int:\n    """Return the factorial of n."""\n\n\n@overload\ndef factorial(n: float) -> float:\n    """Return the factorial of n."""\n\n\ndef factorial(n):\n    """Return the factorial of n."""\n\n\nfactorial.__doc__  # "Return the factorial of n."\n',
    ),
    ("ISC002", 'z = "The quick brown fox jumps over the lazy "\\\n    "dog."\n'),
    ("N811", "from example import CONSTANT_VALUE as ConstantValue\n"),
    ("N814", "from example import MyClassName as MY_CLASS_NAME\n"),
    ("Q001", "foo = '''\nbar\n'''\n"),
    ("Q002", "'''\nbar\n'''\n"),
    ("Q003", 'foo = "bar\\"s"\n'),
    ("Q004", 'foo = "bar\\\'s"\n'),
    ("W191", "if True:\n\tx = 1\n"),
    # Rules for the code that handles data from outside. The tests are exempt, see below.
    (
        "S301",
        'import pickle\n\nwith open("foo.pickle", "rb") as file:\n    foo = pickle.load(file)\n',
    ),
    ("S602", 'import subprocess\n\nsubprocess.run("ls -l", shell=True)\n'),
]


@pytest.mark.parametrize(("code", "source"), NEW_RULE_CASES, ids=lambda v: v[:8])
def test_rules_without_existing_violations(repo: Path, code: str, source: str) -> None:
    write(repo, "salt/new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="No executable bit on Windows")
def test_executable_file_without_shebang_is_reported(repo: Path) -> None:
    write(repo, "salt/new.py", "value = 1\n")
    (repo / "salt/new.py").chmod(0o755)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "EXE002" in result.stdout


def test_top_level_module_named_like_a_standard_library_module_is_reported(
    repo: Path,
) -> None:
    write(repo, "json.py", "value = 1\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "A005" in result.stdout


# Rules that only look at the type stub files (.pyi).
STUB_RULE_CASES = [
    ("PYI001", 'from typing import TypeVar\n\nT = TypeVar("T")\n'),
    ("PYI002", "import sys\n\nif (3, 10) <= sys.version_info < (3, 12): ...\n"),
    ("PYI003", 'import sys\n\nif sys.version_info[0] == "2": ...\n'),
    ("PYI004", "import sys\n\nif sys.version_info >= (3, 4, 3): ...\n"),
    ("PYI005", "import sys\n\nif sys.version_info[:2] == (3,): ...\n"),
    (
        "PYI007",
        'import sys\n\nif sys.platform == "xunil"[::-1]:\n    # Linux specific definitions\n    ...\nelse:\n    # Posix specific definitions\n    ...\n',
    ),
    ("PYI008", 'import sys\n\nif sys.platform == "linus": ...\n'),
    ("PYI009", "def foo(bar: int) -> list[int]: pass\n"),
    ("PYI010", "def double(x: int) -> int:\n    return x * 2\n"),
    ("PYI011", "def foo(arg: list[int] = list(range(10_000))) -> None: ...\n"),
    ("PYI012", "class MyClass:\n    x: int\n    pass\n"),
    ("PYI014", "def foo(arg=bar()) -> None: ...\n"),
    ("PYI015", "foo: str = bar()\n"),
    (
        "PYI017",
        "from typing import TypeAlias\n\na = b = int\n\nclass Klass: ...\n\nKlass.X: TypeAlias = int\n",
    ),
    ("PYI020", 'def function() -> "int": ...\n'),
    (
        "PYI021",
        'def func(param: int) -> str:\n    """This is a docstring."""\n    ...\n',
    ),
    ("PYI026", "Vector = list[float]\n"),
    ("PYI029", "class Foo:\n    def __repr__(self) -> str: ...\n"),
    ("PYI033", "x = 1  # type: int\n"),
    ("PYI035", "__all__: list[str]\n"),
    ("PYI044", "from __future__ import annotations\n"),
    ("PYI048", "def function():\n    x = 1\n    y = 2\n    return x + y\n"),
    ("PYI050", "from typing import NoReturn\n\ndef foo(x: NoReturn): ...\n"),
    ("PYI052", "field = 0\n"),
    (
        "PYI053",
        'def foo(arg: str = "51 character stringgggggggggggggggggggggggggggggggg") -> None: ...\n',
    ),
    (
        "PYI054",
        "def foo(arg: int = 693568516352839939918568862861217771399698285293568) -> None: ...\n",
    ),
    ("PYI055", "field: type[int] | type[float] | str\n"),
    (
        "PYI058",
        "from typing import Generator\n\nclass Foo:\n    def __iter__(self) -> Generator[int, None, None]: ...\n",
    ),
    (
        "PYI066",
        "import sys\n\nif sys.version_info < (3, 10):\n    def read_data(x, *, preserve_order=True): ...\n\nelse:\n    def read_data(x): ...\n",
    ),
]


@pytest.mark.parametrize(("code", "source"), STUB_RULE_CASES, ids=lambda v: v[:8])
def test_rules_for_stub_files(repo: Path, code: str, source: str) -> None:
    write(repo, "salt/new.pyi", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout


def test_directory_without_init_is_reported_in_the_product_code(repo: Path) -> None:
    write(repo, "salt/newpkg/module.py", "value = 1\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "INP001" in result.stdout


EXEMPT_CASES = [
    # The tests run commands they wrote, unpickle what they pickled, use made-up passwords.
    (
        "tests/pytests/new.py",
        'import subprocess\n\nsubprocess.Popen("ls", shell=True)\n',
    ),
    ("tests/pytests/new.py", "import pickle\n\npickle.loads(pickle.dumps(1))\n"),
    ("tests/pytests/new.py", 'def f(connect):\n    connect(password="secret")\n'),
    # The directories of the tests and of the scripts are not packages.
    ("tests/newdir/new.py", "value = 1\n"),
    ("tools/newdir/new.py", "value = 1\n"),
    (".github/scripts/new.py", "value = 1\n"),
]


@pytest.mark.parametrize(("path", "source"), EXEMPT_CASES, ids=lambda v: v[:20])
def test_rules_are_not_enforced_where_they_do_not_apply(
    repo: Path, path: str, source: str
) -> None:
    write(repo, path, source)
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


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
    # Rules enabled in the second wave: a few existing violations. Only new ones
    # block a PR.
    ("A003", "class C:\n    def next(self):\n        pass\n\n    __next__ = next\n"),
    ("A004", 'from rich import print\n\nprint("Some message")\n'),
    ("B028", 'import warnings\n\nwarnings.warn("This is a warning")\n'),
    ("C400", "list(f(x) for x in foo)\nlist(x for x in foo)\nlist((x for x in foo))\n"),
    ("C406", "dict([(1, 2), (3, 4)])\ndict(((1, 2), (3, 4)))\ndict([])\n"),
    ("C409", "tuple([1, 2])\ntuple((1, 2))\n"),
    ("C413", "reversed(sorted(iterable))\n"),
    ("C418", 'dict({})\ndict({"a": 1})\n'),
    ("DTZ012", "import datetime\n\ndatetime.date.fromtimestamp(946684800)\n"),
    ("FURB105", 'print("")\n'),
    ("FURB116", "print(bin(1337)[2:])\n"),
    (
        "FURB122",
        'from pathlib import Path\n\nwith Path("file").open("w") as f:\n    for line in lines:\n        f.write(line)\n\nwith Path("file").open("wb") as f_b:\n    for line_b in lines_b:\n        f_b.write(line_b.encode())\n',
    ),
    (
        "FURB129",
        'with open("file.txt") as fp:\n    for line in fp.readlines():\n        ...\n',
    ),
    ("FURB132", "nums = {123, 456}\n\nif 123 in nums:\n    nums.remove(123)\n"),
    (
        "FURB136",
        "score1, score2 = 4, 5\n\nhighest_score = score1 if score1 > score2 else score2\n",
    ),
    (
        "FURB157",
        'from decimal import Decimal\n\nDecimal("0")\nDecimal(float("Infinity"))\n',
    ),
    ("FURB177", "from pathlib import Path\n\ncwd = Path().resolve()\n"),
    (
        "FURB192",
        "nums = [3, 1, 4, 1, 5]\nlowest = sorted(nums)[0]\nhighest = sorted(nums)[-1]\nhighest = sorted(nums, reverse=True)[0]\n",
    ),
    (
        "G001",
        'import logging\n\nlogging.basicConfig(format="%(message)s", level=logging.INFO)\n\nuser = "Maria"\n\nlogging.info("{} - Something happened".format(user))\n',
    ),
    ("LOG015", 'import logging\n\nlogging.info("Foobar")\n'),
    ("PERF101", "items = (1, 2, 3)\nfor i in list(items):\n    print(i)\n"),
    ("PIE800", 'foo = {"A": 1, "B": 2}\nbar = {**foo, **{"C": 3}}\n'),
    (
        "PIE807",
        "from dataclasses import dataclass, field\n\n\n@dataclass\nclass Foo:\n    bar: list[int] = field(default_factory=lambda: [])\n",
    ),
    ("PLC0207", 'url = "www.example.com"\nprefix = url.split(".")[0]\n'),
    ("PLR0124", "foo == foo\n"),
    (
        "PLR1716",
        "a = int(input())\nb = int(input())\nc = int(input())\nif a < b and b < c:\n    pass\n",
    ),
    ("PLR1722", 'if __name__ == "__main__":\n    exit()\n'),
    (
        "PLR1736",
        'letters = ["a", "b", "c"]\n\nfor index, letter in enumerate(letters):\n    print(letters[index])\n',
    ),
    ("PLW0108", "df.apply(lambda x: str(x))\n"),
    ("PT013", "import pytest as pt\nfrom pytest import fixture\n"),
    (
        "PT021",
        "import pytest\n\n\n@pytest.fixture()\ndef my_fixture(request):\n    resource = acquire_resource()\n    request.addfinalizer(resource.release)\n    return resource\n",
    ),
    ("PT023", "import pytest\n\n\n@pytest.mark.foo()\ndef test_something(): ...\n"),
    ("PTH121", 'import os\n\nos.path.samefile("f1.py", "f2.py")\n'),
    ("PTH205", "import os\n\nos.path.getctime(__file__)\n"),
    (
        "PTH206",
        'import os\n\n"path/to/file_name.txt".split(os.sep)[-1]\n\n"path/to/file_name.txt".split(os.sep)[-2]\n\n# Iterating over the path parts\nif any(part in blocklist for part in "my/file/path".split(os.sep)):\n    ...\n',
    ),
    ("PYI006", "import sys\n\nif sys.version_info > (3, 0):\n    pass\n"),
    ("PYI025", "from collections.abc import Set\n"),
    (
        "PYI034",
        'class Foo:\n    def __new__(cls, *args, **kwargs) -> "Foo":\n        return super().__new__(cls)\n',
    ),
    ("PYI036", "class Foo:\n    def __exit__(self):\n        pass\n"),
    ("RUF017", "lists = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]\njoined = sum(lists, [])\n"),
    (
        "RUF022",
        'import sys\n\n__all__ = [\n    "b",\n    "c",\n    "a",\n]\n\nif sys.platform == "win32":\n    __all__ += ["z", "y"]\n',
    ),
    ("RUF023", 'class Dog:\n    __slots__ = "name", "breed"\n'),
    ("RUF102", "import os  # noqa: XYZ999\n"),
    ("SIM109", "if foo == x or foo == y:\n    ...\n"),
    (
        "SIM116",
        'def find_phrase(x):\n    if x == 1:\n        return "Hello"\n    elif x == 2:\n        return "Goodbye"\n    elif x == 3:\n        return "Good morning"\n    else:\n        return "Goodnight"\n',
    ),
    ("SIM208", "not (not a)\n"),
    ("SIM211", "False if a else True\n"),
    ("SIM222", "if x or [1] or y:\n    pass\n\na = x or [1] or y\n"),
    ("SIM905", '"a,b,c,d".split(",")\n'),
    ("SLOT000", "class Foo(str):\n    pass\n"),
    ("SLOT001", "class Foo(tuple):\n    pass\n"),
    (
        "SLOT002",
        'from collections import namedtuple\n\n\nclass Foo(namedtuple("foo", ["str", "int"])):\n    pass\n',
    ),
    ("TC006", "from typing import cast\n\nx = cast(dict[str, int], foo)\n"),
    (
        "TRY201",
        "def foo():\n    try:\n        ...\n    except ValueError as exc:\n        raise exc\n",
    ),
    (
        "TRY203",
        "def foo():\n    try:\n        bar()\n    except NotImplementedError:\n        raise\n",
    ),
    # Rules enabled in the third wave: existing violations. Only new ones block a PR.
    (
        "A001",
        "def find_max(list_of_lists):\n    max = 0\n    for flat_list in list_of_lists:\n        for value in flat_list:\n            max = max(max, value)  # TypeError: 'int' object is not callable\n    return max\n",
    ),
    ("B009", 'getattr(obj, "foo")\n'),
    ("B010", 'setattr(obj, "foo", 42)\n'),
    ("C414", "list(tuple(iterable))\n"),
    (
        "C416",
        "{a: b for a, b in iterable}\n[x for x in iterable]\n{x for x in iterable}\n",
    ),
    (
        "C419",
        "any([x.id for x in bar])\nall([x.id for x in bar])\nsum([x.val for x in bar])\nmin([x.val for x in bar])\nmax([x.val for x in bar])\n",
    ),
    ("C420", "{a: None for a in iterable}\n{a: 1 for a in iterable}\n"),
    ("E741", "l = 0\nO = 123\nI = 42\n"),
    ("EXE001", "#!/usr/bin/env python\n"),
    ("FURB110", "x, y = 1, 2\n\nz = x if x else y\n"),
    ("FURB167", 'import re\n\nif re.search("^hello", "hello world", re.I):\n    ...\n'),
    ("FURB171", "1 in [1]\n"),
    (
        "G201",
        'import logging\n\ntry:\n    ...\nexcept ValueError:\n    logging.error("Exception occurred", exc_info=True)\n',
    ),
    (
        "PERF102",
        'obj = {"a": 1, "b": 2}\nfor key, value in obj.items():\n    print(value)\n',
    ),
    (
        "PERF402",
        "original = list(range(10000))\nfiltered = []\nfor i in original:\n    filtered.append(i)\n",
    ),
    (
        "PERF403",
        'pairs = (("a", 1), ("b", 2))\nresult = {}\nfor x, y in pairs:\n    if y % 2:\n        result[x] = y\n',
    ),
    (
        "PIE804",
        'def foo(bar):\n    return bar + 1\n\n\nprint(foo(**{"bar": 2}))  # prints 3\n\n# No typing errors, but results in an exception at runtime.\nprint(foo(**{"bar": 2, "baz": 3}))\n',
    ),
    ("PIE808", "range(0, 3)\n"),
    (
        "PIE810",
        'msg = "Hello, world!"\nif msg.startswith("Hello") or msg.startswith("Hi"):\n    print("Greetings!")\n',
    ),
    (
        "PLC0206",
        'ORCHESTRA = {\n    "violin": "strings",\n    "oboe": "woodwind",\n    "tuba": "brass",\n    "gong": "percussion",\n}\n\nfor instrument in ORCHESTRA:\n    print(f"{instrument}: {ORCHESTRA[instrument]}")\n',
    ),
    (
        "PLR1704",
        'def show(host_id=10.11):\n    for host_id, host in [[12.13, "Venus"], [14.15, "Mars"]]:\n        print(host_id, host)\n',
    ),
    ("PLR1711", "def f():\n    print(5)\n    return None\n"),
    ("PLR1714", 'foo == "bar" or foo == "baz" or foo == "qux"\n'),
    ("PLR1730", "if score > highest_score:\n    highest_score = score\n"),
    (
        "PLR1733",
        'FRUITS = {"apple": 1, "orange": 10, "berry": 22}\n\nfor fruit_name, fruit_count in FRUITS.items():\n    print(FRUITS[fruit_name])\n',
    ),
    ("PT001", "import pytest\n\n\n@pytest.fixture()\ndef my_fixture(): ...\n"),
    (
        "PT003",
        'import pytest\n\n\n@pytest.fixture(scope="function")\ndef my_fixture(): ...\n',
    ),
    (
        "PT011",
        'import pytest\n\n\ndef test_foo():\n    with pytest.raises(ValueError):\n        ...\n\n    # empty string is also an error\n    with pytest.raises(ValueError, match=""):\n        ...\n',
    ),
    (
        "PT012",
        "import pytest\n\n\ndef test_foo():\n    with pytest.raises(MyError):\n        setup()\n        func_to_test()  # not executed if `setup()` raises `MyError`\n        assert foo()  # not executed\n",
    ),
    (
        "PT018",
        "def test_foo():\n    assert something and something_else\n\n\ndef test_bar():\n    assert not (something or something_else)\n",
    ),
    ("PT028", "def test_foo(a=1): ...\n"),
    ("RET501", "def foo(bar):\n    if not bar:\n        return\n    return None\n"),
    ("RET502", "def foo(bar):\n    if not bar:\n        return\n    return 1\n"),
    (
        "RET507",
        "def foo(bar, baz):\n    for i in bar:\n        if i < baz:\n            continue\n        else:\n            x = 0\n",
    ),
    (
        "RET508",
        "def foo(bar, baz):\n    for i in bar:\n        if i > baz:\n            break\n        else:\n            x = 0\n",
    ),
    ("RSE102", "raise TypeError()\n"),
    ("RUF010", 'a = "some string"\nf"{repr(a)}"\n'),
    ("RUF013", "def foo(arg: int = None):\n    pass\n"),
    ("RUF021", "a = True\nb = False\nc = True\nx = a and b or c\n"),
    ("RUF046", "int(len([]))\nint(round(foo, None))\n"),
    ("RUF051", "dictionary = {}\nif key in dictionary:\n    del dictionary[key]\n"),
    (
        "SIM110",
        "def foo():\n    for item in iterable:\n        if predicate(item):\n            return True\n    return False\n",
    ),
    (
        "SIM113",
        'fruits = ["apple", "banana", "cherry"]\ni = 0\nfor fruit in fruits:\n    print(f"{i + 1}. {fruit}")\n    i += 1\n',
    ),
    ("SIM118", "key in foo.keys()\n"),
    ("SIM201", "not a == b\n"),
    ("SIM210", "True if a else False\n"),
    ("SIM212", "b if not a else a\n"),
    (
        "SIM401",
        'foo = {}\nif "bar" in foo:\n    value = foo["bar"]\nelse:\n    value = 0\n',
    ),
    (
        "SIM910",
        'ages = {"Tom": 23, "Maria": 23, "Dog": 11}\nage = ages.get("Cat", None)\n',
    ),
    (
        "TRY002",
        'def main_function():\n    if not cond:\n        raise Exception()\n\n\ndef consumer_func():\n    try:\n        do_step()\n        prepare()\n        main_function()\n    except Exception:\n        logger.error("Oops")\n',
    ),
    # Rules enabled in the fourth wave: existing violations. Only new ones block a PR.
    ("B007", "for i, j in foo:\n    bar(i)\n"),
    (
        "B904",
        'try:\n    ...\nexcept FileNotFoundError:\n    if ...:\n        raise RuntimeError("...")\n    else:\n        raise UserWarning("...")\n',
    ),
    ("RET503", "def foo(bar):\n    if not bar:\n        return 1\n"),
    (
        "RUF012",
        "class A:\n    variable_1: list[int] = []\n    variable_2: set[int] = set()\n    variable_3: dict[str, int] = {}\n",
    ),
    # Security rules enabled with existing violations. Only new ones block a PR.
    ("S102", "exec(\"print('Hello World')\")\n"),
    ("S107", 'def connect_to_server(password="hunter2"): ...\n'),
    (
        "S202",
        "import tarfile\nimport tempfile\n\ntar = tarfile.open(filename)\ntar.extractall(path=tempfile.mkdtemp())\ntar.close()\n",
    ),
    # Rules enabled with an existing violation. Only new ones block a PR.
    (
        "RUF007",
        'letters = "ABCD"\nzip(letters, letters[1:])  # ("A", "B"), ("B", "C"), ("C", "D")\n',
    ),
    ("S106", 'connect_to_server(password="hunter2")\n'),
]


@pytest.mark.parametrize(
    ("code", "source"), RULES_WITH_EXISTING_VIOLATIONS, ids=lambda v: v[:8]
)
def test_rules_with_existing_violations(repo: Path, code: str, source: str) -> None:
    write(repo, "salt/new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout

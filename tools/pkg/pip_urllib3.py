"""
Helpers to make the urllib3 vendored inside a pip wheel match the urllib3
Salt itself ships.

pip vendors urllib3 and lags upstream releases. When a urllib3 release fixes
a security issue, the pip wheel Salt packages (and the copy virtualenv embeds
to seed new virtualenvs) would keep shipping the vulnerable vendored copy. At
build time we overlay the urllib3 version pinned in Salt's lockfiles onto the
wheel and re-apply the few edits pip's own vendoring makes.

This module is deliberately free of ``ptscripts``/``tools`` imports so it can
be unit tested on its own.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import pathlib
import re
import zipfile

VENDOR_PREFIX = "pip/_vendor/urllib3/"

# Files pip adds to its vendored copy that upstream's wheel does not ship in
# the ``urllib3/`` package directory.
PIP_ONLY_FILES = frozenset({"LICENSE.txt"})

_VERSION_RE = re.compile(
    r"""^__version__\s*=\s*(?:version\s*=\s*)?["']([^"']+)["']""", re.MULTILINE
)

# Matches an import of a module pip vendors under ``pip._vendor`` (or that pip
# strips out) which was not rewritten.
_UNREWRITTEN_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(?:urllib3|idna|brotli|brotlicffi)\b", re.MULTILINE
)

_BROTLI_IMPORT_RE = re.compile(
    r"^try:\n"
    r"    try:\n"
    r"        import brotlicffi as brotli[^\n]*\n"
    r"    except ImportError:\n"
    r"        import brotli[^\n]*\n"
    r"except ImportError:\n"
    r"    brotli = None\n",
    re.MULTILINE,
)
_BROTLI_ACCEPT_ENCODING_RE = re.compile(
    r"^try:\n"
    r"    try:\n"
    r"        import brotlicffi as _unused_module_brotli[^\n]*\n"
    r"    except ImportError:\n"
    r"        import brotli as _unused_module_brotli[^\n]*\n"
    r"except ImportError:\n"
    r"    pass\n"
    r"else:\n"
    r'    ACCEPT_ENCODING \+= ",br"\n',
    re.MULTILINE,
)

# Edits pip's vendoring applies to specific files. Every rule listed here
# must match, otherwise upstream changed in a way these rules do not cover
# and we refuse to build a wheel with a half-rewritten urllib3.
_FILE_EDITS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "contrib/emscripten/__init__.py": [
        (
            re.compile(r"^import urllib3\.connection$", re.MULTILINE),
            "import pip._vendor.urllib3.connection as urllib3_connection",
        ),
        (
            re.compile(r"^(\s+)urllib3\.connection\.(\w+) =", re.MULTILINE),
            r"\1urllib3_connection.\2 =",
        ),
    ],
    "contrib/pyopenssl.py": [
        (
            re.compile(r"^(\s+)import urllib3\.contrib\.pyopenssl$", re.MULTILINE),
            r"\1import pip._vendor.urllib3.contrib.pyopenssl as pyopenssl",
        ),
        (
            re.compile(
                r"^(\s+)urllib3\.contrib\.pyopenssl\.inject_into_urllib3\(\)$",
                re.MULTILINE,
            ),
            r"\1pyopenssl.inject_into_urllib3()",
        ),
    ],
    "response.py": [(_BROTLI_IMPORT_RE, "brotli = None\n")],
    "util/request.py": [(_BROTLI_ACCEPT_ENCODING_RE, "")],
}

# Edits applied to every file; these do not need to match anything.
_GLOBAL_EDITS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^(\s+)import urllib3$", re.MULTILINE),
        r"\1from pip._vendor import urllib3",
    ),
    (
        re.compile(r"^(\s+)import idna$", re.MULTILINE),
        r"\1from pip._vendor import idna",
    ),
]


def parse_version(version: str) -> tuple[int, ...]:
    """
    Return the leading numeric components of a version string.
    """
    parts = []
    for part in version.split("."):
        match = re.match(r"\d+", part)
        if match is None:
            break
        parts.append(int(match.group()))
    return tuple(parts)


def urllib3_pin_from_lock(
    lock_file: pathlib.Path, python_version: tuple[int, int]
) -> str | None:
    """
    Return the urllib3 version *lock_file* pins for *python_version*, or
    ``None`` when there is nothing to overlay (Python older than 3.10, which
    stays on urllib3 1.x, or no urllib3 pin).
    """
    if python_version < (3, 10):
        return None
    pin_re = re.compile(r"^urllib3==(?P<version>[^\s;]+)\s*(?:;(?P<marker>.*))?$")
    for line in lock_file.read_text(encoding="utf-8").splitlines():
        match = pin_re.match(line.strip())
        if match is None:
            continue
        marker = match.group("marker") or ""
        # Some lockfiles carry one pin per Python range, e.g.
        # ``urllib3==1.26.20 ; python_full_version < '3.10'``.
        if re.search(r"<\s*['\"]3\.10['\"]", marker):
            continue
        version = match.group("version")
        if parse_version(version) < (2,):
            return None
        return version
    return None


def vendored_version(pip_wheel: pathlib.Path) -> str:
    """
    Return the version of the urllib3 vendored inside *pip_wheel*.
    """
    with zipfile.ZipFile(pip_wheel) as zf:
        text = zf.read(f"{VENDOR_PREFIX}_version.py").decode("utf-8")
    match = _VERSION_RE.search(text)
    if match is None:
        raise ValueError(f"Could not parse the urllib3 version from {pip_wheel.name}")
    return match.group(1)


def transform_source(relpath: str, text: str) -> str:
    """
    Apply pip's vendoring edits to the upstream urllib3 source *text* of the
    file *relpath* (relative to the ``urllib3`` package directory).
    """
    for pattern, replacement in _FILE_EDITS.get(relpath, ()):
        text, count = pattern.subn(replacement, text)
        if not count:
            raise ValueError(
                f"urllib3 {relpath}: expected pip vendoring edit not found "
                f"({pattern.pattern!r}); update tools/pkg/pip_urllib3.py"
            )
    for pattern, replacement in _GLOBAL_EDITS:
        text = pattern.sub(replacement, text)
    leftover = _UNREWRITTEN_IMPORT_RE.search(text)
    if leftover:
        raise ValueError(
            f"urllib3 {relpath}: un-vendored import left after rewriting: "
            f"{leftover.group().strip()!r}; update tools/pkg/pip_urllib3.py"
        )
    return text


def _record_hash(content: bytes) -> str:
    digest = hashlib.sha256(content).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode().rstrip("=")


def overlay_urllib3(pip_wheel: pathlib.Path, urllib3_wheel: pathlib.Path) -> bool:
    """
    Replace the urllib3 vendored inside *pip_wheel* with the one from
    *urllib3_wheel*, applying pip's vendoring edits and updating RECORD.

    The wheel is rewritten in place. Returns ``False`` without touching it
    when the vendored urllib3 is already at least as new as *urllib3_wheel*.
    """
    with zipfile.ZipFile(urllib3_wheel) as zf:
        new_files: dict[str, bytes] = {}
        for name in zf.namelist():
            if name.endswith("/") or not name.startswith("urllib3/"):
                continue
            relpath = name[len("urllib3/") :]
            data = zf.read(name)
            if relpath.endswith(".py"):
                data = transform_source(relpath, data.decode("utf-8")).encode("utf-8")
            new_files[VENDOR_PREFIX + relpath] = data
        version_match = _VERSION_RE.search(
            new_files[f"{VENDOR_PREFIX}_version.py"].decode("utf-8")
        )
    if version_match is None:
        raise ValueError(f"Could not parse the version from {urllib3_wheel.name}")
    target_version = version_match.group(1)

    if parse_version(vendored_version(pip_wheel)) >= parse_version(target_version):
        return False

    tmp_path = pip_wheel.with_suffix(".tmp.whl")
    try:
        with zipfile.ZipFile(pip_wheel) as zin, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as zout:
            record_name = None
            record_rows: list[list[str]] = []
            written: set[str] = set()
            template = zin.getinfo(f"{VENDOR_PREFIX}_version.py")
            for item in zin.infolist():
                name = item.filename
                if name.endswith(".dist-info/RECORD"):
                    record_name = name
                    record_rows = list(
                        csv.reader(zin.read(name).decode("utf-8").splitlines())
                    )
                    continue
                if name.startswith(VENDOR_PREFIX):
                    relpath = name[len(VENDOR_PREFIX) :]
                    if name in new_files:
                        zout.writestr(item, new_files[name])
                        written.add(name)
                    elif relpath in PIP_ONLY_FILES:
                        zout.writestr(item, zin.read(name))
                    # else: file no longer exists upstream; drop it.
                    continue
                zout.writestr(item, zin.read(name))
            for name in sorted(set(new_files) - written):
                info = zipfile.ZipInfo(name, date_time=template.date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = template.external_attr
                zout.writestr(info, new_files[name])

            if record_name is None:
                raise ValueError(f"No RECORD found in {pip_wheel.name}")
            new_rows: list[list[str]] = []
            seen: set[str] = set()
            for row in record_rows:
                path = row[0] if row else ""
                if path.startswith(VENDOR_PREFIX):
                    if path in new_files:
                        content = new_files[path]
                        new_rows.append(
                            [path, _record_hash(content), str(len(content))]
                        )
                        seen.add(path)
                    elif path[len(VENDOR_PREFIX) :] in PIP_ONLY_FILES:
                        new_rows.append(row)
                    continue
                new_rows.append(row)
            for path in sorted(set(new_files) - seen):
                content = new_files[path]
                new_rows.append([path, _record_hash(content), str(len(content))])
            # Keep RECORD's own (empty) row last, as wheel tooling expects.
            new_rows.sort(key=lambda row: row[0] == record_name)
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\n").writerows(new_rows)
            zout.writestr(record_name, buf.getvalue())
        tmp_path.replace(pip_wheel)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    final = vendored_version(pip_wheel)
    if final != target_version:
        raise ValueError(
            f"{pip_wheel.name} vendors urllib3 {final} after overlay, "
            f"expected {target_version}"
        )
    return True

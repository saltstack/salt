"""
Audit which Salt Python dependencies are shipped by target OSes as native
``python3-*`` packages, flag the gaps that must be vendored at
native-package build time, and infer per-pyver floors from what ships.

The three outputs this command group produces are:

* ``cicd/native-deps/<slug>.json`` -- per-distro audit of lock entries vs
  the OS's native ``python3-*`` repo, written by ``audit``.
* ``cicd/native-deps/floors.yml`` -- per-pyver proposed floors (min across
  distros that ship each dep natively) with gap-vs-lock annotations,
  written by ``floors``. Review artifact only -- promote to
  ``requirements/*.in`` by hand.
* ``cicd/native-deps/<slug>-vendor.txt`` -- per-distro list of
  ``pkg==ver`` pins that must be ``pip install``'d into the native
  package's ``_vendor/`` dir at build time, written by ``vendor-plan``.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import datetime
import json
import logging
import pathlib
import re
import subprocess
from typing import Any

import yaml
from packaging.version import InvalidVersion, Version
from ptscripts import Context, command_group

import tools.utils

log = logging.getLogger(__name__)

native_deps = command_group(
    name="native-deps",
    help="Native OS Python-dependency audit for native packages.",
    description=__doc__,
    parent="pkg",
)

AUDIT_DIR = tools.utils.REPO_ROOT / "cicd" / "native-deps"

# Backends
BACKEND_TDNF = "tdnf"
BACKEND_YUM_DNF = "yum-dnf"
BACKEND_APT = "apt"

# Debian/Ubuntu share one pkg-name translation table: Salt dep name (as it
# appears in the uv-compiled .lock) → the system package name on apt
# distros. Everything not listed here falls back to ``python3-<name>``.
DEB_PKGMAP = {
    "pytz": "python3-tz",
    "pyzmq": "python3-zmq",
    "pyyaml": "python3-yaml",
    "pycryptodomex": "python3-pycryptodome",
    "python-gnupg": "python3-gnupg",
    "python-dateutil": "python3-dateutil",
    "pyopenssl": "python3-openssl",
}

RHEL_PKGMAP = {
    "python-dateutil": "python3-dateutil",
    "pyzmq": "python3-zmq",
    "python-gnupg": "python3-gnupg",
}

AMAZON_PKGMAP = {
    "python-dateutil": "python3-dateutil",
    "pyzmq": "python3-pyzmq",
}

PHOTON_PKGMAP = {
    "python-dateutil": "python3-dateutil",
    "python-gnupg": "python3-gnupg",
    "pyzmq": "python3-zmq",
}

# Distro slug → (image, backend, needs_epel, pkgmap). Images are stock
# upstream tags so the audit reflects what the base distro repo ships, not
# whatever salt-ci-containers happens to have pre-provisioned.
DISTROS: dict[str, dict[str, Any]] = {
    "amazonlinux-2023": {
        "image": "amazonlinux:2023",
        "backend": BACKEND_YUM_DNF,
        "needs_epel": False,
        "pkgmap": AMAZON_PKGMAP,
    },
    "debian-12": {
        "image": "debian:12",
        "backend": BACKEND_APT,
        "needs_epel": False,
        "pkgmap": DEB_PKGMAP,
    },
    "debian-13": {
        "image": "debian:13",
        "backend": BACKEND_APT,
        "needs_epel": False,
        "pkgmap": DEB_PKGMAP,
    },
    "fedora-43": {
        "image": "fedora:43",
        "backend": BACKEND_YUM_DNF,
        "needs_epel": False,
        "pkgmap": RHEL_PKGMAP,
    },
    "photon-5": {
        "image": "photon:5.0",
        "backend": BACKEND_TDNF,
        "needs_epel": False,
        "pkgmap": PHOTON_PKGMAP,
    },
    "rockylinux-9": {
        "image": "rockylinux:9",
        "backend": BACKEND_YUM_DNF,
        "needs_epel": True,
        "pkgmap": RHEL_PKGMAP,
    },
    "ubuntu-22.04": {
        "image": "ubuntu:22.04",
        "backend": BACKEND_APT,
        "needs_epel": False,
        "pkgmap": DEB_PKGMAP,
    },
    "ubuntu-24.04": {
        "image": "ubuntu:24.04",
        "backend": BACKEND_APT,
        "needs_epel": False,
        "pkgmap": DEB_PKGMAP,
    },
    "ubuntu-26.04": {
        "image": "ubuntu:26.04",
        "backend": BACKEND_APT,
        "needs_epel": False,
        "pkgmap": DEB_PKGMAP,
    },
}

# Flavor notes keyed by lock-file dep name. Attached to the audit entry
# when a dep is missing from the native repo so reviewers can see at a
# glance whether a gap matters.
MISSING_NOTES = {
    "aiohttp": "needed for websocket transport",
    "aiosignal": "needed for websocket transport",
    "annotated-types": "missing ok",
    "async-timeout": "needed for websocket transport",
    "attrs": "missing ok",
    "autocommand": "missing ok",
    "charset-normalizer": "requests>=2.26.0 dependency",
    "cheroot": "cherrypy",
    "cherrypy": "salt-api degraded",
    "contextvars": "salt-ssh will not work",
    "croniter": "schedules can not use cron format",
    "frozenlist": "needed for websocket transport",
    "immutables": "salt-ssh will not work",
    "importlib-metadata": "used by jaraco.text",
    "importlib-resources": "needed on python < 3.10",
    "jaraco-classes": "missing ok",
    "jaraco-collections": "missing ok",
    "jaraco-context": "missing ok",
    "jaraco-functools": "missing ok",
    "jaraco-text": "missing ok",
    "looseversion": "used by many modules",
    "msgpack": "absolutely needed",
    "multidict": "needed for websocket transport",
    "networkx": "needed for state requisites",
    "packaging": "absolutely needed",
    "portend": "cherrypy",
    "pydantic-core": "needed for pydantic >= 2.0",
    "python-gnupg": "works if gpg binary available",
    "pyzmq": "absolutely needed",
    "rpm-vercmp": "missing ok",
    "setproctitle": "nice to have",
    "tempora": "cherrypy",
    "timelib": "missing ok",
    "yarl": "needed for websocket transport",
    "zc-lockfile": "cherrypy",
    "zipp": "needed by importlib-metadata",
}

# Entrypoint for the probe container. 'tail -f /dev/null' needs an inotify
# instance, which may be exhausted on busy workstations. 'sleep infinity'
# is not portable (Photon's coreutils rejects it). Max 32-bit int seconds
# works everywhere.
_SLEEP_SECONDS = "2147483647"


# Lock distribution name → Python import module name(s). Everything NOT
# listed falls back to ``name.replace("-", "_")``. The hand overrides
# cover the two awkward cases: names that start with ``py``/``python-``
# but import as something else (``pyyaml``→``yaml``) and PEP 420
# namespace packages (``jaraco-text``→``jaraco.text``).
IMPORT_NAMES: dict[str, list[str]] = {
    "apache-libcloud": ["libcloud"],
    "gitpython": ["git"],
    "googleapis-common-protos": ["google.api", "google.rpc"],
    "jaraco-classes": ["jaraco.classes"],
    "jaraco-collections": ["jaraco.collections"],
    "jaraco-context": ["jaraco.context"],
    "jaraco-functools": ["jaraco.functools"],
    "jaraco-text": ["jaraco.text"],
    "markdown-it-py": ["markdown_it"],
    "opentelemetry-api": ["opentelemetry"],
    "opentelemetry-exporter-otlp-proto-common": [
        "opentelemetry.exporter.otlp.proto.common"
    ],
    "opentelemetry-exporter-otlp-proto-http": [
        "opentelemetry.exporter.otlp.proto.http"
    ],
    "opentelemetry-exporter-prometheus": ["opentelemetry.exporter.prometheus"],
    "opentelemetry-proto": ["opentelemetry.proto"],
    "opentelemetry-sdk": ["opentelemetry.sdk"],
    "opentelemetry-semantic-conventions": ["opentelemetry.semconv"],
    "protobuf": ["google.protobuf"],
    "pycryptodomex": ["Cryptodome"],
    "pyopenssl": ["OpenSSL"],
    "python-dateutil": ["dateutil"],
    "python-discovery": ["discovery"],
    "python-gnupg": ["gnupg"],
    "pyyaml": ["yaml"],
    "pyzmq": ["zmq"],
    "typer-slim": ["typer"],
    "zc-lockfile": ["zc.lockfile"],
}

# Classification tiers for a lock dep's imports in salt/ source.
TIER_MODULE_TOP = "module-top"  # unindented import, owning module on hot path
TIER_FEATURE_OPT_IN = "feature-opt-in"  # unindented, but owner is lazy-loaded
TIER_INDENTED = "indented"  # only inside try/except or function bodies
TIER_NONE = "none"  # no import of this dep anywhere in salt/

# Salt files/dirs whose modules are lazy-imported only when a specific
# feature is selected at runtime. A module-top import inside one of
# these only ImportErrors on a deployment that opts into the feature;
# for a native build that doesn't support the feature the dep can be
# omitted without breaking core Salt. Prefixes ending in ``/`` match a
# whole subdir; others match an exact file path.
LAZY_FEATURE_OWNERS: dict[str, str] = {
    "salt/transport/zeromq.py": "zeromq transport",
    "salt/transport/tcp.py": "tcp transport",
    "salt/transport/ws.py": "ws transport",
    "salt/netapi/rest_cherrypy/": "cherrypy netapi backend",
    "salt/netapi/rest_tornado/": "tornado netapi backend",
}


def _feature_for_site(site: str) -> str | None:
    """Return the feature name owning this import site, else ``None``."""
    path = site.split(":", 1)[0]
    for prefix, feature in LAZY_FEATURE_OWNERS.items():
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return feature
        elif path == prefix:
            return feature
    return None


def import_names(lock_name: str) -> list[str]:
    """Return the candidate Python import names for a lock distribution name."""
    if lock_name in IMPORT_NAMES:
        return IMPORT_NAMES[lock_name]
    return [lock_name.replace("-", "_")]


def _parse_grep_output(stdout: str) -> tuple[list[str], list[str]]:
    """Split ``git grep -n`` output into (module-top sites, indented sites).

    A "module-top" site is any line whose content begins at column 0 --
    those are the imports that fire at module load time and will
    ImportError-crash the whole module.
    """
    sites_top: list[str] = []
    sites_indented: list[str] = []
    for raw in stdout.splitlines():
        try:
            path, lineno, content = raw.split(":", 2)
        except ValueError:
            continue
        if content.startswith((" ", "\t")):
            sites_indented.append(f"{path}:{lineno}")
        else:
            sites_top.append(f"{path}:{lineno}")
    return sites_top, sites_indented


def _classify_from_sites(
    sites_top: list[str], sites_indented: list[str]
) -> tuple[str, list[str], list[str]]:
    """Pick the dominant tier for a dep.

    Returns ``(tier, owning_features, sites)``. ``owning_features`` is
    populated only for ``feature-opt-in`` -- it names each lazy-loaded
    Salt subsystem the dep is reachable through so reviewers can see
    exactly which feature they'd forfeit by not vendoring the dep.

    Tier precedence: module-top (hot path) beats feature-opt-in beats
    indented beats none.
    """
    if sites_top:
        features: set[str] = set()
        on_hot_path = False
        for site in sites_top:
            feature = _feature_for_site(site)
            if feature is None:
                on_hot_path = True
            else:
                features.add(feature)
        sites = sites_top + sites_indented
        if on_hot_path:
            return TIER_MODULE_TOP, [], sites
        return TIER_FEATURE_OPT_IN, sorted(features), sites
    if sites_indented:
        return TIER_INDENTED, [], sites_indented
    return TIER_NONE, [], []


def classify_lock_name(
    repo_root: pathlib.Path, lock_name: str
) -> tuple[str, list[str], list[str], list[str]]:
    """Grep ``salt/`` for imports of each candidate name and pick a tier.

    Returns ``(tier, probed_imports, sites, owning_features)``:

    * ``tier`` -- ``module-top``, ``feature-opt-in``, ``indented``, or ``none``.
    * ``probed_imports`` -- the module names we grepped for (so reviewers
      can double-check the derivation was sane).
    * ``sites`` -- list of ``path:lineno`` strings for every import found,
      module-top first then indented.
    * ``owning_features`` -- for the ``feature-opt-in`` tier, the sorted
      list of Salt features the dep is reachable through. Empty for
      every other tier.
    """
    probed = import_names(lock_name)
    all_top: list[str] = []
    all_indented: list[str] = []
    for mod in probed:
        # Match ``import mod`` or ``from mod`` with word boundary on the
        # right so ``import foo`` doesn't also match ``import foobar``.
        pat = (
            r"^(\s*)(import " + re.escape(mod) + r"|from " + re.escape(mod) + r")"
            r"(\s|\.|$)"
        )
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "grep", "-nE", pat, "--", "salt/"],
            capture_output=True,
            check=False,
            text=True,
        )
        if proc.returncode not in (0, 1):
            # 0 = matches, 1 = no match. Anything else is a real error.
            continue
        top, indented = _parse_grep_output(proc.stdout)
        all_top.extend(top)
        all_indented.extend(indented)
    tier, features, sites = _classify_from_sites(all_top, all_indented)
    return tier, probed, sites, features


def _dexec(container: str, *args: str) -> subprocess.CompletedProcess:
    """``docker container exec`` wrapper. Captures and returns the proc."""
    return subprocess.run(
        ["docker", "container", "exec", container, *args],
        capture_output=True,
        check=False,
    )


def _create_container(ctx: Context, container: str, image: str) -> None:
    """Remove any stale copy, create+start a fresh container for probing."""
    # Pass --dns 8.8.8.8 so the container doesn't inherit a corp DNS the
    # Docker bridge can't route to. Harmless on CI runners.
    ctx.run(
        "docker",
        "container",
        "rm",
        "-f",
        container,
        check=False,
        capture=True,
    )
    ctx.run(
        "docker",
        "container",
        "create",
        "--dns",
        "8.8.8.8",
        "--entrypoint",
        "sleep",
        "--name",
        container,
        image,
        _SLEEP_SECONDS,
        check=True,
        capture=True,
    )
    ctx.run("docker", "container", "start", container, check=True, capture=True)


def _remove_container(ctx: Context, container: str) -> None:
    ctx.run("docker", "container", "stop", container, check=False, capture=True)
    ctx.run("docker", "container", "rm", container, check=False, capture=True)


def _image_digest(ctx: Context, image: str) -> str | None:
    """Resolved sha256 of the image we probed, written into the audit for traceability."""
    proc = ctx.run(
        "docker",
        "image",
        "inspect",
        "--format",
        "{{.Id}}",
        image,
        check=False,
        capture=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode().strip() or None


# -------------------------- backend probes --------------------------


def _parse_rpm_version(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith("Version"):
            return line.split(":", 1)[1].strip()
    return None


def _parse_deb_version(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith("Version:"):
            v = line.split(":", 1)[1].strip()
            # Strip Debian revision ("1.0-2") and backport suffix ("1.0+deb12u1").
            for sep in ("-", "+"):
                if sep in v:
                    v = v.split(sep, 1)[0]
            return v
    return None


def _probe_rpm(container: str, package: str, tool: str) -> str | None:
    proc = _dexec(container, tool, "info", package)
    if proc.returncode != 0:
        return None
    return _parse_rpm_version(proc.stdout.decode(errors="replace"))


def _probe_deb(container: str, package: str) -> str | None:
    proc = _dexec(container, "apt-cache", "show", package)
    if proc.returncode != 0:
        return None
    return _parse_deb_version(proc.stdout.decode(errors="replace"))


def _probe(container: str, backend: str, package: str) -> str | None:
    if backend == BACKEND_TDNF:
        return _probe_rpm(container, package, "tdnf")
    if backend == BACKEND_YUM_DNF:
        # ``yum`` is a shim to dnf on Fedora/Rocky and native on Amazon
        # Linux 2023 (via dnf5). The ``info`` output format is stable.
        return _probe_rpm(container, package, "yum")
    if backend == BACKEND_APT:
        return _probe_deb(container, package)
    raise ValueError(f"unknown backend: {backend}")


def _refresh_index(ctx: Context, container: str, backend: str) -> None:
    """Sync the package index. Failures are soft -- most base images ship
    enough baked metadata that ``info`` lookups still succeed."""
    if backend == BACKEND_TDNF:
        cmd = ["tdnf", "update", "-y"]
    elif backend == BACKEND_YUM_DNF:
        cmd = ["yum", "update", "-y"]
    elif backend == BACKEND_APT:
        cmd = ["apt-get", "update"]
    else:
        raise ValueError(f"unknown backend: {backend}")
    proc = _dexec(container, *cmd)
    if proc.returncode != 0:
        ctx.warn(
            f"index refresh exit={proc.returncode} on {container}; falling "
            "back to prebaked metadata."
        )


def _install_epel(ctx: Context, container: str) -> None:
    proc = _dexec(container, "yum", "install", "-y", "epel-release")
    if proc.returncode != 0:
        ctx.warn(
            f"epel-release install exit={proc.returncode} on {container}; "
            "EPEL-provided packages will show as missing."
        )


# -------------------------- lock parsing --------------------------


def iter_lock(path: pathlib.Path):
    """Yield ``(pkg, ver)`` pairs from a uv-compiled pip lock file."""
    with path.open() as fp:
        for raw in fp:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # ``pkg==1.0 ; python_version<'3.11'`` -> ``pkg==1.0``
            line = line.split(";", 1)[0].strip()
            if "==" not in line:
                continue
            pkg, ver = line.split("==", 1)
            # ``requests[socks]==2.3`` -> ``requests``
            if "[" in pkg:
                pkg = pkg.split("[", 1)[0]
            yield pkg.strip().lower(), ver.strip()


def _python_version(container: str, backend: str) -> tuple[str | None, str | None]:
    """Return ``(full, major.minor)`` of the OS's ``python3`` package."""
    v = _probe(container, backend, "python3")
    if v is None:
        return None, None
    parts = v.split(".")
    if len(parts) < 2:
        return v, None
    return v, f"{parts[0]}.{parts[1]}"


def audit_slug(ctx: Context, slug: str, keep: bool = False) -> dict:
    """Run the full audit for one slug and return the result dict."""
    descr = DISTROS[slug]
    image = descr["image"]
    backend = descr["backend"]
    pkgmap = descr["pkgmap"]
    needs_epel = descr.get("needs_epel", False)

    container = slug.replace(".", "-")
    ctx.info(f"creating container {container} from {image} ...")
    _create_container(ctx, container, image)
    try:
        _refresh_index(ctx, container, backend)
        if needs_epel:
            _install_epel(ctx, container)

        full_pyver, pyver = _python_version(container, backend)
        if pyver is None:
            raise RuntimeError(
                f"python3 not available on {slug} ({image}); audit aborted"
            )
        ctx.info(f"{slug}: python3 {full_pyver}")

        setuptools_ver = _probe(container, backend, "python3-setuptools")
        wheel_ver = _probe(container, backend, "python3-wheel")

        lock_path = (
            tools.utils.REPO_ROOT
            / "requirements"
            / "static"
            / "pkg"
            / f"py{pyver}"
            / "linux.lock"
        )
        if not lock_path.exists():
            raise RuntimeError(
                f"no lock file for py{pyver}: {lock_path} does not exist; "
                "Salt doesn't currently target this Python version."
            )

        packages: dict[str, dict[str, Any]] = {}
        for pkg, lock_ver in iter_lock(lock_path):
            native_pkg = pkgmap.get(pkg, f"python3-{pkg}")
            native_ver = _probe(container, backend, native_pkg)
            tier, probed, sites, features = classify_lock_name(
                tools.utils.REPO_ROOT, pkg
            )
            entry: dict[str, Any] = {
                "lock_version": lock_ver,
                "native_pkg": native_pkg,
                "native_version": native_ver,
                "status": "present" if native_ver else "missing",
                "import_tier": tier,
                "import_names": probed,
                "import_sites": sites,
            }
            if features:
                entry["owning_features"] = features
            if entry["status"] == "missing" and pkg in MISSING_NOTES:
                entry["note"] = MISSING_NOTES[pkg]
            packages[pkg] = entry

        now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
        return {
            "slug": slug,
            "image": image,
            "image_digest": _image_digest(ctx, image),
            "probed_at": now.isoformat().replace("+00:00", "Z"),
            "python_version_full": full_pyver,
            "python_version": pyver,
            "setuptools_version": setuptools_ver,
            "wheel_version": wheel_ver,
            "lock_file": str(lock_path.relative_to(tools.utils.REPO_ROOT)),
            "packages": packages,
        }
    finally:
        if not keep:
            _remove_container(ctx, container)
        else:
            ctx.info(f"leaving container {container} running (--keep)")


# -------------------------- floors + vendor plan --------------------------


def _version_key(v: str) -> Version:
    try:
        return Version(v)
    except InvalidVersion:
        # Non-PEP-440 strings sort below everything so they can't win min().
        return Version("0!0")


def compute_floors(audits: list[dict]) -> dict:
    """Group audits by Python version and compute per-pkg floors.

    For each ``(pyver, pkg)``, the floor is the minimum version across
    distros that ship the package natively. Distros that don't ship it
    are listed under ``missing_in`` (they'd be vendoring the pkg on that
    build, so they don't constrain the floor). ``gap_major`` reports how
    many major versions the lock pin is ahead of the floor so reviewers
    can spot cases where the min-shipped version is unusably old.
    """
    by_pyver: dict[str, dict[str, dict]] = {}
    for audit in audits:
        py = f"py{audit['python_version']}"
        bucket = by_pyver.setdefault(py, {})
        for pkg, entry in audit["packages"].items():
            info = bucket.setdefault(
                pkg,
                {
                    "lock_pin": entry["lock_version"],
                    "votes": {},
                    "missing_in": [],
                },
            )
            if entry["status"] == "present":
                info["votes"][audit["slug"]] = entry["native_version"]
            else:
                info["missing_in"].append(audit["slug"])

    for bucket in by_pyver.values():
        for info in bucket.values():
            info["missing_in"].sort()
            if info["votes"]:
                ranked = sorted(
                    info["votes"].items(),
                    key=lambda item: _version_key(item[1]),
                )
                floor_slug, floor_ver = ranked[0]
                info["floor"] = floor_ver
                info["floor_slug"] = floor_slug
                try:
                    info["gap_major"] = (
                        Version(info["lock_pin"]).major - Version(floor_ver).major
                    )
                except InvalidVersion:
                    info["gap_major"] = None
            else:
                info["floor"] = None
                info["floor_slug"] = None
                info["gap_major"] = None
    return by_pyver


def vendor_list(audit: dict, tiers: tuple[str, ...] | None = None) -> list[str]:
    """Return ``pkg==ver`` lines for the deps missing on this distro.

    If ``tiers`` is given, keep only entries whose ``import_tier`` is in
    the set (e.g. ``("module-top",)`` for crash-will-happen deps).
    ``None`` (default) returns every missing entry.
    """
    out = []
    for pkg, entry in sorted(audit["packages"].items()):
        if entry["status"] != "missing":
            continue
        if tiers is not None and entry.get("import_tier") not in tiers:
            continue
        out.append(f"{pkg}=={entry['lock_version']}")
    return out


def vendor_plan_sections(audit: dict) -> dict[str, list[str]]:
    """Group a distro's missing deps by import tier for ``vendor-plan``.

    Returns a dict with four fixed keys so downstream consumers don't
    have to worry about ordering: ``module_top``, ``feature_opt_in``,
    ``indented``, ``transitive``. Each value is the sorted ``pkg==ver``
    list for that tier.
    """
    return {
        "module_top": vendor_list(audit, tiers=(TIER_MODULE_TOP,)),
        "feature_opt_in": vendor_list(audit, tiers=(TIER_FEATURE_OPT_IN,)),
        "indented": vendor_list(audit, tiers=(TIER_INDENTED,)),
        "transitive": vendor_list(audit, tiers=(TIER_NONE,)),
    }


# -------------------------- commands --------------------------


@native_deps.command(
    name="list-platforms",
    help="List slugs the audit command accepts.",
)
def list_platforms(ctx: Context):
    for slug in sorted(DISTROS):
        d = DISTROS[slug]
        extra = " +epel" if d.get("needs_epel") else ""
        ctx.print(f"  {slug:20s} image={d['image']:22s} backend={d['backend']}{extra}")


@native_deps.command(
    name="audit",
    help="Probe one distro's native python3-* repo against our lock file.",
    arguments={
        "slug": {
            "help": "Distro slug (see list-platforms).",
        },
        "keep": {
            "help": "Leave the probe container running after the audit.",
        },
        "stdout": {
            "help": "Print JSON to stdout instead of writing cicd/native-deps/<slug>.json.",
        },
    },
)
def audit(
    ctx: Context,
    slug: str,
    keep: bool = False,
    stdout: bool = False,
):
    if slug not in DISTROS:
        ctx.error(f"unknown slug: {slug!r}")
        ctx.info("known slugs: " + ", ".join(sorted(DISTROS)))
        ctx.exit(1)
    result = audit_slug(ctx, slug, keep=keep)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if stdout:
        print(text, end="")
        return
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIT_DIR / f"{slug}.json"
    out.write_text(text)
    ctx.info(f"wrote {out.relative_to(tools.utils.REPO_ROOT)}")


@native_deps.command(
    name="floors",
    help="Compute per-pyver floors from committed audit JSONs.",
    arguments={
        "stdout": {
            "help": "Print to stdout instead of writing floors.yml.",
        },
    },
)
def floors(ctx: Context, stdout: bool = False):
    audits = []
    for slug in sorted(DISTROS):
        p = AUDIT_DIR / f"{slug}.json"
        if p.exists():
            audits.append(json.loads(p.read_text()))
    if not audits:
        ctx.error(
            "no audit JSONs found under cicd/native-deps/; "
            "run `tools pkg native-deps audit <slug>` first"
        )
        ctx.exit(1)
    data = compute_floors(audits)
    header = (
        "# Generated by `tools pkg native-deps floors`.\n"
        "# Do NOT edit by hand -- this is a review artifact.\n"
        "# Agreed floors must be hand-promoted into requirements/*.in.\n"
        "#\n"
        "# For each pyver/pkg:\n"
        "#   floor       = min version across distros that ship it natively\n"
        "#   votes       = slug -> native-version observed in audit\n"
        "#   missing_in  = distros that must vendor this dep\n"
        "#   gap_major   = lock_pin.major - floor.major (lock is ahead by N)\n"
        "\n"
    )
    body = yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
    text = header + body
    if stdout:
        print(text, end="")
        return
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIT_DIR / "floors.yml"
    out.write_text(text)
    ctx.info(f"wrote {out.relative_to(tools.utils.REPO_ROOT)}")


@native_deps.command(
    name="vendor-plan",
    help="For one slug, emit the deps the native package must vendor at build time.",
    arguments={
        "slug": {
            "help": "Distro slug.",
        },
        "stdout": {
            "help": "Print to stdout instead of writing <slug>-vendor.txt.",
        },
    },
)
def vendor_plan(ctx: Context, slug: str, stdout: bool = False):
    audit_path = AUDIT_DIR / f"{slug}.json"
    if not audit_path.exists():
        ctx.error(
            f"no audit for {slug} at "
            f"{audit_path.relative_to(tools.utils.REPO_ROOT)}"
        )
        ctx.info(f"run `tools pkg native-deps audit {slug}` first")
        ctx.exit(1)
    audit_result = json.loads(audit_path.read_text())
    sections = vendor_plan_sections(audit_result)
    header = (
        f"# Generated by `tools pkg native-deps vendor-plan {slug}`.\n"
        f"# Source: {audit_result['lock_file']}\n"
        f"# From audit of {audit_result['image']} at {audit_result['probed_at']}.\n"
        "# Install into the native package's _vendor/ dir at build time:\n"
        f"#   pip install --target=/usr/lib/salt/_vendor "
        f"-r cicd/native-deps/{slug}-vendor.txt\n"
        "#\n"
        "# Deps are grouped by their Salt-side import tier. Entries\n"
        "# below the first section are commented out by default -- the\n"
        "# subsystems they live under already degrade gracefully when\n"
        "# the dep is missing. Uncomment to opt a feature into the\n"
        "# vendored set.\n"
        "\n"
    )
    packages = audit_result["packages"]

    def _lines(pin_list: list[str], commented: bool) -> str:
        if not pin_list:
            return "# (none)\n"
        prefix = "# " if commented else ""
        rendered = []
        for pin in pin_list:
            pkg = pin.split("==", 1)[0]
            feats = packages.get(pkg, {}).get("owning_features") or []
            tail = f"  # features: {', '.join(feats)}" if feats else ""
            rendered.append(f"{prefix}{pin}{tail}")
        return "\n".join(rendered) + "\n"

    chunks: list[str] = []
    chunks.append(
        "# === module-top imports ===\n"
        "# Unindented `import X` in salt/. Missing -> ImportError the\n"
        "# moment Salt loads the owning module. Vendor these or drop\n"
        "# the subsystem from the native build.\n"
    )
    chunks.append(_lines(sections["module_top"], commented=False))
    chunks.append(
        "\n# === feature-opt-in imports ===\n"
        "# Unindented import, but the owning module is lazy-loaded only\n"
        "# when the named feature is configured (see LAZY_FEATURE_OWNERS\n"
        "# in tools/pkg/native_deps.py). Vendor only if the native\n"
        "# package declares the feature supported.\n"
    )
    chunks.append(_lines(sections["feature_opt_in"], commented=True))
    chunks.append(
        "\n# === indented imports (try/except or lazy) ===\n"
        "# Salt code imports these behind try/except or inside a\n"
        "# function. Missing -> feature degrades silently.\n"
        "# Uncomment any you want to keep functional on this distro.\n"
    )
    chunks.append(_lines(sections["indented"], commented=True))
    chunks.append(
        "\n# === transitive only (no import in salt/) ===\n"
        "# Nothing in salt/ imports these; they are pulled in only by\n"
        "# their parent packages above. Uncomment only if you vendor a\n"
        "# parent that needs them.\n"
    )
    chunks.append(_lines(sections["transitive"], commented=True))
    text = header + "".join(chunks)
    if stdout:
        print(text, end="")
        return
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIT_DIR / f"{slug}-vendor.txt"
    out.write_text(text)
    ctx.info(f"wrote {out.relative_to(tools.utils.REPO_ROOT)}")

"""
Common functions for working with RPM packages
"""

import collections
import datetime
import logging
import platform
import subprocess

import salt.utils.path
import salt.utils.stringutils

log = logging.getLogger(__name__)

# These arches compiled from the rpmUtils.arch python module source
ARCHES_64 = ("x86_64", "athlon", "amd64", "ia32e", "ia64", "geode")
ARCHES_32 = ("i386", "i486", "i586", "i686")
ARCHES_PPC = ("ppc", "ppc64", "ppc64le", "ppc64iseries", "ppc64pseries")
ARCHES_S390 = ("s390", "s390x")
ARCHES_SPARC = ("sparc", "sparcv8", "sparcv9", "sparcv9v", "sparc64", "sparc64v")
ARCHES_ALPHA = (
    "alpha",
    "alphaev4",
    "alphaev45",
    "alphaev5",
    "alphaev56",
    "alphapca56",
    "alphaev6",
    "alphaev67",
    "alphaev68",
    "alphaev7",
)
ARCHES_ARM_32 = (
    "armv5tel",
    "armv5tejl",
    "armv6l",
    "armv6hl",
    "armv7l",
    "armv7hl",
    "armv7hnl",
)
ARCHES_ARM_64 = ("aarch64",)
ARCHES_SH = ("sh3", "sh4", "sh4a")

ARCHES = (
    ARCHES_64
    + ARCHES_32
    + ARCHES_PPC
    + ARCHES_S390
    + ARCHES_ALPHA
    + ARCHES_ARM_32
    + ARCHES_ARM_64
    + ARCHES_SH
)

# EPOCHNUM can't be used until RHEL5 is EOL as it is not present
QUERYFORMAT = "%{NAME}_|-%{EPOCH}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}_|-%{REPOID}_|-%{INSTALLTIME}"


def get_osarch():
    """
    Get the os architecture using rpm --eval
    """
    if salt.utils.path.which("rpm"):
        ret = subprocess.Popen(
            ["rpm", "--eval", "%{_host_cpu}"],
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).communicate()[0]
    else:
        ret = "".join([x for x in platform.uname()[-2:] if x][-1:])

    return salt.utils.stringutils.to_str(ret).strip() or "unknown"


def check_32(arch, osarch=None):
    """
    Returns True if both the OS arch and the passed arch are x86 or ARM 32-bit
    """
    if osarch is None:
        osarch = get_osarch()
    return all(x in ARCHES_32 for x in (osarch, arch)) or all(
        x in ARCHES_ARM_32 for x in (osarch, arch)
    )


def pkginfo(name, version, arch, repoid, install_date=None, install_date_time_t=None):
    """
    Build and return a pkginfo namedtuple
    """
    pkginfo_tuple = collections.namedtuple(
        "PkgInfo",
        ("name", "version", "arch", "repoid", "install_date", "install_date_time_t"),
    )
    return pkginfo_tuple(name, version, arch, repoid, install_date, install_date_time_t)


def resolve_name(name, arch, osarch=None):
    """
    Resolve the package name and arch into a unique name referred to by salt.
    For example, on a 64-bit OS, a 32-bit package will be pkgname.i386.
    """
    if osarch is None:
        osarch = get_osarch()

    if not check_32(arch, osarch) and arch not in (osarch, "noarch"):
        name += f".{arch}"
    return name


def parse_pkginfo(line, osarch=None):
    """
    A small helper to parse an rpm/repoquery command's output. Returns a
    pkginfo namedtuple.
    """
    try:
        name, epoch, version, release, arch, repoid, install_time = line.split("_|-")
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    name = resolve_name(name, arch, osarch)
    if release:
        version += f"-{release}"
    if epoch not in ("(none)", "0"):
        version = ":".join((epoch, version))

    if install_time not in ("(none)", "0"):
        install_date = (
            datetime.datetime.utcfromtimestamp(int(install_time)).isoformat() + "Z"
        )
        install_date_time_t = int(install_time)
    else:
        install_date = None
        install_date_time_t = None

    return pkginfo(name, version, arch, repoid, install_date, install_date_time_t)


def combine_comments(comments):
    """
    Given a list of comments, strings, a single comment or a single string,
    return a single string of text containing all of the comments, prepending
    the '#' and joining with newlines as necessary.
    """
    if not isinstance(comments, list):
        comments = [comments]
    ret = []
    for comment in comments:
        if not isinstance(comment, str):
            comment = str(comment)
        # Normalize for any spaces (or lack thereof) after the #
        ret.append("# {}\n".format(comment.lstrip("#").lstrip()))
    return "".join(ret)


def evr_compare(
    # evr1: tuple[str | None, str | None, str | None],
    evr1,
    # evr2: tuple[str | None, str | None, str | None],
    evr2,
) -> int:
    """
    Compare two RPM package identifiers using full epoch–version–release semantics.

    This is a pure‑Python equivalent of ``rpm.labelCompare()``, returning the same
    ordering as the system RPM library without requiring the ``python3-rpm`` bindings.

    The comparison is performed in three stages:

    1. **Epoch** — compared numerically; missing or empty values are treated as 0.
    2. **Version** — compared using RPM's ``rpmvercmp`` rules:
       - Split into digit, alpha, and tilde (``~``) segments.
       - Tilde sorts before all other characters (e.g. ``1.0~beta`` < ``1.0``).
       - Numeric segments are compared as integers, ignoring leading zeros.
       - Numeric segments sort before alpha segments.
    3. **Release** — compared with the same rules as version.

    :param evr1: The first ``(epoch, version, release)`` triple to compare.
                 Each element may be a string or ``None``.
    :param evr2: The second ``(epoch, version, release)`` triple to compare.
                 Each element may be a string or ``None``.
    :return: ``-1`` if ``evr1`` is considered older than ``evr2``,
             ``0`` if they are considered equal,
             ``1`` if ``evr1`` is considered newer than ``evr2``.

    .. note::
       This comparison is **not** the same as PEP 440, ``LooseVersion``, or
       ``StrictVersion``. It is intended for RPM package metadata and will match
       the ordering used by tools like ``rpm``, ``dnf``, and ``yum``.

    .. code-block:: python

       >>> label_compare(("0", "1.2.3", "1"), ("0", "1.2.3", "2"))
       -1
       >>> label_compare(("1", "1.0", "1"), ("0", "9.9", "9"))
       1
       >>> label_compare(("0", "1.0~beta", "1"), ("0", "1.0", "1"))
       -1
    """
    epoch1, version1, release1 = evr1
    epoch2, version2, release2 = evr2
    epoch1 = int(epoch1 or 0)
    epoch2 = int(epoch2 or 0)
    if epoch1 != epoch2:
        return 1 if epoch1 > epoch2 else -1
    cmp_versions = _rpmvercmp(version1 or "", version2 or "")
    if cmp_versions != 0:
        return cmp_versions
    return _rpmvercmp(release1 or "", release2 or "")


def _rpmvercmp(a: str, b: str) -> int:
    """
    Pure-Python comparator matching RPM's rpmvercmp().
    Handles separators, tilde (~), caret (^), numeric/alpha segments.
    """
    # Fast path: identical strings
    if a == b:
        return 0

    i = j = 0
    la, lb = len(a), len(b)

    def isalnum_(c: str) -> bool:
        return c.isalnum()

    while i < la or j < lb:
        # Skip separators: anything not alnum, not ~, not ^
        while i < la and not (isalnum_(a[i]) or a[i] in "~^"):
            i += 1
        while j < lb and not (isalnum_(b[j]) or b[j] in "~^"):
            j += 1

        # Tilde: sorts before everything else
        if i < la and a[i] == "~" or j < lb and b[j] == "~":
            if not (i < la and a[i] == "~"):
                return 1
            if not (j < lb and b[j] == "~"):
                return -1
            i += 1
            j += 1
            continue

        # Caret: like tilde except base (end) loses to caret
        if i < la and a[i] == "^" or j < lb and b[j] == "^":
            if i >= la:
                return -1
            if j >= lb:
                return 1
            if not (i < la and a[i] == "^"):
                return 1
            if not (j < lb and b[j] == "^"):
                return -1
            i += 1
            j += 1
            continue

        # If either ran out now, stop
        if not (i < la and j < lb):
            break

        # Segment start positions
        si, sj = i, j

        # Decide type from left side
        isnum = a[i].isdigit()
        if isnum:
            while i < la and a[i].isdigit():
                i += 1
            while j < lb and b[j].isdigit():
                j += 1
        else:
            while i < la and a[i].isalpha():
                i += 1
            while j < lb and b[j].isalpha():
                j += 1

        # If right side had no same‑type run, types differ
        if sj == j:
            return 1 if isnum else -1

        seg_a = a[si:i]
        seg_b = b[sj:j]

        if isnum:
            # Strip leading zeros
            seg_a_nz = seg_a.lstrip("0")
            seg_b_nz = seg_b.lstrip("0")
            # Compare by length
            if len(seg_a_nz) != len(seg_b_nz):
                return 1 if len(seg_a_nz) > len(seg_b_nz) else -1
            # Same length: lexicographic
            if seg_a_nz != seg_b_nz:
                return 1 if seg_a_nz > seg_b_nz else -1
        else:
            # Alpha vs alpha
            if seg_a != seg_b:
                return 1 if seg_a > seg_b else -1
        # else equal segment → loop continues

    # Tail handling
    if i >= la and j >= lb:
        return 0
    return -1 if i >= la else 1


def version_to_evr(verstring):
    """
    Split the package version string into epoch, version and release.
    Return this as tuple.

    The epoch is always not empty. The version and the release can be an empty
    string if such a component could not be found in the version string.

    "2:1.0-1.2" => ('2', '1.0', '1.2)
    "1.0" => ('0', '1.0', '')
    "" => ('0', '', '')
    """
    if verstring in [None, ""]:
        return "0", "", ""

    idx_e = verstring.find(":")
    if idx_e != -1:
        try:
            epoch = str(int(verstring[:idx_e]))
        except ValueError:
            # look, garbage in the epoch field, how fun, kill it
            epoch = "0"  # this is our fallback, deal
    else:
        epoch = "0"
    idx_r = verstring.find("-")
    if idx_r != -1:
        version = verstring[idx_e + 1 : idx_r]
        release = verstring[idx_r + 1 :]
    else:
        version = verstring[idx_e + 1 :]
        release = ""

    return epoch, version, release

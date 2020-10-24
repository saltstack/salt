"""
Set up the version of Salt
"""

import platform
import re
import sys

MAX_SIZE = sys.maxsize
VERSION_LIMIT = MAX_SIZE - 200

# ----- ATTENTION --------------------------------------------------------------------------------------------------->
#
# ALL major version bumps, new release codenames, MUST be defined in the SaltStackVersion.NAMES dictionary, i.e.:
#
#    class SaltStackVersion(object):
#
#        NAMES = {
#            'Hydrogen': (2014, 1),   # <- This is the tuple to bump versions
#            ( ... )
#        }
#
#
# ONLY UPDATE CODENAMES AFTER BRANCHING
#
# As an example, The Helium codename must only be properly defined with "(2014, 7)" after Hydrogen, "(2014, 1)", has
# been branched out into its own branch.
#
# ALL OTHER VERSION INFORMATION IS EXTRACTED FROM THE GIT TAGS
#
# <---- ATTENTION ----------------------------------------------------------------------------------------------------


class SaltStackVersion:
    """
    Handle SaltStack versions class.

    Knows how to parse ``git describe`` output, knows about release candidates
    and also supports version comparison.
    """

    __slots__ = (
        "name",
        "major",
        "minor",
        "bugfix",
        "mbugfix",
        "pre_type",
        "pre_num",
        "noc",
        "sha",
    )

    git_sha_regex = r"(?P<sha>g?[a-f0-9]{7,40})"

    git_describe_regex = re.compile(
        r"(?:[^\d]+)?(?P<major>[\d]{1,4})"
        r"(?:\.(?P<minor>[\d]{1,2}))?"
        r"(?:\.(?P<bugfix>[\d]{0,2}))?"
        r"(?:\.(?P<mbugfix>[\d]{0,2}))?"
        r"(?:(?P<pre_type>rc|a|b|alpha|beta|nb)(?P<pre_num>[\d]{1}))?"
        r"(?:(?:.*)-(?P<noc>(?:[\d]+|n/a))-" + git_sha_regex + r")?"
    )
    git_sha_regex = r"^" + git_sha_regex

    git_sha_regex = re.compile(git_sha_regex)

    # Salt versions after 0.17.0 will be numbered like:
    #   <4-digit-year>.<month>.<bugfix>
    #
    # Since the actual version numbers will only be know on release dates, the
    # periodic table element names will be what's going to be used to name
    # versions and to be able to mention them.

    NAMES = {
        # Let's keep at least 3 version names uncommented counting from the
        # latest release so we can map deprecation warnings to versions.
        # pylint: disable=E8203
        # ----- Please refrain from fixing PEP-8 E203 and E265 ----->
        # The idea is to keep this readable.
        # -----------------------------------------------------------
        "Hydrogen": (2014, 1),
        "Helium": (2014, 7),
        "Lithium": (2015, 5),
        "Beryllium": (2015, 8),
        "Boron": (2016, 3),
        "Carbon": (2016, 11),
        "Nitrogen": (2017, 7),
        "Oxygen": (2018, 3),
        "Fluorine": (2019, 2),
        "Neon": (3000,),
        "Sodium": (3001,),
        "Magnesium": (3002,),
        "Aluminium": (MAX_SIZE - 96, 0),
        "Silicon": (MAX_SIZE - 95, 0),
        "Phosphorus": (MAX_SIZE - 94, 0),
        # pylint: disable=E8265
        #'Sulfur'       : (MAX_SIZE - 93, 0),
        #'Chlorine'     : (MAX_SIZE - 92, 0),
        #'Argon'        : (MAX_SIZE - 91, 0),
        #'Potassium'    : (MAX_SIZE - 90, 0),
        #'Calcium'      : (MAX_SIZE - 89, 0),
        #'Scandium'     : (MAX_SIZE - 88, 0),
        #'Titanium'     : (MAX_SIZE - 87, 0),
        #'Vanadium'     : (MAX_SIZE - 86, 0),
        #'Chromium'     : (MAX_SIZE - 85, 0),
        #'Manganese'    : (MAX_SIZE - 84, 0),
        #'Iron'         : (MAX_SIZE - 83, 0),
        #'Cobalt'       : (MAX_SIZE - 82, 0),
        #'Nickel'       : (MAX_SIZE - 81, 0),
        #'Copper'       : (MAX_SIZE - 80, 0),
        #'Zinc'         : (MAX_SIZE - 79, 0),
        #'Gallium'      : (MAX_SIZE - 78, 0),
        #'Germanium'    : (MAX_SIZE - 77, 0),
        #'Arsenic'      : (MAX_SIZE - 76, 0),
        #'Selenium'     : (MAX_SIZE - 75, 0),
        #'Bromine'      : (MAX_SIZE - 74, 0),
        #'Krypton'      : (MAX_SIZE - 73, 0),
        #'Rubidium'     : (MAX_SIZE - 72, 0),
        #'Strontium'    : (MAX_SIZE - 71, 0),
        #'Yttrium'      : (MAX_SIZE - 70, 0),
        #'Zirconium'    : (MAX_SIZE - 69, 0),
        #'Niobium'      : (MAX_SIZE - 68, 0),
        #'Molybdenum'   : (MAX_SIZE - 67, 0),
        #'Technetium'   : (MAX_SIZE - 66, 0),
        #'Ruthenium'    : (MAX_SIZE - 65, 0),
        #'Rhodium'      : (MAX_SIZE - 64, 0),
        #'Palladium'    : (MAX_SIZE - 63, 0),
        #'Silver'       : (MAX_SIZE - 62, 0),
        #'Cadmium'      : (MAX_SIZE - 61, 0),
        #'Indium'       : (MAX_SIZE - 60, 0),
        #'Tin'          : (MAX_SIZE - 59, 0),
        #'Antimony'     : (MAX_SIZE - 58, 0),
        #'Tellurium'    : (MAX_SIZE - 57, 0),
        #'Iodine'       : (MAX_SIZE - 56, 0),
        #'Xenon'        : (MAX_SIZE - 55, 0),
        #'Caesium'      : (MAX_SIZE - 54, 0),
        #'Barium'       : (MAX_SIZE - 53, 0),
        #'Lanthanum'    : (MAX_SIZE - 52, 0),
        #'Cerium'       : (MAX_SIZE - 51, 0),
        #'Praseodymium' : (MAX_SIZE - 50, 0),
        #'Neodymium'    : (MAX_SIZE - 49, 0),
        #'Promethium'   : (MAX_SIZE - 48, 0),
        #'Samarium'     : (MAX_SIZE - 47, 0),
        #'Europium'     : (MAX_SIZE - 46, 0),
        #'Gadolinium'   : (MAX_SIZE - 45, 0),
        #'Terbium'      : (MAX_SIZE - 44, 0),
        #'Dysprosium'   : (MAX_SIZE - 43, 0),
        #'Holmium'      : (MAX_SIZE - 42, 0),
        #'Erbium'       : (MAX_SIZE - 41, 0),
        #'Thulium'      : (MAX_SIZE - 40, 0),
        #'Ytterbium'    : (MAX_SIZE - 39, 0),
        #'Lutetium'     : (MAX_SIZE - 38, 0),
        #'Hafnium'      : (MAX_SIZE - 37, 0),
        #'Tantalum'     : (MAX_SIZE - 36, 0),
        #'Tungsten'     : (MAX_SIZE - 35, 0),
        #'Rhenium'      : (MAX_SIZE - 34, 0),
        #'Osmium'       : (MAX_SIZE - 33, 0),
        #'Iridium'      : (MAX_SIZE - 32, 0),
        #'Platinum'     : (MAX_SIZE - 31, 0),
        #'Gold'         : (MAX_SIZE - 30, 0),
        #'Mercury'      : (MAX_SIZE - 29, 0),
        #'Thallium'     : (MAX_SIZE - 28, 0),
        #'Lead'         : (MAX_SIZE - 27, 0),
        #'Bismuth'      : (MAX_SIZE - 26, 0),
        #'Polonium'     : (MAX_SIZE - 25, 0),
        #'Astatine'     : (MAX_SIZE - 24, 0),
        #'Radon'        : (MAX_SIZE - 23, 0),
        #'Francium'     : (MAX_SIZE - 22, 0),
        #'Radium'       : (MAX_SIZE - 21, 0),
        #'Actinium'     : (MAX_SIZE - 20, 0),
        #'Thorium'      : (MAX_SIZE - 19, 0),
        #'Protactinium' : (MAX_SIZE - 18, 0),
        #'Uranium'      : (MAX_SIZE - 17, 0),
        #'Neptunium'    : (MAX_SIZE - 16, 0),
        #'Plutonium'    : (MAX_SIZE - 15, 0),
        #'Americium'    : (MAX_SIZE - 14, 0),
        #'Curium'       : (MAX_SIZE - 13, 0),
        #'Berkelium'    : (MAX_SIZE - 12, 0),
        #'Californium'  : (MAX_SIZE - 11, 0),
        #'Einsteinium'  : (MAX_SIZE - 10, 0),
        #'Fermium'      : (MAX_SIZE - 9, 0),
        #'Mendelevium'  : (MAX_SIZE - 8, 0),
        #'Nobelium'     : (MAX_SIZE - 7, 0),
        #'Lawrencium'   : (MAX_SIZE - 6, 0),
        #'Rutherfordium': (MAX_SIZE - 5, 0),
        #'Dubnium'      : (MAX_SIZE - 4, 0),
        #'Seaborgium'   : (MAX_SIZE - 3, 0),
        #'Bohrium'      : (MAX_SIZE - 2, 0),
        #'Hassium'      : (MAX_SIZE - 1, 0),
        #'Meitnerium'   : (MAX_SIZE - 0, 0),
        # <---- Please refrain from fixing PEP-8 E203 and E265 ------
        # pylint: enable=E8203,E8265
    }

    LNAMES = {k.lower(): v for (k, v) in iter(NAMES.items())}
    VNAMES = {v: k for (k, v) in iter(NAMES.items())}
    RMATCH = {v[:2]: k for (k, v) in iter(NAMES.items())}

    def __init__(
        self,  # pylint: disable=C0103
        major,
        minor=None,
        bugfix=None,
        mbugfix=0,
        pre_type=None,
        pre_num=None,
        noc=0,
        sha=None,
    ):

        if isinstance(major, str):
            major = int(major)

        if isinstance(minor, str):
            if not minor:
                # Empty string
                minor = None
            else:
                minor = int(minor)

        if bugfix is None and not self.new_version(major=major):
            bugfix = 0
        elif isinstance(bugfix, str):
            if not bugfix:
                bugfix = None
            else:
                bugfix = int(bugfix)

        if mbugfix is None:
            mbugfix = 0
        elif isinstance(mbugfix, str):
            mbugfix = int(mbugfix)

        if pre_type is None:
            pre_type = ""
        if pre_num is None:
            pre_num = 0
        elif isinstance(pre_num, str):
            pre_num = int(pre_num)

        if noc is None:
            noc = 0
        elif isinstance(noc, str) and noc == "n/a":
            noc = -1
        elif isinstance(noc, str):
            noc = int(noc)

        self.major = major
        self.minor = minor
        self.bugfix = bugfix
        self.mbugfix = mbugfix
        self.pre_type = pre_type
        self.pre_num = pre_num
        self.name = self.VNAMES.get((major, minor), None)
        if self.new_version(major):
            self.name = self.VNAMES.get((major,), None)
        self.noc = noc
        self.sha = sha

    def new_version(self, major):
        """
        determine if using new versioning scheme
        """
        return bool(int(major) >= 3000 and int(major) < VERSION_LIMIT)

    @classmethod
    def parse(cls, version_string):
        if version_string.lower() in cls.LNAMES:
            return cls.from_name(version_string)
        vstr = (
            version_string.decode()
            if isinstance(version_string, bytes)
            else version_string
        )
        match = cls.git_describe_regex.match(vstr)
        if not match:
            raise ValueError(
                "Unable to parse version string: '{}'".format(version_string)
            )
        return cls(*match.groups())

    @classmethod
    def from_name(cls, name):
        if name.lower() not in cls.LNAMES:
            raise ValueError("Named version '{}' is not known".format(name))
        return cls(*cls.LNAMES[name.lower()])

    @classmethod
    def from_last_named_version(cls):
        return cls.from_name(
            cls.VNAMES[
                max(
                    [
                        version_info
                        for version_info in cls.VNAMES
                        if version_info[0] < (VERSION_LIMIT)
                    ]
                )
            ]
        )

    @classmethod
    def next_release(cls):
        return cls.from_name(
            cls.VNAMES[
                min(
                    [
                        version_info
                        for version_info in cls.VNAMES
                        if version_info > cls.from_last_named_version().info
                    ]
                )
            ]
        )

    @property
    def sse(self):
        # Higher than 0.17, lower than first date based
        return 0 < self.major < 2014

    def min_info(self):
        info = [self.major]
        if self.new_version(self.major):
            if self.minor:
                info.append(self.minor)
        else:
            info.extend([self.minor, self.bugfix, self.mbugfix])
        return info

    @property
    def info(self):
        return tuple(self.min_info())

    @property
    def pre_info(self):
        info = self.min_info()
        info.extend([self.pre_type, self.pre_num])
        return tuple(info)

    @property
    def noc_info(self):
        info = self.min_info()
        info.extend([self.pre_type, self.pre_num, self.noc])
        return tuple(info)

    @property
    def full_info(self):
        info = self.min_info()
        info.extend([self.pre_type, self.pre_num, self.noc, self.sha])
        return tuple(info)

    @property
    def full_info_all_versions(self):
        """
        Return the full info regardless
        of which versioning scheme we
        are using.
        """
        info = [
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.pre_type,
            self.pre_num,
            self.noc,
            self.sha,
        ]
        return tuple(info)

    @property
    def string(self):
        if self.new_version(self.major):
            version_string = "{}".format(self.major)
            if self.minor:
                version_string = "{}.{}".format(self.major, self.minor)
        else:
            version_string = "{}.{}.{}".format(self.major, self.minor, self.bugfix)
        if self.mbugfix:
            version_string += ".{}".format(self.mbugfix)
        if self.pre_type:
            version_string += "{}{}".format(self.pre_type, self.pre_num)
        if self.noc and self.sha:
            noc = self.noc
            if noc < 0:
                noc = "n/a"
            version_string += "-{}-{}".format(noc, self.sha)
        return version_string

    @property
    def formatted_version(self):
        if self.name and self.major > 10000:
            version_string = self.name
            if self.sse:
                version_string += " Enterprise"
            version_string += " (Unreleased)"
            return version_string
        version_string = self.string
        if self.sse:
            version_string += " Enterprise"
        if (self.major, self.minor) in self.RMATCH:
            version_string += " ({})".format(self.RMATCH[(self.major, self.minor)])
        return version_string

    @property
    def pre_index(self):
        if self.new_version(self.major):
            pre_type = 2
            if not isinstance(self.minor, int):
                pre_type = 1
        else:
            pre_type = 4
        return pre_type

    def __str__(self):
        return self.string

    def __compare__(self, other, method):
        if not isinstance(other, SaltStackVersion):
            if isinstance(other, str):
                other = SaltStackVersion.parse(other)
            elif isinstance(other, (list, tuple)):
                other = SaltStackVersion(*other)
            else:
                raise ValueError(
                    "Cannot instantiate Version from type '{}'".format(type(other))
                )

        pre_type = self.pre_index
        other_pre_type = other.pre_index
        other_noc_info = list(other.noc_info)
        noc_info = list(self.noc_info)

        if self.new_version(self.major):
            if self.minor and not other.minor:
                # We have minor information, the other side does not
                if self.minor > 0:
                    other_noc_info[1] = 0

            if not self.minor and other.minor:
                # The other side has minor information, we don't
                if other.minor > 0:
                    noc_info[1] = 0

        if self.pre_type and not other.pre_type:
            # We have pre-release information, the other side doesn't
            other_noc_info[other_pre_type] = "zzzzz"

        if not self.pre_type and other.pre_type:
            # The other side has pre-release information, we don't
            noc_info[pre_type] = "zzzzz"

        return method(tuple(noc_info), tuple(other_noc_info))

    def __lt__(self, other):
        return self.__compare__(other, lambda _self, _other: _self < _other)

    def __le__(self, other):
        return self.__compare__(other, lambda _self, _other: _self <= _other)

    def __eq__(self, other):
        return self.__compare__(other, lambda _self, _other: _self == _other)

    def __ne__(self, other):
        return self.__compare__(other, lambda _self, _other: _self != _other)

    def __ge__(self, other):
        return self.__compare__(other, lambda _self, _other: _self >= _other)

    def __gt__(self, other):
        return self.__compare__(other, lambda _self, _other: _self > _other)

    def __repr__(self):
        parts = []
        if self.name:
            parts.append("name='{}'".format(self.name))
        parts.extend(["major={}".format(self.major), "minor={}".format(self.minor)])

        if self.new_version(self.major):
            if not self.minor:
                parts.remove("".join([x for x in parts if re.search("^minor*", x)]))
        else:
            parts.extend(["bugfix={}".format(self.bugfix)])

        if self.mbugfix:
            parts.append("minor-bugfix={}".format(self.mbugfix))
        if self.pre_type:
            parts.append("{}={}".format(self.pre_type, self.pre_num))
        noc = self.noc
        if noc == -1:
            noc = "n/a"
        if noc and self.sha:
            parts.extend(["noc={}".format(noc), "sha={}".format(self.sha)])
        return "<{} {}>".format(self.__class__.__name__, " ".join(parts))


# ----- Hardcoded Salt Codename Version Information ----------------------------------------------------------------->
#
#   There's no need to do anything here. The last released codename will be picked up
# --------------------------------------------------------------------------------------------------------------------
__saltstack_version__ = SaltStackVersion.from_last_named_version()
# <---- Hardcoded Salt Version Information ---------------------------------------------------------------------------


# ----- Dynamic/Runtime Salt Version Information -------------------------------------------------------------------->
def __discover_version(saltstack_version):
    # This might be a 'python setup.py develop' installation type. Let's
    # discover the version information at runtime.
    import os
    import subprocess

    if "SETUP_DIRNAME" in globals():
        # This is from the exec() call in Salt's setup.py
        cwd = SETUP_DIRNAME  # pylint: disable=E0602
        if not os.path.exists(os.path.join(cwd, ".git")):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return saltstack_version
    else:
        cwd = os.path.abspath(os.path.dirname(__file__))
        if not os.path.exists(os.path.join(os.path.dirname(cwd), ".git")):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return saltstack_version

    try:
        kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)

        if not sys.platform.startswith("win"):
            # Let's not import `salt.utils` for the above check
            kwargs["close_fds"] = True

        process = subprocess.Popen(
            [
                "git",
                "describe",
                "--tags",
                "--first-parent",
                "--match",
                "v[0-9]*",
                "--always",
            ],
            **kwargs
        )

        out, err = process.communicate()

        if process.returncode != 0:
            # The git version running this might not support --first-parent
            # Revert to old command
            process = subprocess.Popen(
                ["git", "describe", "--tags", "--match", "v[0-9]*", "--always"],
                **kwargs
            )
            out, err = process.communicate()
        out = out.decode().strip()
        err = err.decode().strip()

        if not out or err:
            return saltstack_version

        if SaltStackVersion.git_sha_regex.match(out):
            # We only define the parsed SHA and set NOC as ??? (unknown)
            saltstack_version.sha = out.strip()
            saltstack_version.noc = -1
            return saltstack_version

        return SaltStackVersion.parse(out)

    except OSError as os_err:
        if os_err.errno != 2:
            # If the errno is not 2(The system cannot find the file
            # specified), raise the exception so it can be catch by the
            # developers
            raise
    return saltstack_version


def __get_version(saltstack_version):
    """
    If we can get a version provided at installation time or from Git, use
    that instead, otherwise we carry on.
    """
    try:
        # Try to import the version information provided at install time
        from salt._version import __saltstack_version__  # pylint: disable=E0611,F0401

        return __saltstack_version__
    except ImportError:
        return __discover_version(saltstack_version)


# Get additional version information if available
__saltstack_version__ = __get_version(__saltstack_version__)
# This function has executed once, we're done with it. Delete it!
del __get_version
# <---- Dynamic/Runtime Salt Version Information ---------------------------------------------------------------------


# ----- Common version related attributes - NO NEED TO CHANGE ------------------------------------------------------->
__version_info__ = __saltstack_version__.info
__version__ = __saltstack_version__.string
# <---- Common version related attributes - NO NEED TO CHANGE --------------------------------------------------------


def salt_information():
    """
    Report version of salt.
    """
    yield "Salt", __version__


def dependency_information(include_salt_cloud=False):
    """
    Report versions of library dependencies.
    """
    libs = [
        ("Python", None, sys.version.rsplit("\n")[0].strip()),
        ("Jinja2", "jinja2", "__version__"),
        ("M2Crypto", "M2Crypto", "version"),
        ("msgpack-python", "msgpack", "version"),
        ("msgpack-pure", "msgpack_pure", "version"),
        ("pycrypto", "Crypto", "__version__"),
        ("pycryptodome", "Cryptodome", "version_info"),
        ("PyYAML", "yaml", "__version__"),
        ("PyZMQ", "zmq", "__version__"),
        ("ZMQ", "zmq", "zmq_version"),
        ("Mako", "mako", "__version__"),
        ("Tornado", "tornado", "version"),
        ("timelib", "timelib", "version"),
        ("dateutil", "dateutil", "__version__"),
        ("pygit2", "pygit2", "__version__"),
        ("libgit2", "pygit2", "LIBGIT2_VERSION"),
        ("smmap", "smmap", "__version__"),
        ("cffi", "cffi", "__version__"),
        ("pycparser", "pycparser", "__version__"),
        ("gitdb", "gitdb", "__version__"),
        ("gitpython", "git", "__version__"),
        ("python-gnupg", "gnupg", "__version__"),
        ("mysql-python", "MySQLdb", "__version__"),
        ("cherrypy", "cherrypy", "__version__"),
        ("docker-py", "docker", "__version__"),
    ]

    if include_salt_cloud:
        libs.append(("Apache Libcloud", "libcloud", "__version__"),)

    for name, imp, attr in libs:
        if imp is None:
            yield name, attr
            continue
        try:
            imp = __import__(imp)
            version = getattr(imp, attr)
            if callable(version):
                version = version()
            if isinstance(version, (tuple, list)):
                version = ".".join(map(str, version))
            yield name, version
        except Exception:  # pylint: disable=broad-except
            yield name, None


def system_information():
    """
    Report system versions.
    """
    # Late import so that when getting called from setup.py does not break
    from distro import linux_distribution

    def system_version():
        """
        Return host system version.
        """

        lin_ver = linux_distribution()
        mac_ver = platform.mac_ver()
        win_ver = platform.win32_ver()

        # linux_distribution() will return a
        # distribution on OS X and Windows.
        # Check mac_ver and win_ver first,
        # then lin_ver.
        if mac_ver[0]:
            if isinstance(mac_ver[1], (tuple, list)) and "".join(mac_ver[1]):
                return " ".join([mac_ver[0], ".".join(mac_ver[1]), mac_ver[2]])
            else:
                return " ".join([mac_ver[0], mac_ver[2]])
        elif win_ver[0]:
            return " ".join(win_ver)
        elif lin_ver[0]:
            return " ".join(lin_ver)
        else:
            return ""

    if platform.win32_ver()[0]:
        # Get the version and release info based on the Windows Operating
        # System Product Name. As long as Microsoft maintains a similar format
        # this should be future proof
        import win32api  # pylint: disable=3rd-party-module-not-gated
        import win32con  # pylint: disable=3rd-party-module-not-gated

        # Get the product name from the registry
        hkey = win32con.HKEY_LOCAL_MACHINE
        key = "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion"
        value_name = "ProductName"
        reg_handle = win32api.RegOpenKey(hkey, key)

        # Returns a tuple of (product_name, value_type)
        product_name, _ = win32api.RegQueryValueEx(reg_handle, value_name)

        version = "Unknown"
        release = ""
        if "Server" in product_name:
            for item in product_name.split(" "):
                # If it's all digits, then it's version
                if re.match(r"\d+", item):
                    version = item
                # If it starts with R and then numbers, it's the release
                # ie: R2
                if re.match(r"^R\d+$", item):
                    release = item
            release = "{}Server{}".format(version, release)
        else:
            for item in product_name.split(" "):
                # If it's a number, decimal number, Thin or Vista, then it's the
                # version
                if re.match(r"^(\d+(\.\d+)?)|Thin|Vista$", item):
                    version = item
            release = version

        _, ver, service_pack, extra = platform.win32_ver()
        version = " ".join([release, ver, service_pack, extra])
    else:
        version = system_version()
        release = platform.release()

    system = [
        ("system", platform.system()),
        ("dist", " ".join(linux_distribution(full_distribution_name=False))),
        ("release", release),
        ("machine", platform.machine()),
        ("version", version),
        ("locale", __salt_system_encoding__),
    ]

    for name, attr in system:
        yield name, attr
        continue


def versions_information(include_salt_cloud=False):
    """
    Report the versions of dependent software.
    """
    salt_info = list(salt_information())
    lib_info = list(dependency_information(include_salt_cloud))
    sys_info = list(system_information())

    return {
        "Salt Version": dict(salt_info),
        "Dependency Versions": dict(lib_info),
        "System Versions": dict(sys_info),
    }


def versions_report(include_salt_cloud=False):
    """
    Yield each version properly formatted for console output.
    """
    ver_info = versions_information(include_salt_cloud)
    not_installed = "Not Installed"
    ns_pad = len(not_installed)
    lib_pad = max(len(name) for name in ver_info["Dependency Versions"])
    sys_pad = max(len(name) for name in ver_info["System Versions"])
    padding = max(lib_pad, sys_pad, ns_pad) + 1

    fmt = "{0:>{pad}}: {1}"
    info = []
    for ver_type in ("Salt Version", "Dependency Versions", "System Versions"):
        info.append("{}:".format(ver_type))
        # List dependencies in alphabetical, case insensitive order
        for name in sorted(ver_info[ver_type], key=lambda x: x.lower()):
            ver = fmt.format(
                name, ver_info[ver_type][name] or not_installed, pad=padding
            )
            info.append(ver)
        info.append(" ")

    yield from info


if __name__ == "__main__":
    print(__version__)

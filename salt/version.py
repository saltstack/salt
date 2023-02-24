"""
Set up the version of Salt
"""
import operator
import os
import platform
import re
import sys
from collections import namedtuple
from functools import total_ordering

MAX_SIZE = sys.maxsize
VERSION_LIMIT = MAX_SIZE - 200

# ----- ATTENTION --------------------------------------------------------------------------------------------------->
#
# ALL major version bumps, new release codenames, MUST be defined in the SaltStackVersion.NAMES dictionary, i.e.:
#
#    class SaltStackVersion:
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


@total_ordering
class SaltVersion(namedtuple("SaltVersion", "name, info, released")):
    __slots__ = ()

    def __new__(cls, name, info, released=False):
        if isinstance(info, int):
            info = (info,)
        return super().__new__(cls, name, info, released)

    def __eq__(self, other):
        return self.info == other.info

    def __gt__(self, other):
        return self.info > other.info


class SaltVersionsInfo(type):

    _sorted_versions = ()
    _current_release = None
    _previous_release = None
    _next_release = None

    # pylint: disable=bad-whitespace,multiple-spaces-before-operator
    # ----- Please refrain from fixing whitespace ---------------------------------->
    # The idea is to keep this readable.
    # -------------------------------------------------------------------------------
    # fmt: off
    HYDROGEN      = SaltVersion("Hydrogen"     , info=(2014, 1),  released=True)
    HELIUM        = SaltVersion("Helium"       , info=(2014, 7),  released=True)
    LITHIUM       = SaltVersion("Lithium"      , info=(2015, 5),  released=True)
    BERYLLIUM     = SaltVersion("Beryllium"    , info=(2015, 8),  released=True)
    BORON         = SaltVersion("Boron"        , info=(2016, 3),  released=True)
    CARBON        = SaltVersion("Carbon"       , info=(2016, 11), released=True)
    NITROGEN      = SaltVersion("Nitrogen"     , info=(2017, 7),  released=True)
    OXYGEN        = SaltVersion("Oxygen"       , info=(2018, 3),  released=True)
    FLUORINE      = SaltVersion("Fluorine"     , info=(2019, 2),  released=True)
    NEON          = SaltVersion("Neon"         , info=3000,       released=True)
    SODIUM        = SaltVersion("Sodium"       , info=3001,       released=True)
    MAGNESIUM     = SaltVersion("Magnesium"    , info=3002,       released=True)
    ALUMINIUM     = SaltVersion("Aluminium"    , info=3003,       released=True)
    SILICON       = SaltVersion("Silicon"      , info=3004,       released=True)
    PHOSPHORUS    = SaltVersion("Phosphorus"   , info=3005,       released=True)
    SULFUR        = SaltVersion("Sulfur"       , info=(3006, 0))
    CHLORINE      = SaltVersion("Chlorine"     , info=(3007, 0))
    ARGON         = SaltVersion("Argon"        , info=(3008, 0))
    POTASSIUM     = SaltVersion("Potassium"    , info=(3009, 0))
    CALCIUM       = SaltVersion("Calcium"      , info=(3010, 0))
    SCANDIUM      = SaltVersion("Scandium"     , info=(3011, 0))
    TITANIUM      = SaltVersion("Titanium"     , info=(3012, 0))
    VANADIUM      = SaltVersion("Vanadium"     , info=(3013, 0))
    CHROMIUM      = SaltVersion("Chromium"     , info=(3014, 0))
    MANGANESE     = SaltVersion("Manganese"    , info=(3015, 0))
    IRON          = SaltVersion("Iron"         , info=(3016, 0))
    COBALT        = SaltVersion("Cobalt"       , info=(3017, 0))
    NICKEL        = SaltVersion("Nickel"       , info=(3018, 0))
    COPPER        = SaltVersion("Copper"       , info=(3019, 0))
    ZINC          = SaltVersion("Zinc"         , info=(3020, 0))
    GALLIUM       = SaltVersion("Gallium"      , info=(3021, 0))
    GERMANIUM     = SaltVersion("Germanium"    , info=(3022, 0))
    ARSENIC       = SaltVersion("Arsenic"      , info=(3023, 0))
    SELENIUM      = SaltVersion("Selenium"     , info=(3024, 0))
    BROMINE       = SaltVersion("Bromine"      , info=(3025, 0))
    KRYPTON       = SaltVersion("Krypton"      , info=(3026, 0))
    RUBIDIUM      = SaltVersion("Rubidium"     , info=(3027, 0))
    STRONTIUM     = SaltVersion("Strontium"    , info=(3028, 0))
    YTTRIUM       = SaltVersion("Yttrium"      , info=(3029, 0))
    ZIRCONIUM     = SaltVersion("Zirconium"    , info=(3030, 0))
    NIOBIUM       = SaltVersion("Niobium"      , info=(3031, 0))
    MOLYBDENUM    = SaltVersion("Molybdenum"   , info=(3032, 0))
    TECHNETIUM    = SaltVersion("Technetium"   , info=(3033, 0))
    RUTHENIUM     = SaltVersion("Ruthenium"    , info=(3034, 0))
    RHODIUM       = SaltVersion("Rhodium"      , info=(3035, 0))
    PALLADIUM     = SaltVersion("Palladium"    , info=(3036, 0))
    SILVER        = SaltVersion("Silver"       , info=(3037, 0))
    CADMIUM       = SaltVersion("Cadmium"      , info=(3038, 0))
    INDIUM        = SaltVersion("Indium"       , info=(3039, 0))
    TIN           = SaltVersion("Tin"          , info=(3040, 0))
    ANTIMONY      = SaltVersion("Antimony"     , info=(3041, 0))
    TELLURIUM     = SaltVersion("Tellurium"    , info=(3042, 0))
    IODINE        = SaltVersion("Iodine"       , info=(3043, 0))
    XENON         = SaltVersion("Xenon"        , info=(3044, 0))
    CESIUM        = SaltVersion("Cesium"       , info=(3045, 0))
    BARIUM        = SaltVersion("Barium"       , info=(3046, 0))
    LANTHANUM     = SaltVersion("Lanthanum"    , info=(3047, 0))
    CERIUM        = SaltVersion("Cerium"       , info=(3048, 0))
    PRASEODYMIUM  = SaltVersion("Praseodymium" , info=(3049, 0))
    NEODYMIUM     = SaltVersion("Neodymium"    , info=(3050, 0))
    PROMETHIUM    = SaltVersion("Promethium"   , info=(3051, 0))
    SAMARIUM      = SaltVersion("Samarium"     , info=(3052, 0))
    EUROPIUM      = SaltVersion("Europium"     , info=(3053, 0))
    GADOLINIUM    = SaltVersion("Gadolinium"   , info=(3054, 0))
    TERBIUM       = SaltVersion("Terbium"      , info=(3055, 0))
    DYSPROSIUM    = SaltVersion("Dysprosium"   , info=(3056, 0))
    HOLMIUM       = SaltVersion("Holmium"      , info=(3057, 0))
    ERBIUM        = SaltVersion("Erbium"       , info=(3058, 0))
    THULIUM       = SaltVersion("Thulium"      , info=(3059, 0))
    YTTERBIUM     = SaltVersion("Ytterbium"    , info=(3060, 0))
    LUTETIUM      = SaltVersion("Lutetium"     , info=(3061, 0))
    HAFNIUM       = SaltVersion("Hafnium"      , info=(3062, 0))
    TANTALUM      = SaltVersion("Tantalum"     , info=(3063, 0))
    TUNGSTEN      = SaltVersion("Tungsten"     , info=(3064, 0))
    RHENIUM       = SaltVersion("Rhenium"      , info=(3065, 0))
    OSMIUM        = SaltVersion("Osmium"       , info=(3066, 0))
    IRIDIUM       = SaltVersion("Iridium"      , info=(3067, 0))
    PLATINUM      = SaltVersion("Platinum"     , info=(3068, 0))
    GOLD          = SaltVersion("Gold"         , info=(3069, 0))
    MERCURY       = SaltVersion("Mercury"      , info=(3070, 0))
    THALLIUM      = SaltVersion("Thallium"     , info=(3071, 0))
    LEAD          = SaltVersion("Lead"         , info=(3072, 0))
    BISMUTH       = SaltVersion("Bismuth"      , info=(3073, 0))
    POLONIUM      = SaltVersion("Polonium"     , info=(3074, 0))
    ASTATINE      = SaltVersion("Astatine"     , info=(3075, 0))
    RADON         = SaltVersion("Radon"        , info=(3076, 0))
    FRANCIUM      = SaltVersion("Francium"     , info=(3077, 0))
    RADIUM        = SaltVersion("Radium"       , info=(3078, 0))
    ACTINIUM      = SaltVersion("Actinium"     , info=(3079, 0))
    THORIUM       = SaltVersion("Thorium"      , info=(3080, 0))
    PROTACTINIUM  = SaltVersion("Protactinium" , info=(3081, 0))
    URANIUM       = SaltVersion("Uranium"      , info=(3082, 0))
    NEPTUNIUM     = SaltVersion("Neptunium"    , info=(3083, 0))
    PLUTONIUM     = SaltVersion("Plutonium"    , info=(3084, 0))
    AMERICIUM     = SaltVersion("Americium"    , info=(3085, 0))
    CURIUM        = SaltVersion("Curium"       , info=(3086, 0))
    BERKELIUM     = SaltVersion("Berkelium"    , info=(3087, 0))
    CALIFORNIUM   = SaltVersion("Californium"  , info=(3088, 0))
    EINSTEINIUM   = SaltVersion("Einsteinium"  , info=(3089, 0))
    FERMIUM       = SaltVersion("Fermium"      , info=(3090, 0))
    MENDELEVIUM   = SaltVersion("Mendelevium"  , info=(3091, 0))
    NOBELIUM      = SaltVersion("Nobelium"     , info=(3092, 0))
    LAWRENCIUM    = SaltVersion("Lawrencium"   , info=(3093, 0))
    RUTHERFORDIUM = SaltVersion("Rutherfordium", info=(3094, 0))
    DUBNIUM       = SaltVersion("Dubnium"      , info=(3095, 0))
    SEABORGIUM    = SaltVersion("Seaborgium"   , info=(3096, 0))
    BOHRIUM       = SaltVersion("Bohrium"      , info=(3097, 0))
    HASSIUM       = SaltVersion("Hassium"      , info=(3098, 0))
    MEITNERIUM    = SaltVersion("Meitnerium"   , info=(3099, 0))
    DARMSTADTIUM  = SaltVersion("Darmstadtium" , info=(3100, 0))
    ROENTGENIUM   = SaltVersion("Roentgenium"  , info=(3101, 0))
    COPERNICIUM   = SaltVersion("Copernicium"  , info=(3102, 0))
    NIHONIUM      = SaltVersion("Nihonium"     , info=(3103, 0))
    FLEROVIUM     = SaltVersion("Flerovium"    , info=(3104, 0))
    MOSCOVIUM     = SaltVersion("Moscovium"    , info=(3105, 0))
    LIVERMORIUM   = SaltVersion("Livermorium"  , info=(3106, 0))
    TENNESSINE    = SaltVersion("Tennessine"   , info=(3107, 0))
    OGANESSON     = SaltVersion("Oganesson"    , info=(3108, 0))
    # <---- Please refrain from fixing whitespace -----------------------------------
    # The idea is to keep this readable.
    # -------------------------------------------------------------------------------
    # pylint: enable=bad-whitespace,multiple-spaces-before-operator
    # fmt: on

    @classmethod
    def versions(cls):
        if not cls._sorted_versions:
            cls._sorted_versions = sorted(
                (getattr(cls, name) for name in dir(cls) if name.isupper()),
                key=operator.attrgetter("info"),
            )
        return cls._sorted_versions

    @classmethod
    def current_release(cls):
        if cls._current_release is None:
            for version in cls.versions():
                if version.released is False:
                    cls._current_release = version
                    break
        return cls._current_release

    @classmethod
    def next_release(cls):
        if cls._next_release is None:
            next_release_ahead = False
            for version in cls.versions():
                if next_release_ahead:
                    cls._next_release = version
                    break
                if version == cls.current_release():
                    next_release_ahead = True
        return cls._next_release

    @classmethod
    def previous_release(cls):
        if cls._previous_release is None:
            previous = None
            for version in cls.versions():
                if version == cls.current_release():
                    break
                previous = version
            cls._previous_release = previous
        return cls._previous_release


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
        r"(?:(?P<pre_type>rc|a|b|alpha|beta|nb)(?P<pre_num>[\d]+))?"
        r"(?:(?:.*)(?:\+|-)(?P<noc>(?:0na|[\d]+|n/a))(?:-|\.)" + git_sha_regex + r")?"
    )
    git_sha_regex = r"^" + git_sha_regex

    git_sha_regex = re.compile(git_sha_regex)

    NAMES = {v.name: v.info for v in SaltVersionsInfo.versions()}
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
        if self.can_have_dot_zero(major):
            minor = minor if minor else 0

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
        elif isinstance(noc, str) and noc in ("0na", "n/a"):
            noc = -1
        elif isinstance(noc, str):
            noc = int(noc)

        self.major = major
        self.minor = minor
        self.bugfix = bugfix
        self.mbugfix = mbugfix
        self.pre_type = pre_type
        self.pre_num = pre_num
        if self.can_have_dot_zero(major):
            vnames_key = (major, 0)
        elif self.new_version(major):
            vnames_key = (major,)
        else:
            vnames_key = (major, minor)
        self.name = self.VNAMES.get(vnames_key)
        self.noc = noc
        self.sha = sha

    def new_version(self, major):
        """
        determine if using new versioning scheme
        """
        return bool(int(major) >= 3000 and int(major) < VERSION_LIMIT)

    def can_have_dot_zero(self, major):
        """
        determine if using new versioning scheme
        """
        return bool(int(major) >= 3006 and int(major) < VERSION_LIMIT)

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
        import salt.utils.versions

        salt.utils.versions.warn_until(
            SaltVersionsInfo.SULFUR,
            "The use of SaltStackVersion.from_last_named_version() is "
            "deprecated and set to be removed in {version}. Please use "
            "SaltStackVersion.current_release() instead.",
        )
        return cls.current_release()

    @classmethod
    def current_release(cls):
        return cls(*SaltVersionsInfo.current_release().info)

    @classmethod
    def next_release(cls):
        return cls(*SaltVersionsInfo.next_release().info)

    @property
    def sse(self):
        # Higher than 0.17, lower than first date based
        return 0 < self.major < 2014

    def min_info(self):
        info = [self.major]
        if self.new_version(self.major):
            if self.minor:
                info.append(self.minor)
            elif self.can_have_dot_zero(self.major):
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
            if not self.minor and self.can_have_dot_zero(self.major):
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
                noc = "0na"
            version_string += "+{}.{}".format(noc, self.sha)
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
            if not self.can_have_dot_zero(self.major) and not self.minor:
                parts.remove("".join([x for x in parts if re.search("^minor*", x)]))
        else:
            parts.extend(["bugfix={}".format(self.bugfix)])

        if self.mbugfix:
            parts.append("minor-bugfix={}".format(self.mbugfix))
        if self.pre_type:
            parts.append("{}={}".format(self.pre_type, self.pre_num))
        noc = self.noc
        if noc == -1:
            noc = "0na"
        if noc and self.sha:
            parts.extend(["noc={}".format(noc), "sha={}".format(self.sha)])
        return "<{} {}>".format(self.__class__.__name__, " ".join(parts))


# ----- Hardcoded Salt Codename Version Information ----------------------------------------------------------------->
#
#   There's no need to do anything here. The last released codename will be picked up
# --------------------------------------------------------------------------------------------------------------------
__saltstack_version__ = SaltStackVersion.current_release()
# <---- Hardcoded Salt Version Information ---------------------------------------------------------------------------


# ----- Dynamic/Runtime Salt Version Information -------------------------------------------------------------------->
def __discover_version(saltstack_version):
    # This might be a 'python setup.py develop' installation type. Let's
    # discover the version information at runtime.
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
                "--long",
                "--match",
                "v[0-9]*",
                "--always",
            ],
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
    _hardcoded_version_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_version.txt"
    )
    if not os.path.exists(_hardcoded_version_file):
        return __discover_version(saltstack_version)
    with open(  # pylint: disable=resource-leakage
        _hardcoded_version_file, encoding="utf-8"
    ) as rfh:
        return SaltStackVersion.parse(rfh.read().strip())


# Get additional version information if available
__saltstack_version__ = __get_version(__saltstack_version__)
if __saltstack_version__.name:
    # Set SaltVersionsInfo._current_release to avoid lookups when finding previous and next releases
    SaltVersionsInfo._current_release = getattr(
        SaltVersionsInfo, __saltstack_version__.name.upper()
    )

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
        ("msgpack", "msgpack", "version"),
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
        ("packaging", "packaging", "__version__"),
        ("looseversion", "looseversion", None),
    ]

    if include_salt_cloud:
        libs.append(
            ("Apache Libcloud", "libcloud", "__version__"),
        )

    for name, imp, attr in libs:
        if imp is None:
            yield name, attr
            continue
        try:
            if attr is None:
                # Late import to reduce the needed available modules and libs
                # installed when running `python salt/version.py`
                from salt._compat import importlib_metadata

                version = importlib_metadata.version(imp)
                yield name, version
                continue
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


def extensions_information():
    """
    Gather infomation about any installed salt extensions
    """
    # Late import
    import salt.utils.entrypoints

    extensions = {}
    for entry_point in salt.utils.entrypoints.iter_entry_points("salt.loader"):
        dist_nv = salt.utils.entrypoints.name_and_version_from_entry_point(entry_point)
        if not dist_nv:
            continue
        if dist_nv.name in extensions:
            continue
        extensions[dist_nv.name] = dist_nv.version
    return extensions


def versions_information(include_salt_cloud=False, include_extensions=True):
    """
    Report the versions of dependent software.
    """
    salt_info = list(salt_information())
    lib_info = list(dependency_information(include_salt_cloud))
    sys_info = list(system_information())

    info = {
        "Salt Version": dict(salt_info),
        "Dependency Versions": dict(lib_info),
        "System Versions": dict(sys_info),
    }
    if include_extensions:
        extensions_info = extensions_information()
        if extensions_info:
            info["Salt Extensions"] = extensions_info
    return info


def versions_report(include_salt_cloud=False, include_extensions=True):
    """
    Yield each version properly formatted for console output.
    """
    ver_info = versions_information(
        include_salt_cloud=include_salt_cloud, include_extensions=include_extensions
    )
    not_installed = "Not Installed"
    ns_pad = len(not_installed)
    lib_pad = max(len(name) for name in ver_info["Dependency Versions"])
    sys_pad = max(len(name) for name in ver_info["System Versions"])
    if include_extensions and "Salt Extensions" in ver_info:
        ext_pad = max(len(name) for name in ver_info["Salt Extensions"])
    else:
        ext_pad = 1
    padding = max(lib_pad, sys_pad, ns_pad, ext_pad) + 1

    fmt = "{0:>{pad}}: {1}"
    info = []
    for ver_type in (
        "Salt Version",
        "Dependency Versions",
        "Salt Extensions",
        "System Versions",
    ):
        if ver_type == "Salt Extensions" and ver_type not in ver_info:
            # No salt Extensions to report
            continue
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

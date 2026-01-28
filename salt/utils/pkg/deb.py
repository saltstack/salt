"""
Common functions for working with deb packages
"""

import logging
import os
import re
from collections import OrderedDict

from salt.exceptions import SaltInvocationError
import salt.utils.files

log = logging.getLogger(__name__)


_APT_SOURCES_LIST = "/etc/apt/sources.list"
_APT_SOURCES_PARTSDIR = "/etc/apt/sources.list.d/"


def string_to_bool(s):
    """
    Convert string representation of bool values to bool
    """
    if isinstance(s, bool):
        return s
    s = s.lower()
    if s in ("no", "false", "without", "off", "disable"):
        return False
    elif s in ("yes", "true", "with", "on", "enable"):
        return True
    raise ValueError(f"Unable to convert to boolean: {s}")


class Deb822Section:
    """
    A deb822 section representation of single entry,
    which could contain comments.
    """

    def __init__(self, section):
        """
        Init new deb822 section object
        """
        if isinstance(section, Deb822Section):
            self.tags = OrderedDict(section.tags)
            self.header = section.header
            self.footer = section.footer
        else:
            self.tags, self.header, self.footer = self._parse_section_string(section)
        self._tag_map = {k.lower(): k for k in self.tags}

    @staticmethod
    def _parse_section_string(section_string):
        """
        Parse section string to comments and tags
        """
        header = []
        footer = []
        raw_data = []
        tag_re = re.compile(r"\A(\S+):\s*(\S.*|)")
        tags = OrderedDict()

        for line in section_string.splitlines():
            if line.startswith("#"):
                if raw_data:
                    footer.append(line)
                else:
                    header.append(line)
            else:
                raw_data.append(line)

        tag = None
        value = None
        for line in raw_data:
            match = tag_re.match(line)
            if match:
                if tag is not None:
                    # Store previous found tag,
                    # as the values could contain multiple lines
                    tags[tag] = value.strip()
                tag, value = match.groups()
            elif line == "" and tag is not None:
                tags[tag] = value.strip()
            else:
                value = f"{value}\n{line}"
        if tag is not None:
            tags[tag] = value.strip()

        return tags, header, footer

    def __getitem__(self, key):
        """
        Get the value of a tag
        """
        return self.tags[self._tag_map.get(key.lower(), key)]

    def __delitem__(self, key):
        """
        Delete the tag
        """
        _lc_key = key.lower()
        del self.tags[self._tag_map.get(_lc_key, key)]
        del self._tag_map[_lc_key]

    def __setitem__(self, key, val):
        """
        Set the value of the tag
        """
        _lc_key = key.lower()
        if _lc_key not in self._tag_map:
            self._tag_map[_lc_key] = key
        self.tags[key] = val

    def __bool__(self):
        """
        Represent as True if the section has any tag
        """
        return bool(self.tags)

    def get(self, key, default=None):
        """
        Get the value of a tag or return default
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __str__(self):
        """
        Return the string representation of the section
        """
        return (
            "\n".join(self.header)
            + ("\n" if self.header else "")
            + "".join(
                (f"{k}: {v}\n" if str(v) != "" else "") for k, v in self.tags.items()
            )
            + "\n".join(self.footer)
            + ("\n" if self.footer else "")
        )


class Deb822SourceEntry:
    """
    Source entry in deb822 format
    """

    _properties = {
        "architectures": {"key": "Architectures", "multi": True},
        "types": {"key": "Types", "multi": True},
        "type": {"key": "Types", "multi": False, "deprecated": True},
        "uris": {"key": "URIs", "multi": True},
        "uri": {"key": "URIs", "multi": False, "deprecated": True},
        "suites": {"key": "Suites", "multi": True},
        "dist": {"key": "Suites", "multi": False, "deprecated": True},
        "comps": {"key": "Components", "multi": True},
        "signedby": {"key": "Signed-By", "multi": False},
    }

    def __init__(
        self,
        section,
        file,
        list=None,
    ):
        if section is None:
            self.section = Deb822Section("")
        elif isinstance(section, str):
            self.section = Deb822Section(section)
        else:
            self.section = section

        self._line = str(self.section)
        self.file = file

    def __getattr__(self, name):
        """
        Get the values to the section for specified keys
        """
        if name in self._properties:
            if self._properties[name]["multi"]:
                return SourceEntry.split_source_line(
                    self.section.get(self._properties[name]["key"], "")
                )
            else:
                return self.section.get(self._properties[name]["key"], None)

    def __setattr__(self, name, value):
        """
        Pass the values to the section for specified keys
        """
        if name not in self._properties:
            return super().__setattr__(name, value)

        key = self._properties[name]["key"]
        if value is None:
            del self.section[key]
        else:
            if key == "Signed-By":
                value = str(value)
            self.section[key] = (
                " ".join(value) if self._properties[name]["multi"] else value
            )

    def __eq__(self, other):
        """
        Equal operator for deb822 source entries
        """
        return (
            self.disabled == other.disabled
            and self.type == other.type
            and set([uri.rstrip("/") for uri in self.uris])
            == set([uri.rstrip("/") for uri in other.uris])
            and self.dist == other.dist
            and self.comps == other.comps
        )

    @property
    def comment(self):
        """
        Returns the header of the section
        """
        return "\n".join(self.section.header)

    @comment.setter
    def comment(self, comment):
        """
        Sets the header of the section
        """
        comments = comment.splitlines()
        if not all(x.startswith("#") for x in comments):
            comments = [f"#{x}" for x in comments]
        self.section.header = comments

    @property
    def trusted(self):
        """
        Return the value of the Trusted field
        """
        try:
            return string_to_bool(self.section["Trusted"])
        except KeyError:
            return None

    @trusted.setter
    def trusted(self, value):
        if isinstance(value, bool):
            self.section["Trusted"] = "yes" if value else "no"
        elif isinstance(value, int) and value in (0, 1):
            self.section["Trusted"] = "yes" if value == 1 else "no"
        elif isinstance(value, str):
            self.section["Trusted"] = "yes" if string_to_bool(value) else "no"
        else:
            try:
                del self.section["Trusted"]
            except KeyError:
                pass

    @property
    def disabled(self):
        """
        Return True if the source is enabled
        """
        return not string_to_bool(self.section.get("Enabled", "yes"))

    @disabled.setter
    def disabled(self, value):
        if value:
            self.section["Enabled"] = "no"
        else:
            try:
                del self.section["Enabled"]
            except KeyError:
                pass

    @property
    def invalid(self):
        """
        Return True if the source doesn't have proper attributes
        """
        return not self.section

    @property
    def line(self):
        """
        Return the original string representation of the source entry
        """
        return self._line

    def __str__(self):
        """
        Return the string representation of the entry
        """
        return str(self.section).strip()


class SourceEntry:
    """
    Distinct sources.list entry
    """

    def __init__(self, line, file=None):
        self.invalid = False
        self.disabled = False  # identified as disabled if commented
        self.type = ""  # type of the source (deb, deb-src)
        self.architectures = []
        self._signedby = ""
        self._trusted = None
        self.uri = ""
        self.dist = ""  # distribution name
        self.comps = []  # list of available componetns (or empty)
        self.comment = ""  # comment (optional)
        self.line = line  # the original sources.list entry
        if file is None:
            file = _APT_SOURCES_LIST
        if file.endswith(".sources"):
            raise ValueError("Classic SourceEntry cannot be written to .sources file")
        self.file = file  # the file that the entry is located in
        self.parse(line)
        self.children = []

    def __eq__(self, other):
        """
        Equal operator for two classic sources.list entries
        """
        return (
            self.disabled == other.disabled
            and self.type == other.type
            and self.uri.rstrip("/") == other.uri.rstrip("/")
            and self.dist == other.dist
            and self.comps == other.comps
        )

    @staticmethod
    def split_source_line(line):
        """
        Splits the entries of sources.list format
        """
        line = line.strip()
        pieces = []
        tmp = ""
        # we are inside a [..] block
        p_found = False
        space_found = False
        for c in line:
            if c == "[":
                if space_found:
                    space_found = False
                    p_found = True
                    pieces.append(tmp)
                    tmp = c
                else:
                    p_found = True
                    tmp += c
            elif c == "]":
                p_found = False
                tmp += c
            elif space_found and not c.isspace():
                # we skip one or more space
                space_found = False
                pieces.append(tmp)
                tmp = c
            elif c.isspace() and not p_found:
                # found a whitespace
                space_found = True
            else:
                tmp += c
        # append last piece
        if len(tmp) > 0:
            pieces.append(tmp)
        return pieces

    def parse(self, line):
        """
        Parse lines from sources files
        """
        self.disabled, self.invalid, self.comment, repo_line = _invalid(line)
        if self.invalid:
            return False
        if repo_line[1].startswith("["):
            repo_line = [x for x in (line.strip("[]") for line in repo_line) if x]
            opts = _get_opts(self.line)
            if "arch" in opts:
                self.architectures.extend(opts["arch"]["value"])
            if "signedby" in opts:
                self.signedby = opts["signedby"]["value"]
            if "trusted" in opts:
                self.trusted = opts["trusted"]["value"]
            for opt in opts.values():
                opt = opt["full"]
                if opt:
                    try:
                        repo_line.pop(repo_line.index(opt))
                    except ValueError:
                        repo_line.pop(repo_line.index(f"[{opt}]"))
        if len(repo_line) < 3:
            raise SaltInvocationError(f"Invalid repository definition: {' '.join(repo_line)}")
        self.type = repo_line[0]
        self.uri = repo_line[1]
        self.dist = repo_line[2]
        self.comps = repo_line[3:]
        return True

    def __str__(self):
        """
        Return string representation
        """
        return self.repo_line().strip()

    def repo_line(self):
        """
        Return the line of the entry for the sources file
        """
        repo_line = []
        if self.invalid:
            return self.line
        if self.disabled:
            repo_line.append("#")

        repo_line.append(self.type)
        opts = _get_opts(self.line)
        if self.architectures:
            if "arch" not in opts:
                opts["arch"] = {}
            opts["arch"]["full"] = f"arch={','.join(self.architectures)}"
            opts["arch"]["value"] = self.architectures
        if self.signedby:
            if "signedby" not in opts:
                opts["signedby"] = {}
            opts["signedby"]["full"] = f"signed-by={self.signedby}"
            opts["signedby"]["value"] = self.signedby
        if self._trusted:
            if "trusted" not in opts:
                opts["trusted"] = {}
            opts["trusted"]["value"] = "yes" if self._trusted else "no"
            opts["trusted"]["full"] = f"trusted={opts['trusted']['value']}"
        if "trusted" in opts and opts["trusted"]["value"] == "no":
            del opts["trusted"]

        ordered_opts = []
        for opt in opts.values():
            if opt["full"] != "":
                ordered_opts.append(opt["full"])

        if ordered_opts:
            repo_line.append(f"[{' '.join(ordered_opts)}]")

        repo_line += [self.uri, self.dist, " ".join(self.comps)]
        if self.comment:
            repo_line.append(f"#{self.comment}")
        return " ".join(repo_line) + "\n"

    @property
    def types(self):
        """
        Deb822 compatible attribute for the type
        """
        return [self.type]

    @property
    def uris(self):
        """
        Deb822 compatible attribute for the uri
        """
        return [self.uri]

    @property
    def suites(self):
        """
        Deb822 compatible attribute for the suite
        """
        if self.dist:
            return [self.dist]
        return []

    @suites.setter
    def suites(self, suites):
        """
        Deb822 compatible setter for the suite
        """
        if len(suites) > 1:
            raise ValueError("Only one suite is possible for non deb822 source entry")
        if suites:
            self.dist = str(suites[0])
            assert self.dist == suites[0]
        else:
            self.dist = ""
            assert self.dist == ""

    @property
    def signedby(self):
        """
        Deb822 compatible attribute for the signedby
        """
        return self._signedby

    @signedby.setter
    def signedby(self, signedby):
        """
        Deb822 compatible setter for the signedy
        """
        self._signedby = str(signedby)

    @property
    def trusted(self):
        """
        Deb822 compatible attribute for the trusted
        """
        return self._trusted

    @trusted.setter
    def trusted(self, trusted):
        """
        Deb822 compatible setter for the trusted
        """
        if isinstance(trusted, bool):
            self._trusted = trusted
        elif isinstance(trusted, int) and trusted in (0, 1):
            self._trusted = trusted == 1
        elif isinstance(trusted, str):
            self._trusted = string_to_bool(trusted)
        else:
            self._trusted = None


class SourcesList:
    """
    Represents the full sources.list + sources.list.d files
    including deb822 .sources files
    """

    def __init__(
        self,
    ):
        self.list = []  # the actual SourceEntries Type
        self.refresh()

    def refresh(self):
        """update the list of known entries"""
        self.list = []
        # read sources.list
        file = _APT_SOURCES_LIST
        if os.path.isfile(file):
            self.load(file)
        # read sources.list.d
        partsdir = _APT_SOURCES_PARTSDIR
        if os.path.isdir(partsdir):
            for file in os.listdir(partsdir):
                if file.endswith(".sources") or file.endswith(".list"):
                    self.load(os.path.join(partsdir, file))

    def __iter__(self):
        """
        Iterate over self.list with SourceEntry elements
        """
        yield from self.list

    def add(
        self,
        type,
        uri,
        dist,
        orig_comps,
        comment="",
        pos=-1,
        file=None,
        architectures=None,
        signedby="",
        suites=None,
        trusted=False,
        types=None,
        parent=None,
        uris=None,
    ):
        """
        Add a new source to the sources.list.
        The method will search for existing matching repos and will try to
        reuse them as far as possible
        """

        type = type.strip()
        disabled = type.startswith("#")
        if disabled:
            type = type[1:].lstrip()
        if architectures is None:
            architectures = []
        # create a working copy of the component list so that
        # we can modify it later
        comps = orig_comps[:]

        new_entry = None
        if file is None:
            file = _APT_SOURCES_LIST
        if file.endswith(".sources"):
            new_entry = Deb822SourceEntry(None, file=file, list=self)
            if parent:
                parent = getattr(parent, "parent", parent)
                assert isinstance(parent, Deb822SourceEntry)
                for k in parent.section.tags:
                    new_entry.section[k] = parent.section[k]
            new_entry.types = types if types and isinstance(types, list) else [type]
            new_entry.uris = uris if uris and isinstance(uris, list) else [uri]
            new_entry.suites = suites if suites and isinstance(suites, list) else [dist]
            new_entry.comps = comps
            if architectures:
                new_entry.architectures = list(architectures)
            new_entry.section.header = (
                comment if isinstance(comment, list) else [comment]
            )
            new_entry.disabled = disabled
            if signedby:
                new_entry.signedby = signedby
            if trusted is not False:
                new_entry.trusted = trusted
        else:
            ext_attrs = ""
            if architectures:
                ext_attrs = f"arch={','.join(architectures)}"
            if signedby:
                if ext_attrs:
                    ext_attrs = f"{ext_attrs} "
                ext_attrs = f"{ext_attrs}signed-by={signedby}"
            if trusted:
                if ext_attrs:
                    ext_attrs = f"{ext_attrs} "
                ext_attrs = f"{ext_attrs}trusted=yes"
            parts = [
                "#" if disabled else "",
                type,
                f"[{ext_attrs}]" if ext_attrs else "",
                uri,
                dist,
            ]
            parts.extend(comps)
            if comment:
                parts.append("#" + comment)
            line = " ".join(part for part in parts if part) + "\n"

            new_entry = SourceEntry(line)
            if file is not None:
                new_entry.file = file

        if pos < 0:
            self.list.append(new_entry)
        else:
            self.list.insert(pos, new_entry)
        return new_entry

    def remove(self, source_entry):
        """
        Remove the entry from the sources.list
        """
        self.list.remove(source_entry)

    def load_deb822_sections(self, file_obj):
        """
        Return Deb822 sections from .sources file object
        """
        sections = []
        section = ""
        for line in file_obj:
            if not line.isspace():
                # Consider not empty line as a part of a section
                section += line
            elif section:
                # Add a new section on getting first space line
                sections.append(Deb822Section(section))
                section = ""

        # Create the last section if we still have data for it
        if section:
            sections.append(Deb822Section(section))

        return sections

    def load(self, file_path):
        """
        Load the sources from the file
        """
        try:
            with salt.utils.files.fopen(file_path) as f:
                if file_path.endswith(".sources"):
                    for section in self.load_deb822_sections(f):
                        self.list.append(
                            Deb822SourceEntry(section, file_path, list=self)
                        )
                else:
                    for line in f:
                        source = SourceEntry(line, file_path)
                        self.list.append(source)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Could not parse source file '%s'", file_path, exc_info=True)

    def index(self, entry):
        return self.list.index(entry)

    def save(self):
        """save the current sources"""
        # write an empty default config file if there aren't any sources
        if len(self.list) == 0:
            path = _APT_SOURCES_LIST
            header = (
                "## See sources.list(5) for more information, especialy\n"
                "# Remember that you can only use http, ftp or file URIs\n"
                "# CDROMs are managed through the apt-cdrom tool.\n"
            )

            try:
                with salt.utils.files.fopen(path, "w") as f:
                    f.write(header)
            except FileNotFoundError:
                # No need to create file if there is no apt directory
                pass
            return

        files = {}
        for source in self.list:
            if source.file not in files:
                files[source.file] = []
            elif isinstance(source, Deb822SourceEntry):
                files[source.file].append("\n")
            files[source.file].append(str(source) + "\n")
        for file in files:
            with salt.utils.files.fopen(file, "w") as f:
                f.write("".join(files[file]))


def _invalid(line):
    """
    This is a workaround since python3-apt does not support
    the signed-by argument. This function was removed from
    the class to ensure users using the python3-apt module or
    not can use the signed-by option.
    """
    disabled = False
    invalid = False
    comment = ""
    line = line.strip()
    if not line:
        invalid = True
        return disabled, invalid, comment, ""

    if line.startswith("#"):
        disabled = True
        line = line[1:]

    idx = line.find("#")
    if idx > 0:
        comment = line[idx + 1 :]
        line = line[:idx]

    cdrom_match = re.match(r"(.*)(cdrom:.*/)(.*)", line.strip())
    if cdrom_match:
        repo_line = (
            [p.strip() for p in cdrom_match.group(1).split()]
            + [cdrom_match.group(2).strip()]
            + [p.strip() for p in cdrom_match.group(3).split()]
        )
    else:
        repo_line = line.strip().split()
    if (
        not repo_line
        or repo_line[0] not in ["deb", "deb-src", "rpm", "rpm-src"]
        or len(repo_line) < 3
    ):
        invalid = True
        return disabled, invalid, comment, repo_line

    if repo_line[1].startswith("["):
        if not any(x.endswith("]") for x in repo_line[1:]):
            invalid = True
            return disabled, invalid, comment, repo_line

    return disabled, invalid, comment, repo_line


def _get_opts(line):
    """
    Return all opts in [] for a repo line
    """
    get_opts = re.search(r"\[(.*?=.*?)\]", line)
    ret = OrderedDict()

    if not get_opts:
        return ret
    opts = get_opts.group(0).strip("[]")
    architectures = []
    for opt in opts.split():
        if opt.startswith("arch"):
            architectures.extend(opt.split("=", 1)[1].split(","))
            ret["arch"] = {}
            ret["arch"]["full"] = opt
            ret["arch"]["value"] = architectures
        elif opt.startswith("signed-by"):
            ret["signedby"] = {}
            ret["signedby"]["full"] = opt
            ret["signedby"]["value"] = opt.split("=", 1)[1]
        else:
            other_opt = opt.split("=", 1)[0]
            ret[other_opt] = {}
            ret[other_opt]["full"] = opt
            ret[other_opt]["value"] = opt.split("=", 1)[1]
    return ret


def combine_comments(comments):
    """
    Given a list of comments, or a comment submitted as a string, return a
    single line of text containing all of the comments.
    """
    if isinstance(comments, list):
        comments = [c if isinstance(c, str) else str(c) for c in comments]
    else:
        if not isinstance(comments, str):
            comments = [str(comments)]
        else:
            comments = [comments]
    return " ".join(comments).strip()


def strip_uri(repo):
    """
    Remove the trailing slash from the URI in a repo definition
    """
    splits = repo.split()
    for idx, val in enumerate(splits):
        if any(val.startswith(x) for x in ("http://", "https://", "ftp://")):
            splits[idx] = val.rstrip("/")
    return " ".join(splits)

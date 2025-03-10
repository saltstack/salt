"""
Common functions for working with deb packages
"""

import logging
import os
import re
import weakref
from collections import OrderedDict
from typing import Generic, TypeVar, Union

import salt.utils.files

log = logging.getLogger(__name__)


_APT_SOURCES_LIST = "/etc/apt/sources.list"
_APT_SOURCES_PARTSDIR = "/etc/apt/sources.list.d/"


def string_to_bool(s):
    """
    Convert string representation of bool values to integer
    """
    s = s.lower()
    if s in ("no", "false", "without", "off", "disable"):
        return 0
    elif s in ("yes", "true", "with", "on", "enable"):
        return 1
    return -1


class TagSection:

    def __init__(self, section):
        self._data = section
        self._re = re.compile(r"\A(\S+): (.*)")

    def __iter__(self):
        lines = self._data.split("\n")
        tag = None
        value = None
        while lines:
            line = lines.pop(0)
            match = self._re.match(line)
            if match:
                if tag is not None:
                    yield tag, value.strip()
                tag = match.group(1)
                value = match.group(2)
            elif line == "" and tag is not None:
                yield tag, value.strip()
            else:
                value = f"{value}\n{line}"
        if tag is not None:
            yield tag, value.strip()


class Section:
    """A single deb822 section, possibly with comments.

    This represents a single deb822 section.
    """

    tags: OrderedDict
    _case_mapping: dict
    header: str
    footer: str

    def __init__(self, section):
        if isinstance(section, Section):
            self.tags = OrderedDict(section.tags)
            self._case_mapping = {k.casefold(): k for k in self.tags}
            self.header = section.header
            self.footer = section.footer
            return

        comments = ["", ""]
        in_section = False
        trimmed_section = ""

        for line in section.split("\n"):
            if line.startswith("#"):
                # remove the leading #
                line = line[1:]
                comments[in_section] += line + "\n"
                continue

            in_section = True
            trimmed_section += line + "\n"

        self.tags = OrderedDict(TagSection(trimmed_section))
        self._case_mapping = {k.casefold(): k for k in self.tags}
        self.header, self.footer = comments

    def __getitem__(self, key):
        """Get the value of a field."""
        return self.tags[self._case_mapping.get(key.casefold(), key)]

    def __delitem__(self, key):
        """Delete a field"""
        del self.tags[self._case_mapping.get(key.casefold(), key)]

    def __setitem__(self, key, val):
        """Set the value of a field."""
        if key.casefold() not in self._case_mapping:
            self._case_mapping[key.casefold()] = key
        self.tags[self._case_mapping[key.casefold()]] = val

    def __bool__(self):
        return bool(self.tags)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    @staticmethod
    def __comment_lines(content):
        return (
            "\n".join("#" + line for line in content.splitlines()) + "\n"
            if content
            else ""
        )

    def __str__(self):
        """Canonical string rendering of this section."""
        return (
            self.__comment_lines(self.header)
            + "".join(f"{k}: {v}\n" for k, v in self.tags.items())
            + self.__comment_lines(self.footer)
        )


class File:
    """
    Parse a given file object into a list of Section objects.
    """

    def __init__(self, fobj):
        self.sections = []
        section = ""
        for line in fobj:
            if not line.isspace():
                # A line is part of the section if it has non-whitespace characters
                section += line
            elif section:
                # Our line is just whitespace and we have gathered section content, so let's write out the section
                self.sections.append(Section(section))
                section = ""

        # The final section may not be terminated by an empty line
        if section:
            self.sections.append(Section(section))

    def __iter__(self):
        return iter(self.sections)

    def __str__(self):
        return "\n".join(str(s) for s in self.sections)


class SingleValueProperty(property):
    def __init__(self, key, doc):
        self.key = key
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.section.get(self.key, None)

    def __set__(self, obj, value):
        if value is None:
            del obj.section[self.key]
        else:
            obj.section[self.key] = value


class MultiValueProperty(property):
    def __init__(self, key, doc):
        self.key = key
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return SourceEntry.mysplit(obj.section.get(self.key, ""))

    def __set__(self, obj, values):
        obj.section[self.key] = " ".join(values)


class ExplodedEntryProperty(property, Generic[TypeVar("T")]):
    def __init__(self, parent):
        self.parent = parent

    def __get__(
        self,
        obj,
        objtype=None,
    ):
        if obj is None:
            return self
        return self.parent.__get__(obj.parent)

    def __set__(self, obj, value):
        obj.split_out()
        self.parent.__set__(obj.parent, value)


def DeprecatedProperty(prop):
    """Wrapper to mark deprecated properties"""
    return prop


def _null_weakref():
    """Behaves like an expired weakref.ref, returning None"""
    return None


class Deb822SourceEntry:
    def __init__(
        self,
        section,
        file,
        list=None,
    ):
        if section is None:
            self.section = Section("")
        elif isinstance(section, str):
            self.section = Section(section)
        else:
            self.section = section

        self._line = str(self.section)
        self.file = file
        self.template = None  # type DistInfo.Suite
        self.may_merge = False
        self._children = weakref.WeakSet()

        if list:
            self._list = weakref.ref(list)
        else:
            self._list = _null_weakref

        self.signedby = self.section.tags.get("Signed-By", "")

    def __eq__(self, other):
        #  FIXME: Implement plurals more correctly
        """equal operator for two sources.list entries"""
        return (
            self.disabled == other.disabled
            and self.type == other.type
            and self.uri
            and self.uri.rstrip("/") == other.uri.rstrip("/")
            and self.dist == other.dist
            and self.comps == other.comps
        )

    architectures = MultiValueProperty("Architectures", "The list of architectures")
    types = MultiValueProperty("Types", "The list of types")
    type = DeprecatedProperty(SingleValueProperty("Types", "The list of types"))
    uris = MultiValueProperty("URIs", "URIs in the source")
    uri = DeprecatedProperty(SingleValueProperty("URIs", "URIs in the source"))
    suites = MultiValueProperty("Suites", "Suites in the source")
    dist = DeprecatedProperty(SingleValueProperty("Suites", "Suites in the source"))
    comps = MultiValueProperty("Components", "Components in the source")

    @property
    def comment(self):
        """Legacy attribute describing the paragraph header."""
        return self.section.header

    @comment.setter
    def comment(self, comment):
        """Legacy attribute describing the paragraph header."""
        self.section.header = comment

    @property
    def trusted(self):
        """Return the value of the Trusted field"""
        try:
            return string_to_bool(self.section["Trusted"])
        except KeyError:
            return None

    @trusted.setter
    def trusted(self, value):
        if value is None:
            try:
                del self.section["Trusted"]
            except KeyError:
                pass
        else:
            self.section["Trusted"] = "yes" if value else "no"

    @property
    def disabled(self):
        """Check if Enabled: no is set."""
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
        """A section is invalid if it doesn't have proper entries."""
        return not self.section

    @property
    def line(self):
        """The entire (original) paragraph."""
        return self._line

    def __str__(self):
        return self.str().strip()

    def str(self):
        """Section as a string, newline terminated."""
        return str(self.section)

    def set_enabled(self, enabled):
        """Deprecated (for deb822) accessor for .disabled"""
        self.disabled = not enabled

    def merge(self, other):
        """Merge the two entries if they are compatible."""
        if (
            not self.may_merge
            and self.template is None
            and not all(child.template for child in self._children)
        ):
            return False
        if self.file != other.file:
            return False
        if not isinstance(other, Deb822SourceEntry):
            return False
        if self.comment != other.comment and not any(
            "Added by software-properties" in c for c in (self.comment, other.comment)
        ):
            return False

        for tag in set(list(self.section.tags) + list(other.section.tags)):
            if tag.lower() in (
                "types",
                "uris",
                "suites",
                "components",
                "architectures",
                "signed-by",
            ):
                continue
            in_self = self.section.get(tag, None)
            in_other = other.section.get(tag, None)
            if in_self != in_other:
                return False

        if (
            sum(
                [
                    set(self.types) != set(other.types),
                    set(self.uris) != set(other.uris),
                    set(self.suites) != set(other.suites),
                    set(self.comps) != set(other.comps),
                    set(self.architectures) != set(other.architectures),
                ]
            )
            > 1
        ):
            return False

        for typ in other.types:
            if typ not in self.types:
                self.types += [typ]

        for uri in other.uris:
            if uri not in self.uris:
                self.uris += [uri]

        for suite in other.suites:
            if suite not in self.suites:
                self.suites += [suite]

        for component in other.comps:
            if component not in self.comps:
                self.comps += [component]

        for arch in other.architectures:
            if arch not in self.architectures:
                self.architectures += [arch]

        return True

    def _reparent_children(self, to):
        """If we end up being split, check if any of our children need to be reparented to the new parent."""
        for child in self._children:
            for typ in to.types:
                for uri in to.uris:
                    for suite in to.suites:
                        if (child._type, child._uri, child._suite) == (
                            typ,
                            uri,
                            suite,
                        ):
                            assert child.parent == self
                            child._parent = weakref.ref(to)


class ExplodedDeb822SourceEntry:
    """This represents a bit of a deb822 paragraph corresponding to a legacy sources.list entry"""

    # Mostly we use slots to prevent accidentally assigning unproxied attributes
    __slots__ = ["_parent", "_type", "_uri", "_suite", "template", "__weakref__"]

    def __init__(self, parent, typ, uri, suite):
        self._parent = weakref.ref(parent)
        self._type = typ
        self._uri = uri
        self._suite = suite
        self.template = parent.template
        parent._children.add(self)

    @property
    def parent(self):
        if self._parent is not None:
            parent = self._parent()
            if parent is not None:
                return parent
        raise ValueError("The parent entry is no longer valid")

    @property
    def uri(self):
        self.__check_valid()
        return self._uri

    @uri.setter
    def uri(self, uri):
        self.split_out()
        self.parent.uris = [u if u != self._uri else uri for u in self.parent.uris]
        self._uri = uri

    @property
    def types(self):
        return [self.type]

    @property
    def suites(self):
        return [self.dist]

    @property
    def uris(self):
        return [self.uri]

    @property
    def type(self):
        self.__check_valid()
        return self._type

    @type.setter
    def type(self, typ):
        self.split_out()
        self.parent.types = [typ]
        self._type = typ
        self.__check_valid()
        assert self._type == typ
        assert self.parent.types == [self._type]

    @property
    def dist(self):
        self.__check_valid()
        return self._suite

    @dist.setter
    def dist(self, suite):
        self.split_out()
        self.parent.suites = [suite]
        self._suite = suite
        self.__check_valid()
        assert self._suite == suite
        assert self.parent.suites == [self._suite]

    def __check_valid(self):
        if self.parent._list() is None:
            raise ValueError("The parent entry is dead")
        for type in self.parent.types:
            for uri in self.parent.uris:
                for suite in self.parent.suites:
                    if (type, uri, suite) == (self._type, self._uri, self._suite):
                        return
        raise ValueError(f"Could not find parent of {self}")

    def split_out(self):
        parent = self.parent
        if (parent.types, parent.uris, parent.suites) == (
            [self._type],
            [self._uri],
            [self._suite],
        ):
            return
        sources_list = parent._list()
        if sources_list is None:
            raise ValueError("The parent entry is dead")

        try:
            index = sources_list.list.index(parent)
        except ValueError as e:
            raise ValueError(
                f"Parent entry for partial deb822 {self} no longer valid"
            ) from e

        sources_list.remove(parent)

        reparented = False
        for type in reversed(parent.types):
            for uri in reversed(parent.uris):
                for suite in reversed(parent.suites):
                    new = Deb822SourceEntry(
                        section=Section(parent.section),
                        file=parent.file,
                        list=sources_list,
                    )
                    new.types = [type]
                    new.uris = [uri]
                    new.suites = [suite]
                    new.may_merge = True

                    parent._reparent_children(new)
                    sources_list.list.insert(index, new)
                    if (type, uri, suite) == (self._type, self._uri, self._suite):
                        self._parent = weakref.ref(new)
                        reparented = True
        if not reparented:
            raise ValueError(f"Could not find parent of {self}")

    def __repr__(self):
        return f"<child {self._type} {self._uri} {self._suite} of {self._parent}"

    architectures = ExplodedEntryProperty(Deb822SourceEntry.architectures)
    comps = ExplodedEntryProperty(Deb822SourceEntry.comps)
    invalid = ExplodedEntryProperty(Deb822SourceEntry.invalid)
    disabled = ExplodedEntryProperty(Deb822SourceEntry.disabled)
    trusted = ExplodedEntryProperty(Deb822SourceEntry.trusted)
    comment = ExplodedEntryProperty(Deb822SourceEntry.comment)

    def set_enabled(self, enabled):
        """Set the source to enabled."""
        self.disabled = not enabled

    @property
    def file(self):
        """Return the file."""
        return self.parent.file


class SourceEntry:
    """single sources.list entry"""

    def __init__(self, line, file=None):
        self.invalid = False  # is the source entry valid
        self.disabled = False  # is it disabled ('#' in front)
        self.type = ""  # what type (deb, deb-src)
        self.architectures = []  # architectures
        self.signedby = ""  # signed-by
        self.trusted = None  # Trusted
        self.uri = ""  # base-uri
        self.dist = ""  # distribution (dapper, edgy, etc)
        self.comps = []  # list of available componetns (may empty)
        self.comment = ""  # (optional) comment
        self.line = line  # the original sources.list line
        if file is None:
            file = _APT_SOURCES_LIST
        if file.endswith(".sources"):
            raise ValueError("Classic SourceEntry cannot be written to .sources file")
        self.file = file  # the file that the entry is located in
        self._parse_sources(line)
        self.template = None  # type DistInfo.Suite
        self.children = []

    def __eq__(self, other):
        """equal operator for two sources.list entries"""
        return (
            self.disabled == other.disabled
            and self.type == other.type
            and self.uri.rstrip("/") == other.uri.rstrip("/")
            and self.dist == other.dist
            and self.comps == other.comps
        )

    @staticmethod
    def mysplit(line):
        """a split() implementation that understands the sources.list
        format better and takes [] into account (for e.g. cdroms)"""
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
        """parse a given sources.list (textual) line and break it up
        into the field we have"""
        return self._parse_sources(line)

    def __str__(self):
        """debug helper"""
        return self.str().strip()

    def str(self):
        return self.repo_line()

    def repo_line(self):
        """
        Return the repo line for the sources file
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

    def _parse_sources(self, line):
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
            for opt in opts.values():
                opt = opt["full"]
                if opt:
                    try:
                        repo_line.pop(repo_line.index(opt))
                    except ValueError:
                        repo_line.pop(repo_line.index(f"[{opt}]"))
        self.type = repo_line[0]
        self.uri = repo_line[1]
        self.dist = repo_line[2]
        self.comps = repo_line[3:]
        return True

    @property
    def types(self):
        """deb822 compatible accessor for the type"""
        return [self.type]

    @property
    def uris(self):
        """deb822 compatible accessor for the uri"""
        return [self.uri]

    @property
    def suites(self):
        """deb822 compatible accessor for the suite"""
        if self.dist:
            return [self.dist]
        return []

    @suites.setter
    def suites(self, suites):
        """deb822 compatible setter for the suite"""
        if len(suites) > 1:
            raise ValueError("Only one suite is possible for non deb822 source entry")
        if suites:
            self.dist = str(suites[0])
            assert self.dist == suites[0]
        else:
            self.dist = ""
            assert self.dist == ""


AnySourceEntry = Union[SourceEntry, Deb822SourceEntry]
AnyExplodedSourceEntry = Union[
    SourceEntry, Deb822SourceEntry, ExplodedDeb822SourceEntry
]


class SourcesList:
    """represents the full sources.list + sources.list.d file"""

    def __init__(
        self,
        deb822=True,
    ):
        self.list = []  # the actual SourceEntries Type
        self.deb822 = deb822
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
                if (self.deb822 and file.endswith(".sources")) or file.endswith(
                    ".list"
                ):
                    self.load(os.path.join(partsdir, file))

    def __iter__(self):
        """simple iterator to go over self.list, returns SourceEntry
        types"""
        yield from self.list

    def __find(self, *predicates, **attrs):
        uri = attrs.pop("uri", None)
        for source in self.exploded_list():
            if uri and source.uri and uri.rstrip("/") != source.uri.rstrip("/"):
                continue
            if all(getattr(source, key) == attrs[key] for key in attrs) and all(
                predicate(source) for predicate in predicates
            ):
                yield source

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
        parent=None,
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
        architectures = set(architectures)
        # create a working copy of the component list so that
        # we can modify it later
        comps = orig_comps[:]
        sources = self.__find(
            lambda s: set(s.architectures) == architectures,
            disabled=disabled,
            invalid=False,
            type=type,
            uri=uri,
            dist=dist,
        )
        # check if we have this source already in the sources.list
        for source in sources:
            for new_comp in comps:
                if new_comp in source.comps:
                    # we have this component already, delete it
                    # from the new_comps list
                    del comps[comps.index(new_comp)]
                    if len(comps) == 0:
                        return source

        sources = self.__find(
            lambda s: set(s.architectures) == architectures,
            invalid=False,
            type=type,
            uri=uri,
            dist=dist,
        )
        for source in sources:
            if source.disabled == disabled:
                # if there is a repo with the same (disabled, type, uri, dist)
                # just add the components
                if set(source.comps) != set(comps):
                    source.comps = list(set(source.comps + comps))
                return source
            elif source.disabled and not disabled:
                # enable any matching (type, uri, dist), but disabled repo
                if set(source.comps) == set(comps):
                    source.disabled = False
                    return source

        new_entry: AnySourceEntry
        if file is None:
            file = _APT_SOURCES_LIST
        if file.endswith(".sources"):
            new_entry = Deb822SourceEntry(None, file=file, list=self)
            if parent:
                parent = getattr(parent, "parent", parent)
                assert isinstance(parent, Deb822SourceEntry)
                for k in parent.section.tags:
                    new_entry.section[k] = parent.section[k]
            new_entry.types = [type]
            new_entry.uris = [uri]
            new_entry.suites = [dist]
            new_entry.comps = comps
            if architectures:
                new_entry.architectures = list(architectures)
            new_entry.section.header = comment
            new_entry.disabled = disabled
        else:
            # there isn't any matching source, so create a new line and parse it
            parts = [
                "#" if disabled else "",
                type,
                ("[arch=%s]" % ",".join(architectures)) if architectures else "",
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
        """remove the specified entry from the sources.list"""
        if isinstance(source_entry, ExplodedDeb822SourceEntry):
            source_entry.split_out()
            source_entry = source_entry.parent
        self.list.remove(source_entry)

    def load(self, file):
        """(re)load the current sources"""
        try:
            with salt.utils.files.fopen(file) as f:
                if file.endswith(".sources"):
                    for section in File(f):
                        self.list.append(Deb822SourceEntry(section, file, list=self))
                else:
                    for line in f:
                        source = SourceEntry(line, file)
                        self.list.append(source)
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning(f"could not parse source file '{file}': {exc}\n")

    def index(self, entry):
        if isinstance(entry, ExplodedDeb822SourceEntry):
            return self.list.index(entry.parent)
        return self.list.index(entry)

    def merge(self):
        """Merge consecutive entries that have been split back together."""
        merged = True
        while merged:
            i = 0
            merged = False
            while i + 1 < len(self.list):
                entry = self.list[i]
                if isinstance(entry, Deb822SourceEntry):
                    j = i + 1
                    while j < len(self.list):
                        if entry.merge(self.list[j]):
                            del self.list[j]
                            merged = True
                        else:
                            j += 1
                i += 1

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

        self.merge()
        files = {}
        for source in self.list:
            if source.file not in files:
                files[source.file] = []
            elif isinstance(source, Deb822SourceEntry):
                files[source.file].append("\n")
            files[source.file].append(source.str())
        for file in files:
            with salt.utils.files.fopen(file, "w") as f:
                f.write("".join(files[file]))

    def exploded_list(self):
        """Present an exploded view of the list where each entry corresponds exactly to a Release file.

        A release file is uniquely identified by the triplet (type, uri, suite). Old style entries
        always referred to a single release file, but deb822 entries allow multiple values for each
        of those fields.
        """
        res: list[AnyExplodedSourceEntry] = []
        for entry in self.list:
            if isinstance(entry, SourceEntry):
                res.append(entry)
            elif (
                len(entry.types) == 1
                and len(entry.uris) == 1
                and len(entry.suites) == 1
            ):
                res.append(entry)
            else:
                for typ in entry.types:
                    for uri in entry.uris:
                        for sui in entry.suites:
                            res.append(ExplodedDeb822SourceEntry(entry, typ, uri, sui))

        return res


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
    get_opts = re.search(r"\[(.*=.*)\]", line)
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

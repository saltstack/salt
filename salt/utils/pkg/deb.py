"""
Common functions for working with deb packages
"""

import logging
import os
import pathlib
import re
import shutil
import tempfile
from collections import OrderedDict

import salt.utils.files

log = logging.getLogger(__name__)


class SourceEntry:  # pylint: disable=function-redefined
    def __init__(self, line, file=None):
        self.invalid = False
        self.comps = []
        self.disabled = False
        self.comment = ""
        self.dist = ""
        self.type = ""
        self.uri = ""
        self.line = line
        self.architectures = []
        self.signedby = ""
        self.file = file
        if not self.file:
            self.file = str(pathlib.Path(os.sep, "etc", "apt", "sources.list"))
        self._parse_sources(line)

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


class SourcesList:  # pylint: disable=function-redefined
    def __init__(self):
        self.list = []
        self.files = [
            pathlib.Path(os.sep, "etc", "apt", "sources.list"),
            pathlib.Path(os.sep, "etc", "apt", "sources.list.d"),
        ]
        for file in self.files:
            if file.is_dir():
                for fp in file.glob("**/*.list"):
                    self.add_file(file=fp)
            else:
                self.add_file(file)

    def __iter__(self):
        yield from self.list

    def add_file(self, file):
        """
        Add the lines of a file to self.list
        """
        if file.is_file():
            with salt.utils.files.fopen(str(file)) as source:
                for line in source:
                    self.list.append(SourceEntry(line, file=str(file)))
        else:
            log.debug("The apt sources file %s does not exist", file)

    def add(self, type, uri, dist, orig_comps, architectures, signedby):
        opts_count = []
        opts_line = ""
        if architectures:
            architectures = f"arch={','.join(architectures)}"
            opts_count.append(architectures)
        if signedby:
            signedby = f"signed-by={signedby}"
            opts_count.append(signedby)
        if len(opts_count) > 1:
            opts_line = f"[{' '.join(opts_count)}]"
        elif len(opts_count) == 1:
            opts_line = f"[{''.join(opts_count)}]"
        repo_line = [
            type,
            opts_line,
            uri,
            dist,
            " ".join(orig_comps),
        ]
        return SourceEntry(" ".join([line for line in repo_line if line.strip()]))

    def remove(self, source):
        """
        remove a source from the list of sources
        """
        self.list.remove(source)

    def save(self):
        """
        write all of the sources from the list of sources
        to the file.
        """
        filemap = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            for source in self.list:
                fname = pathlib.Path(tmpdir, pathlib.Path(source.file).name)
                with salt.utils.files.fopen(str(fname), "a") as fp:
                    fp.write(source.repo_line())
                if source.file not in filemap:
                    filemap[source.file] = {"tmp": fname}

            for fp in filemap:
                shutil.move(str(filemap[fp]["tmp"]), fp)


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

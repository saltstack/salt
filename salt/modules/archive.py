"""
A module to wrap (non-Windows) archive calls

.. versionadded:: 2014.1.0
"""

import contextlib
import copy
import errno
import glob
import logging
import os
import re
import shlex
import stat
import subprocess
import tarfile
import urllib.parse
import zipfile

import salt.utils.decorators
import salt.utils.decorators.path
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.templates
from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    import rarfile

    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False


if salt.utils.platform.is_windows():
    import win32file

# TODO: Check that the passed arguments are correct

# Don't shadow built-in's.
__func_alias__ = {"zip_": "zip", "list_": "list"}

log = logging.getLogger(__name__)


def list_(
    name,
    archive_format=None,
    options=None,
    strip_components=None,
    clean=False,
    verbose=False,
    saltenv="base",
    source_hash=None,
    use_etag=False,
):
    """
    .. versionadded:: 2016.11.0
    .. versionchanged:: 2016.11.2,3005
        The rarfile_ Python module is now supported for listing the contents of
        rar archives. This is necessary on minions with older releases of the
        ``rar`` CLI tool, which do not support listing the contents in a
        parsable format.

    .. _rarfile: https://pypi.python.org/pypi/rarfile

    List the files and directories in an tar, zip, or rar archive.

    .. note::
        This function will only provide results for XZ-compressed archives if
        the xz_ CLI command is available, as Python does not at this time
        natively support XZ compression in its tarfile_ module. Keep in mind
        however that most Linux distros ship with xz_ already installed.

        To check if a given minion has xz_, the following Salt command can be
        run:

        .. code-block:: bash

            salt minion_id cmd.which xz

        If ``None`` is returned, then xz_ is not present and must be installed.
        It is widely available and should be packaged as either ``xz`` or
        ``xz-utils``.

    name
        Path/URL of archive

    archive_format
        Specify the format of the archive (``tar``, ``zip``, or ``rar``). If
        this argument is omitted, the archive format will be guessed based on
        the value of the ``name`` parameter.

    options
        **For tar archives only.** This function will, by default, try to use
        the tarfile_ module from the Python standard library to get a list of
        files/directories. If this method fails, then it will fall back to
        using the shell to decompress the archive to stdout and pipe the
        results to ``tar -tf -`` to produce a list of filenames. XZ-compressed
        archives are already supported automatically, but in the event that the
        tar archive uses a different sort of compression not supported natively
        by tarfile_, this option can be used to specify a command that will
        decompress the archive to stdout. For example:

        .. code-block:: bash

            salt minion_id archive.list /path/to/foo.tar.gz options='gzip --decompress --stdout'

        .. note::
            It is not necessary to manually specify options for gzip'ed
            archives, as gzip compression is natively supported by tarfile_.

    strip_components
        This argument specifies a number of top-level directories to strip from
        the results. This is similar to the paths that would be extracted if
        ``--strip-components`` (or ``--strip``) were used when extracting tar
        archives.

        .. versionadded:: 2016.11.2

    clean : False
        Set this value to ``True`` to delete the path referred to by ``name``
        once the contents have been listed. This option should be used with
        care.

        .. note::
            If there is an error listing the archive's contents, the cached
            file will not be removed, to allow for troubleshooting.

    verbose : False
        If ``False``, this function will return a list of files/dirs in the
        archive. If ``True``, it will return a dictionary categorizing the
        paths into separate keys containing the directory names, file names,
        and also directories/files present in the top level of the archive.

        .. versionchanged:: 2016.11.2
            This option now includes symlinks in their own list. Before, they
            were included with files.

    saltenv : base
        Specifies the fileserver environment from which to retrieve
        ``archive``. This is only applicable when ``archive`` is a file from
        the ``salt://`` fileserver.

    source_hash
        If ``name`` is an http(s)/ftp URL and the file exists in the minion's
        file cache, this option can be passed to keep the minion from
        re-downloading the archive if the cached copy matches the specified
        hash.

        .. versionadded:: 2018.3.0

    use_etag
        If ``True``, remote http/https file sources will attempt to use the
        ETag header to determine if the remote file needs to be downloaded.
        This provides a lightweight mechanism for promptly refreshing files
        changed on a web server without requiring a full hash comparison via
        the ``source_hash`` parameter.

        .. versionadded:: 3005

    .. _tarfile: https://docs.python.org/2/library/tarfile.html
    .. _xz: http://tukaani.org/xz/

    CLI Examples:

    .. code-block:: bash

            salt '*' archive.list /path/to/myfile.tar.gz
            salt '*' archive.list /path/to/myfile.tar.gz strip_components=1
            salt '*' archive.list salt://foo.tar.gz
            salt '*' archive.list https://domain.tld/myfile.zip
            salt '*' archive.list https://domain.tld/myfile.zip source_hash=f1d2d2f924e986ac86fdf7b36c94bcdf32beec15
            salt '*' archive.list ftp://10.1.2.3/foo.rar
    """

    def _list_tar(name, cached, decompress_cmd, failhard=False):
        """
        List the contents of a tar archive.
        """
        dirs = []
        files = []
        links = []
        try:
            open_kwargs = (
                {"name": cached}
                if not isinstance(cached, subprocess.Popen)
                else {"fileobj": cached.stdout, "mode": "r|"}
            )
            with contextlib.closing(tarfile.open(**open_kwargs)) as tar_archive:
                for member in tar_archive.getmembers():
                    _member = salt.utils.data.decode(member.name)
                    if member.issym():
                        links.append(_member)
                    elif member.isdir():
                        dirs.append(_member + "/")
                    else:
                        files.append(_member)
            return dirs, files, links

        except tarfile.ReadError:
            if failhard:
                if isinstance(cached, subprocess.Popen):
                    stderr = cached.communicate()[1]
                    if cached.returncode != 0:
                        raise CommandExecutionError(
                            "Failed to decompress {}".format(name),
                            info={"error": stderr},
                        )
            else:
                if not salt.utils.path.which("tar"):
                    raise CommandExecutionError("'tar' command not available")
                if decompress_cmd is not None and isinstance(decompress_cmd, str):
                    # Guard against shell injection
                    try:
                        decompress_cmd = [
                            shlex.quote(x) for x in shlex.split(decompress_cmd)
                        ]
                    except AttributeError:
                        raise CommandExecutionError("Invalid CLI options")
                else:
                    if (
                        salt.utils.path.which("xz")
                        and __salt__["cmd.retcode"](
                            ["xz", "-t", cached],
                            python_shell=False,
                            ignore_retcode=True,
                        )
                        == 0
                    ):
                        decompress_cmd = ["xz", "--decompress", "--stdout"]

                if decompress_cmd:
                    decompressed = subprocess.Popen(
                        decompress_cmd + [shlex.quote(cached)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    return _list_tar(name, decompressed, None, True)

        raise CommandExecutionError(
            "Unable to list contents of {}. If this is an XZ-compressed tar "
            "archive, install XZ Utils to enable listing its contents. If it "
            "is compressed using something other than XZ, it may be necessary "
            "to specify CLI options to decompress the archive. See the "
            "documentation for details.".format(name)
        )

    def _list_zip(name, cached):
        """
        List the contents of a zip archive.
        Password-protected ZIP archives can still be listed by zipfile, so
        there is no reason to invoke the unzip command.
        """
        dirs = set()
        files = []
        links = []
        try:
            with contextlib.closing(zipfile.ZipFile(cached)) as zip_archive:
                for member in zip_archive.infolist():
                    path = member.filename
                    if salt.utils.platform.is_windows():
                        if path.endswith("/"):
                            # zipfile.ZipInfo objects on windows use forward
                            # slash at end of the directory name.
                            dirs.add(path)
                        else:
                            files.append(path)
                    else:
                        mode = member.external_attr >> 16
                        if stat.S_ISLNK(mode):
                            links.append(path)
                        elif stat.S_ISDIR(mode):
                            dirs.add(path)
                        else:
                            files.append(path)

                _files = copy.deepcopy(files)
                for path in _files:
                    # ZIP files created on Windows do not add entries
                    # to the archive for directories. So, we'll need to
                    # manually add them.
                    dirname = "".join(path.rpartition("/")[:2])
                    if dirname:
                        dirs.add(dirname)
                        if dirname in files:
                            files.remove(dirname)
            return list(dirs), files, links
        except zipfile.BadZipfile:
            raise CommandExecutionError("{} is not a ZIP file".format(name))

    def _list_rar(name, cached):
        """
        List the contents of a rar archive.
        """
        dirs = []
        files = []
        if HAS_RARFILE:
            with rarfile.RarFile(cached) as rf:
                for member in rf.infolist():
                    path = member.filename.replace("\\", "/")
                    if member.isdir():
                        dirs.append(path + "/")
                    else:
                        files.append(path)
        else:
            if not salt.utils.path.which("rar"):
                raise CommandExecutionError(
                    "rar command not available, is it installed?"
                )
            output = __salt__["cmd.run"](
                ["rar", "lt", name], python_shell=False, ignore_retcode=False
            )
            matches = re.findall(r"Name:\s*([^\n]+)\s*Type:\s*([^\n]+)", output)
            for path, type_ in matches:
                if type_ == "Directory":
                    dirs.append(path + "/")
                else:
                    files.append(path)
            if not dirs and not files:
                raise CommandExecutionError(
                    "Failed to list {}, is it a rar file? If so, the "
                    "installed version of rar may be too old to list data in "
                    "a parsable format. Installing the rarfile Python module "
                    "may be an easier workaround if newer rar is not readily "
                    "available.".format(name),
                    info={"error": output},
                )
        return dirs, files, []

    cached = __salt__["cp.cache_file"](
        name, saltenv, source_hash=source_hash, use_etag=use_etag
    )
    if not cached:
        raise CommandExecutionError("Failed to cache {}".format(name))

    try:
        if strip_components:
            try:
                int(strip_components)
            except ValueError:
                strip_components = -1

            if strip_components <= 0:
                raise CommandExecutionError(
                    "'strip_components' must be a positive integer"
                )

        parsed = urllib.parse.urlparse(name)
        path = parsed.path or parsed.netloc

        def _unsupported_format(archive_format):
            """
            Raise the proper exception message for the given archive format.
            """
            if archive_format is None:
                raise CommandExecutionError(
                    "Unable to guess archive format, please pass an "
                    "'archive_format' argument."
                )
            raise CommandExecutionError(
                "Unsupported archive format '{}'".format(archive_format)
            )

        if not archive_format:
            guessed_format = salt.utils.files.guess_archive_type(path)
            if guessed_format is None:
                _unsupported_format(archive_format)
            archive_format = guessed_format

        func = locals().get("_list_" + archive_format)
        if not hasattr(func, "__call__"):
            _unsupported_format(archive_format)

        args = (options,) if archive_format == "tar" else ()
        try:
            dirs, files, links = func(name, cached, *args)
        except OSError as exc:
            raise CommandExecutionError(
                "Failed to list contents of {}: {}".format(name, exc.__str__())
            )
        except CommandExecutionError as exc:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandExecutionError(
                "Uncaught exception '{}' when listing contents of {}".format(exc, name)
            )

        if clean:
            try:
                os.remove(cached)
                log.debug("Cleaned cached archive %s", cached)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    log.warning(
                        "Failed to clean cached archive %s: %s", cached, exc.__str__()
                    )

        if strip_components:
            for item in (dirs, files, links):
                for index, path in enumerate(item):
                    try:
                        # Strip off the specified number of directory
                        # boundaries, and grab what comes after the last
                        # stripped path separator.
                        item[index] = item[index].split(os.sep, strip_components)[
                            strip_components
                        ]
                    except IndexError:
                        # Path is excluded by strip_components because it is not
                        # deep enough. Set this to an empty string so it can
                        # be removed in the generator expression below.
                        item[index] = ""

                # Remove all paths which were excluded
                item[:] = (x for x in item if x)
                item.sort()

        if verbose:
            ret = {
                "dirs": sorted(salt.utils.data.decode_list(dirs)),
                "files": sorted(salt.utils.data.decode_list(files)),
                "links": sorted(salt.utils.data.decode_list(links)),
            }
            top_level_dirs = [x for x in ret["dirs"] if x.count("/") == 1]
            # the common_prefix logic handles scenarios where the TLD
            # isn't listed as an archive member on its own
            common_prefix = os.path.commonprefix(ret["dirs"])
            if "/" in common_prefix:
                common_prefix = common_prefix.split("/")[0] + "/"
                if common_prefix not in top_level_dirs:
                    top_level_dirs.append(common_prefix)
            ret["top_level_dirs"] = top_level_dirs
            ret["top_level_files"] = [x for x in ret["files"] if x.count("/") == 0]
            ret["top_level_links"] = [x for x in ret["links"] if x.count("/") == 0]
        else:
            ret = sorted(dirs + files + links)
        return ret

    except CommandExecutionError as exc:
        # Reraise with cache path in the error so that the user can examine the
        # cached archive for troubleshooting purposes.
        info = exc.info or {}
        info["archive location"] = cached
        raise CommandExecutionError(exc.error, info=info)


_glob_wildcards = re.compile("[*?[]")


def _glob(pathname):
    """
    In case ``pathname`` contains glob wildcards, performs expansion and returns
    the possibly empty list of matching pathnames. Otherwise returns a list that
    contains only ``pathname`` itself.
    """
    if _glob_wildcards.search(pathname) is None:
        return [pathname]
    else:
        return glob.glob(pathname)


def _expand_sources(sources):
    """
    Expands a user-provided specification of source files into a list of paths.
    """
    if sources is None:
        return []
    if isinstance(sources, str):
        sources = [x.strip() for x in sources.split(",")]
    elif isinstance(sources, (float, int)):
        sources = [str(sources)]
    return [path for source in sources for path in _glob(source)]


@salt.utils.decorators.path.which("tar")
def tar(options, tarfile, sources=None, dest=None, cwd=None, template=None, runas=None):
    """
    .. note::

        This function has changed for version 0.17.0. In prior versions, the
        ``cwd`` and ``template`` arguments must be specified, with the source
        directories/files coming as a space-separated list at the end of the
        command. Beginning with 0.17.0, ``sources`` must be a comma-separated
        list, and the ``cwd`` and ``template`` arguments are optional.

    Uses the tar command to pack, unpack, etc. tar files


    options
        Options to pass to the tar command

        .. versionchanged:: 2015.8.0

            The mandatory `-` prefixing has been removed.  An options string
            beginning with a `--long-option`, would have uncharacteristically
            needed its first `-` removed under the former scheme.

            Also, tar will parse its options differently if short options are
            used with or without a preceding `-`, so it is better to not
            confuse the user into thinking they're using the non-`-` format,
            when really they are using the with-`-` format.

    tarfile
        The filename of the tar archive to pack/unpack

    sources
        Comma delimited list of files to **pack** into the tarfile. Can also be
        passed as a Python list.

        .. versionchanged:: 2017.7.0
            Globbing is now supported for this argument

    dest
        The destination directory into which to **unpack** the tarfile

    cwd : None
        The directory in which the tar command should be executed. If not
        specified, will default to the home directory of the user under which
        the salt minion process is running.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.tar cjvf /tmp/salt.tar.bz2 {{grains.saltpath}} template=jinja

    CLI Examples:

    .. code-block:: bash

        # Create a tarfile
        salt '*' archive.tar cjvf /tmp/tarfile.tar.bz2 /tmp/file_1,/tmp/file_2
        # Create a tarfile using globbing (2017.7.0 and later)
        salt '*' archive.tar cjvf /tmp/tarfile.tar.bz2 '/tmp/file_*'
        # Unpack a tarfile
        salt '*' archive.tar xf foo.tar dest=/target/directory
    """
    if not options:
        # Catch instances were people pass an empty string for the "options"
        # argument. Someone would have to be really silly to do this, but we
        # should at least let them know of their silliness.
        raise SaltInvocationError("Tar options can not be empty")

    cmd = ["tar"]
    if options:
        cmd.extend(options.split())

    cmd.extend(["{}".format(tarfile)])
    cmd.extend(_expand_sources(sources))
    if dest:
        cmd.extend(["-C", "{}".format(dest)])

    return __salt__["cmd.run"](
        cmd, cwd=cwd, template=template, runas=runas, python_shell=False
    ).splitlines()


@salt.utils.decorators.path.which("gzip")
def gzip(sourcefile, template=None, runas=None, options=None):
    """
    Uses the gzip command to create gzip files

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.gzip template=jinja /tmp/{{grains.id}}.txt

    runas : None
        The user with which to run the gzip command line

    options : None
        Pass any additional arguments to gzip

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        # Create /tmp/sourcefile.txt.gz
        salt '*' archive.gzip /tmp/sourcefile.txt
        salt '*' archive.gzip /tmp/sourcefile.txt options='-9 --verbose'
    """
    cmd = ["gzip"]
    if options:
        cmd.append(options)
    cmd.append("{}".format(sourcefile))

    return __salt__["cmd.run"](
        cmd, template=template, runas=runas, python_shell=False
    ).splitlines()


@salt.utils.decorators.path.which("gunzip")
def gunzip(gzipfile, template=None, runas=None, options=None):
    """
    Uses the gunzip command to unpack gzip files

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.gunzip template=jinja /tmp/{{grains.id}}.txt.gz

    runas : None
        The user with which to run the gzip command line

    options : None
        Pass any additional arguments to gzip

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        # Create /tmp/sourcefile.txt
        salt '*' archive.gunzip /tmp/sourcefile.txt.gz
        salt '*' archive.gunzip /tmp/sourcefile.txt options='--verbose'
    """
    cmd = ["gunzip"]
    if options:
        cmd.append(options)
    cmd.append("{}".format(gzipfile))

    return __salt__["cmd.run"](
        cmd, template=template, runas=runas, python_shell=False
    ).splitlines()


@salt.utils.decorators.path.which("zip")
def cmd_zip(zip_file, sources, template=None, cwd=None, runas=None):
    """
    .. versionadded:: 2015.5.0
        In versions 2014.7.x and earlier, this function was known as
        ``archive.zip``.

    Uses the ``zip`` command to create zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``zip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zip_file
        Path of zip file to be created

    sources
        Comma-separated list of sources to include in the zip file. Sources can
        also be passed in a Python list.

        .. versionchanged:: 2017.7.0
            Globbing is now supported for this argument

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.cmd_zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    cwd : None
        Use this argument along with relative paths in ``sources`` to create
        zip files which do not contain the leading directories. If not
        specified, the zip file will be created as if the cwd was ``/``, and
        creating a zip file of ``/foo/bar/baz.txt`` will contain the parent
        directories ``foo`` and ``bar``. To create a zip file containing just
        ``baz.txt``, the following command would be used:

        .. code-block:: bash

            salt '*' archive.cmd_zip /tmp/baz.zip baz.txt cwd=/foo/bar

        .. versionadded:: 2014.7.1

    runas : None
        Create the zip file as the specified user. Defaults to the user under
        which the minion is running.

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' archive.cmd_zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
        # Globbing for sources (2017.7.0 and later)
        salt '*' archive.cmd_zip /tmp/zipfile.zip '/tmp/sourcefile*'
    """
    cmd = ["zip", "-r"]
    cmd.append("{}".format(zip_file))
    cmd.extend(_expand_sources(sources))
    return __salt__["cmd.run"](
        cmd, cwd=cwd, template=template, runas=runas, python_shell=False
    ).splitlines()


@salt.utils.decorators.depends("zipfile", fallback_function=cmd_zip)
def zip_(zip_file, sources, template=None, cwd=None, runas=None, zip64=False):
    """
    Uses the ``zipfile`` Python module to create zip files

    .. versionchanged:: 2015.5.0
        This function was rewritten to use Python's native zip file support.
        The old functionality has been preserved in the new function
        :mod:`archive.cmd_zip <salt.modules.archive.cmd_zip>`. For versions
        2014.7.x and earlier, see the :mod:`archive.cmd_zip
        <salt.modules.archive.cmd_zip>` documentation.

    zip_file
        Path of zip file to be created

    sources
        Comma-separated list of sources to include in the zip file. Sources can
        also be passed in a Python list.

        .. versionchanged:: 2017.7.0
            Globbing is now supported for this argument

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    cwd : None
        Use this argument along with relative paths in ``sources`` to create
        zip files which do not contain the leading directories. If not
        specified, the zip file will be created as if the cwd was ``/``, and
        creating a zip file of ``/foo/bar/baz.txt`` will contain the parent
        directories ``foo`` and ``bar``. To create a zip file containing just
        ``baz.txt``, the following command would be used:

        .. code-block:: bash

            salt '*' archive.zip /tmp/baz.zip baz.txt cwd=/foo/bar

    runas : None
        Create the zip file as the specified user. Defaults to the user under
        which the minion is running.

    zip64 : False
        Used to enable ZIP64 support, necessary to create archives larger than
        4 GByte in size.
        If true, will create ZIP file with the ZIPp64 extension when the zipfile
        is larger than 2 GB.
        ZIP64 extension is disabled by default in the Python native zip support
        because the default zip and unzip commands on Unix (the InfoZIP utilities)
        don't support these extensions.

    CLI Example:

    .. code-block:: bash

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
        # Globbing for sources (2017.7.0 and later)
        salt '*' archive.zip /tmp/zipfile.zip '/tmp/sourcefile*'
    """
    if runas:
        euid = os.geteuid()
        egid = os.getegid()
        uinfo = __salt__["user.info"](runas)
        if not uinfo:
            raise SaltInvocationError("User '{}' does not exist".format(runas))

    zip_file, sources = _render_filenames(zip_file, sources, None, template)
    sources = _expand_sources(sources)

    if not cwd:
        for src in sources:
            if not os.path.isabs(src):
                raise SaltInvocationError("Relative paths require the 'cwd' parameter")
    else:
        err_msg = "cwd must be absolute"
        try:
            if not os.path.isabs(cwd):
                raise SaltInvocationError(err_msg)
        except AttributeError:
            raise SaltInvocationError(err_msg)

    if runas and (euid != uinfo["uid"] or egid != uinfo["gid"]):
        # Change the egid first, as changing it after the euid will fail
        # if the runas user is non-privileged.
        os.setegid(uinfo["gid"])
        os.seteuid(uinfo["uid"])

    try:
        exc = None
        archived_files = []
        with contextlib.closing(
            zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED, zip64)
        ) as zfile:
            for src in sources:
                if cwd:
                    src = os.path.join(cwd, src)
                if os.path.exists(src):
                    if os.path.isabs(src):
                        rel_root = "/"
                    else:
                        rel_root = cwd if cwd is not None else "/"
                    if os.path.isdir(src):
                        for dir_name, sub_dirs, files in salt.utils.path.os_walk(src):
                            if cwd and dir_name.startswith(cwd):
                                arc_dir = os.path.relpath(dir_name, cwd)
                            else:
                                arc_dir = os.path.relpath(dir_name, rel_root)
                            if arc_dir:
                                archived_files.append(arc_dir + "/")
                                zfile.write(dir_name, arc_dir)
                            for filename in files:
                                abs_name = os.path.join(dir_name, filename)
                                arc_name = os.path.join(arc_dir, filename)
                                archived_files.append(arc_name)
                                zfile.write(abs_name, arc_name)
                    else:
                        if cwd and src.startswith(cwd):
                            arc_name = os.path.relpath(src, cwd)
                        else:
                            arc_name = os.path.relpath(src, rel_root)
                        archived_files.append(arc_name)
                        zfile.write(src, arc_name)
    except Exception as exc:  # pylint: disable=broad-except
        pass
    finally:
        # Restore the euid/egid
        if runas:
            os.seteuid(euid)
            os.setegid(egid)
        if exc is not None:
            # Wait to raise the exception until euid/egid are restored to avoid
            # permission errors in writing to minion log.
            if exc == zipfile.LargeZipFile:
                raise CommandExecutionError(
                    "Resulting zip file too large, would require ZIP64 support"
                    "which has not been enabled. Rerun command with zip64=True"
                )
            else:
                raise CommandExecutionError(
                    "Exception encountered creating zipfile: {}".format(exc)
                )

    return archived_files


@salt.utils.decorators.path.which("unzip")
def cmd_unzip(
    zip_file,
    dest,
    excludes=None,
    options=None,
    template=None,
    runas=None,
    trim_output=False,
    password=None,
):
    """
    .. versionadded:: 2015.5.0
        In versions 2014.7.x and earlier, this function was known as
        ``archive.unzip``.

    Uses the ``unzip`` command to unpack zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``unzip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zip_file
        Path of zip file to be unpacked

    dest
        The destination directory into which the file should be unpacked

    excludes : None
        Comma-separated list of files not to unpack. Can also be passed in a
        Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.cmd_unzip template=jinja /tmp/zipfile.zip '/tmp/{{grains.id}}' excludes=file_1,file_2

    options
        Optional when using ``zip`` archives, ignored when usign other archives
        files. This is mostly used to overwrite existing files with ``o``.
        This options are only used when ``unzip`` binary is used.

        .. versionadded:: 2016.3.1

    runas : None
        Unpack the zip file as the specified user. Defaults to the user under
        which the minion is running.

        .. versionadded:: 2015.5.0

    trim_output : False
        The number of files we should output on success before the rest are trimmed, if this is
        set to True then it will default to 100

    password
        Password to use with password protected zip files

        .. note::
            This is not considered secure. It is recommended to instead use
            :py:func:`archive.unzip <salt.modules.archive.unzip>` for
            password-protected ZIP files. If a password is used here, then the
            unzip command run to extract the ZIP file will not show up in the
            minion log like most shell commands Salt runs do. However, the
            password will still be present in the events logged to the minion
            log at the ``debug`` log level. If the minion is logging at
            ``debug`` (or more verbose), then be advised that the password will
            appear in the log.

        .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' archive.cmd_unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2
    """
    if isinstance(excludes, str):
        excludes = [x.strip() for x in excludes.split(",")]
    elif isinstance(excludes, (float, int)):
        excludes = [str(excludes)]

    cmd = ["unzip"]
    if password:
        cmd.extend(["-P", password])
    if options:
        cmd.extend(shlex.split(options))
    cmd.extend(["{}".format(zip_file), "-d", "{}".format(dest)])

    if excludes is not None:
        cmd.append("-x")
        cmd.extend(excludes)

    result = __salt__["cmd.run_all"](
        cmd,
        template=template,
        runas=runas,
        python_shell=False,
        redirect_stderr=True,
        output_loglevel="quiet" if password else "debug",
    )

    if result["retcode"] != 0:
        raise CommandExecutionError(result["stdout"])

    return _trim_files(result["stdout"].splitlines(), trim_output)


def unzip(
    zip_file,
    dest,
    excludes=None,
    options=None,
    template=None,
    runas=None,
    trim_output=False,
    password=None,
    extract_perms=True,
):
    """
    Uses the ``zipfile`` Python module to unpack zip files

    .. versionchanged:: 2015.5.0
        This function was rewritten to use Python's native zip file support.
        The old functionality has been preserved in the new function
        :mod:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`. For versions
        2014.7.x and earlier, see the :mod:`archive.cmd_zip
        <salt.modules.archive.cmd_zip>` documentation.

    zip_file
        Path of zip file to be unpacked

    dest
        The destination directory into which the file should be unpacked

    excludes : None
        Comma-separated list of files not to unpack. Can also be passed in a
        Python list.

    options
        This options are only used when ``unzip`` binary is used. In this
        function is ignored.

        .. versionadded:: 2016.3.1

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.unzip template=jinja /tmp/zipfile.zip /tmp/{{grains.id}}/ excludes=file_1,file_2

    runas : None
        Unpack the zip file as the specified user. Defaults to the user under
        which the minion is running.

    trim_output : False
        The number of files we should output on success before the rest are trimmed, if this is
        set to True then it will default to 100

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2

    password
        Password to use with password protected zip files

        .. note::
            The password will be present in the events logged to the minion log
            file at the ``debug`` log level. If the minion is logging at
            ``debug`` (or more verbose), then be advised that the password will
            appear in the log.

        .. versionadded:: 2016.3.0

    extract_perms : True
        The Python zipfile_ module does not extract file/directory attributes
        by default. When this argument is set to ``True``, Salt will attempt to
        apply the file permission attributes to the extracted files/folders.

        On Windows, only the read-only flag will be extracted as set within the
        zip file, other attributes (i.e. user/group permissions) are ignored.

        Set this argument to ``False`` to disable this behavior.

        .. versionadded:: 2016.11.0

    .. _zipfile: https://docs.python.org/2/library/zipfile.html

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ password='BadPassword'
    """
    if not excludes:
        excludes = []
    if runas:
        euid = os.geteuid()
        egid = os.getegid()
        uinfo = __salt__["user.info"](runas)
        if not uinfo:
            raise SaltInvocationError("User '{}' does not exist".format(runas))

    zip_file, dest = _render_filenames(zip_file, dest, None, template)

    if runas and (euid != uinfo["uid"] or egid != uinfo["gid"]):
        # Change the egid first, as changing it after the euid will fail
        # if the runas user is non-privileged.
        os.setegid(uinfo["gid"])
        os.seteuid(uinfo["uid"])

    try:
        # Define cleaned_files here so that an exception will not prevent this
        # variable from being defined and cause a NameError in the return
        # statement at the end of the function.
        cleaned_files = []
        with contextlib.closing(zipfile.ZipFile(zip_file, "r")) as zfile:
            files = zfile.namelist()

            if isinstance(excludes, str):
                excludes = [x.strip() for x in excludes.split(",")]
            elif isinstance(excludes, (float, int)):
                excludes = [str(excludes)]

            cleaned_files.extend([x for x in files if x not in excludes])
            for target in cleaned_files:
                if target not in excludes:
                    if salt.utils.platform.is_windows() is False:
                        info = zfile.getinfo(target)
                        # Check if zipped file is a symbolic link
                        if stat.S_ISLNK(info.external_attr >> 16):
                            source = zfile.read(target)
                            os.symlink(source, os.path.join(dest, target))
                            continue
                    # file.extract is expecting the password to be a bytestring
                    if password:
                        if isinstance(password, int):
                            password = str(password)
                        if isinstance(password, str):
                            password = password.encode()
                    zfile.extract(target, dest, password)
                    if extract_perms:
                        if not salt.utils.platform.is_windows():
                            perm = zfile.getinfo(target).external_attr >> 16
                            if perm == 0:
                                umask_ = salt.utils.files.get_umask()
                                if target.endswith("/"):
                                    perm = 0o777 & ~umask_
                                else:
                                    perm = 0o666 & ~umask_
                            os.chmod(os.path.join(dest, target), perm)
                        else:
                            win32_attr = zfile.getinfo(target).external_attr & 0xFF
                            win32file.SetFileAttributes(
                                os.path.join(dest, target), win32_attr
                            )
    except Exception as exc:  # pylint: disable=broad-except
        if runas:
            os.seteuid(euid)
            os.setegid(egid)
        # Wait to raise the exception until euid/egid are restored to avoid
        # permission errors in writing to minion log.
        raise CommandExecutionError(
            "Exception encountered unpacking zipfile: {}".format(exc)
        )
    finally:
        # Restore the euid/egid
        if runas:
            os.seteuid(euid)
            os.setegid(egid)

    return _trim_files(cleaned_files, trim_output)


def is_encrypted(name, clean=False, saltenv="base", source_hash=None, use_etag=False):
    """
    .. versionadded:: 2016.11.0
    .. versionchanged:: 3005

    Returns ``True`` if the zip archive is password-protected, ``False`` if
    not. If the specified file is not a ZIP archive, an error will be raised.

    name
        The path / URL of the archive to check.

    clean : False
        Set this value to ``True`` to delete the path referred to by ``name``
        once the contents have been listed. This option should be used with
        care.

        .. note::
            If there is an error listing the archive's contents, the cached
            file will not be removed, to allow for troubleshooting.

    saltenv : base
        Specifies the fileserver environment from which to retrieve
        ``archive``. This is only applicable when ``archive`` is a file from
        the ``salt://`` fileserver.

    source_hash
        If ``name`` is an http(s)/ftp URL and the file exists in the minion's
        file cache, this option can be passed to keep the minion from
        re-downloading the archive if the cached copy matches the specified
        hash.

        .. versionadded:: 2018.3.0

    use_etag
        If ``True``, remote http/https file sources will attempt to use the
        ETag header to determine if the remote file needs to be downloaded.
        This provides a lightweight mechanism for promptly refreshing files
        changed on a web server without requiring a full hash comparison via
        the ``source_hash`` parameter.

        .. versionadded:: 3005

    CLI Examples:

    .. code-block:: bash

            salt '*' archive.is_encrypted /path/to/myfile.zip
            salt '*' archive.is_encrypted salt://foo.zip
            salt '*' archive.is_encrypted salt://foo.zip saltenv=dev
            salt '*' archive.is_encrypted https://domain.tld/myfile.zip clean=True
            salt '*' archive.is_encrypted https://domain.tld/myfile.zip source_hash=f1d2d2f924e986ac86fdf7b36c94bcdf32beec15
            salt '*' archive.is_encrypted ftp://10.1.2.3/foo.zip
    """
    cached = __salt__["cp.cache_file"](
        name, saltenv, source_hash=source_hash, use_etag=use_etag
    )
    if not cached:
        raise CommandExecutionError("Failed to cache {}".format(name))

    archive_info = {"archive location": cached}
    try:
        with contextlib.closing(zipfile.ZipFile(cached)) as zip_archive:
            zip_archive.testzip()
    except RuntimeError:
        ret = True
    except zipfile.BadZipfile:
        raise CommandExecutionError(
            "{} is not a ZIP file".format(name), info=archive_info
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise CommandExecutionError(exc.__str__(), info=archive_info)
    else:
        ret = False

    if clean:
        try:
            os.remove(cached)
            log.debug("Cleaned cached archive %s", cached)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                log.warning(
                    "Failed to clean cached archive %s: %s", cached, exc.__str__()
                )
    return ret


@salt.utils.decorators.path.which("rar")
def rar(rarfile, sources, template=None, cwd=None, runas=None):
    """
    Uses `rar for Linux`_ to create rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Path of rar file to be created

    sources
        Comma-separated list of sources to include in the rar file. Sources can
        also be passed in a Python list.

        .. versionchanged:: 2017.7.0
            Globbing is now supported for this argument

    cwd : None
        Run the rar command from the specified directory. Use this argument
        along with relative file paths to create rar files which do not
        contain the leading directories. If not specified, this will default
        to the home directory of the user under which the salt minion process
        is running.

        .. versionadded:: 2014.7.1

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.rar template=jinja /tmp/rarfile.rar '/tmp/sourcefile1,/tmp/{{grains.id}}.txt'

    CLI Example:

    .. code-block:: bash

        salt '*' archive.rar /tmp/rarfile.rar /tmp/sourcefile1,/tmp/sourcefile2
        # Globbing for sources (2017.7.0 and later)
        salt '*' archive.rar /tmp/rarfile.rar '/tmp/sourcefile*'
    """
    cmd = ["rar", "a", "-idp", "{}".format(rarfile)]
    cmd.extend(_expand_sources(sources))
    return __salt__["cmd.run"](
        cmd, cwd=cwd, template=template, runas=runas, python_shell=False
    ).splitlines()


@salt.utils.decorators.path.which_bin(("unrar", "rar"))
def unrar(rarfile, dest, excludes=None, template=None, runas=None, trim_output=False):
    """
    Uses `rar for Linux`_ to unpack rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Name of rar file to be unpacked

    dest
        The destination directory into which to **unpack** the rar file

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.unrar template=jinja /tmp/rarfile.rar /tmp/{{grains.id}}/ excludes=file_1,file_2

    trim_output : False
        The number of files we should output on success before the rest are trimmed, if this is
        set to True then it will default to 100

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unrar /tmp/rarfile.rar /home/strongbad/ excludes=file_1,file_2

    """
    if isinstance(excludes, str):
        excludes = [entry.strip() for entry in excludes.split(",")]

    cmd = [
        salt.utils.path.which_bin(("unrar", "rar")),
        "x",
        "-idp",
        "{}".format(rarfile),
    ]
    if excludes is not None:
        for exclude in excludes:
            cmd.extend(["-x", "{}".format(exclude)])
    cmd.append("{}".format(dest))
    files = __salt__["cmd.run"](
        cmd, template=template, runas=runas, python_shell=False
    ).splitlines()

    return _trim_files(files, trim_output)


def _render_filenames(filenames, zip_file, saltenv, template):
    """
    Process markup in the :param:`filenames` and :param:`zipfile` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    """
    if not template:
        return (filenames, zip_file)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            "Attempted to render file paths with unavailable engine {}".format(template)
        )

    kwargs = {}
    kwargs["salt"] = __salt__
    kwargs["pillar"] = __pillar__
    kwargs["grains"] = __grains__
    kwargs["opts"] = __opts__
    kwargs["saltenv"] = saltenv

    def _render(contents):
        """
        Render :param:`contents` into a literal pathname by writing it to a
        temp file, rendering that file, and returning the result.
        """
        # write out path to temp file
        tmp_path_fn = salt.utils.files.mkstemp()
        with salt.utils.files.fopen(tmp_path_fn, "w+") as fp_:
            fp_.write(salt.utils.stringutils.to_str(contents))
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn, to_str=True, **kwargs
        )
        salt.utils.files.safe_rm(tmp_path_fn)
        if not data["result"]:
            # Failed to render the template
            raise CommandExecutionError(
                "Failed to render file path with error: {}".format(data["data"])
            )
        else:
            return data["data"]

    filenames = _render(filenames)
    zip_file = _render(zip_file)
    return (filenames, zip_file)


def _trim_files(files, trim_output):
    """
    Trim the file list for output.
    """
    count = 100
    if not isinstance(trim_output, bool):
        count = trim_output

    if (
        not (isinstance(trim_output, bool) and trim_output is False)
        and len(files) > count
    ):
        files = files[:count]
        files.append("List trimmed after {} files.".format(count))

    return files

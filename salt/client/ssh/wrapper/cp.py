"""
Wrap the ``cp`` module allowing for managed SSH file transfers.

This module works by keeping a cachedir per SSH minion on the master.
Requested files are first cached there and afterwards replicated to
the minion using ``scp``. The returned paths will point to files in
the remote cachedir. You can convert these paths to the local ones
by calling ``cp.convert_cache_path``, which is a function unique
to the wrapper.

.. note::

    This wrapper currently has several limitations:

    * Replication will always be performed, even if the file exists
      in the minion cache dir in the correct state (no hash checks).
    * Even non-``salt://`` URIs will be fetched by the master node
      first in order for other wrappers to be able to employ this
      one for fetching remotes.
    * When replicating directories, they are currently not sent as
      a tar archive, but file per file, which is very inefficient.
    * You cannot transfer files from the minion to the master-side
      SSH minion cache, they will only be available on the remote.

.. note::
    For backwards-compatibility reasons, this wrapper currently does
    not behave the same as the execution module regarding ``saltenv``.
    The parameter defaults to ``base``, regardless of the current
    value of the minion setting.
"""

import logging
import os
import shlex
import urllib.parse
from pathlib import Path

import salt.client.ssh
import salt.fileclient
import salt.utils.files
import salt.utils.stringutils
import salt.utils.templates
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _client():
    ckey = "_cp_shell"
    if ckey not in __context__:
        # Don't recreate the shell each time, the connection is closed
        # automatically after a command is sent.
        single = salt.client.ssh.Single(__opts__, "", **__salt__.kwargs)
        __context__[ckey] = single.shell
    return SSHCpClient(
        __context__["fileclient"].opts, __context__[ckey], __salt__.kwargs["id_"]
    )


def get_file(path, dest, saltenv="base", makedirs=False, template=None, **kwargs):
    """
    Send a file from the fileserver to the specified location.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.get_file salt://path/to/file /minion/dest

    path
        The path on the fileserver, like ``salt://foo/bar.conf``. It is possible
        to specify the ``saltenv`` using the querystring syntax:
        ``salt://foo/bar.conf?saltenv=config``

    dest
        The absolute path to transfer the file to on the minion. If empty,
        the file will be cached in the minion's cache dir, under
        ``files/<saltenv>/<path>``.

    saltenv
        Salt fileserver environment from which to retrieve the file.
        Defaults to ``base``.

    makedirs
        Whether to create the parent directories for ``dest`` as needed.
        Defaults to false.

    template
        If ``path`` and ``dest`` parameters should be interpreted as templates,
        the name of the renderer to use.

        Template rendering can be enabled on both ``path`` and
        ``dest`` file paths like so:

        .. code-block:: bash

            salt-ssh '*' cp.get_file "salt://{{grains.os}}/vimrc" /etc/vimrc template=jinja

    Additional keyword arguments are passed through to the renderer, otherwise discarded.

    .. note::

        It may be necessary to quote the URL when using the querystring method,
        depending on the shell being used to run the command.

    .. note::

        gzip compression is not supported in the salt-ssh version of
        ``cp.get_file``.
    """
    gzip = kwargs.pop("gzip", None)
    if gzip is not None:
        log.warning("The gzip argument to cp.get_file in salt-ssh is unsupported")

    (path, dest) = _render_filenames(path, dest, saltenv, template, **kwargs)

    path, senv = salt.utils.url.split_env(path)
    if senv:
        saltenv = senv

    if not hash_file(path, saltenv):
        return ""
    else:
        with _client() as client:
            ret = client.get_file(path, dest, makedirs, saltenv)
            if not ret:
                return ret
            # Return the cache path on the minion, not the local one
            return client.target_map[ret]


def envs():
    """
    List available fileserver environments.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.envs
    """
    return __context__["fileclient"].envs()


def get_template(
    path, dest, template="jinja", saltenv="base", makedirs=False, **kwargs
):
    """
    Render a file as a template before writing it.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_template salt://path/to/template /minion/dest

    path
        The path on the fileserver, like ``salt://foo/bar.conf``. It is possible
        to specify the ``saltenv`` using the querystring syntax:
        ``salt://foo/bar.conf?saltenv=config``

    dest
        The absolute path to transfer the file to on the minion. If empty,
        the rendered template will be cached in the minion's cache dir,
        under ``extrn_files/<saltenv>/<path>``.

    template
        The renderer to use for rendering the template. Defaults to ``jinja``.

    saltenv
        The saltenv the template should be pulled from. Defaults to ``base``.

    makedirs
        Whether to create the parent directories for ``dest`` as needed.
        Defaults to false.

    Additional keyword arguments are passed verbatim to the renderer.
    """
    if "salt" not in kwargs:
        kwargs["salt"] = __salt__.value()
    if "pillar" not in kwargs:
        kwargs["pillar"] = __pillar__.value()
    if "grains" not in kwargs:
        kwargs["grains"] = __grains__.value()
    if "opts" not in kwargs:
        kwargs["opts"] = __opts__

    with _client() as client:
        ret = client.get_template(path, dest, template, makedirs, saltenv, **kwargs)
        if not ret:
            return ret
        # Return the cache path on the minion, not the local one
        return client.target_map[ret]


def get_dir(path, dest, saltenv="base", template=None, **kwargs):
    """
    Recursively transfer a directory from the fileserver to the minion.

    .. note::

        This can take a long time since each file is transferred separately
        currently.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.get_dir salt://path/to/dir/ /minion/dest

    path
        The path on the fileserver, like ``salt://foo/bar/``. It is possible
        to specify the ``saltenv`` using the querystring syntax:
        ``salt://foo/bar?saltenv=config``

    dest
        The absolute path to transfer the directory to on the minion. If empty,
        the directory will be cached in the minion's cache dir, under
        ``files/<saltenv>/<path>``. Note that parent directories will
        be created as required automatically.

    saltenv
        Salt fileserver environment from which to retrieve the directory.
        Defaults to ``base``.

    template
        If ``path`` and ``dest`` parameters should be interpreted as templates,
        the name of the renderer to use.

    .. note::

        gzip compression is not supported in the salt-ssh version of
        cp.get_dir. The argument is only accepted for interface compatibility.
    """
    # FIXME: transfer dirs using tar
    gzip = kwargs.pop("gzip", None)
    if gzip is not None:
        log.warning("The gzip argument to cp.get_dir in salt-ssh is unsupported")
    (path, dest) = _render_filenames(path, dest, saltenv, template, **kwargs)

    with _client() as client:
        ret = client.get_dir(path, dest, saltenv, gzip)
        if not ret:
            return ret
        # Return the cache path on the minion, not the local one
        return [client.target_map[x] for x in ret]


def get_url(path, dest="", saltenv="base", makedirs=False, source_hash=None):
    """
    Retrieve a single file from a URL.

    path
        A URL to download a file from. Supported URL schemes are: ``salt://``,
        ``http://``, ``https://``, ``ftp://``, ``s3://``, ``swift://`` and
        ``file://`` (local filesystem). If no scheme was specified, this is
        equivalent of using ``file://``.
        If a ``file://`` URL is given, the function just returns absolute path
        to that file on a local filesystem.
        The function returns ``False`` if Salt was unable to fetch a file from
        a ``salt://`` URL.

        .. note::

            The file:// scheme is currently only partially supported in salt-ssh.
            It behaves the same as the unwrapped ``cp.get_url`` if dest is not
            ``None``, but returning its contents will fail. Use ``get_file_str``
            as a workaround for text files.

    dest
        The destination to write the cached file to. If empty, will cache the file
        in the minion's cache dir under ``extrn_files/<saltenv>/<hostname>/<path>``.
        Defaults to empty (i.e. caching the file).

        .. note::

            To simply return the file contents instead, set destination to
            ``None``. This works with ``salt://``, ``http://`` and ``https://``
            URLs. The files fetched by ``http://`` and ``https://`` will not
            be cached.

    saltenv
        Salt fileserver environment from which to retrieve the file. Ignored if
        ``path`` is not a ``salt://`` URL. Defaults to ``base``.

    makedirs
        Whether to create the parent directories for ``dest`` as needed.
        Defaults to false.

    source_hash
        If ``path`` is an http(s) or ftp URL and the file exists in the
        minion's file cache, this option can be passed to keep the minion from
        re-downloading the file if the cached copy matches the specified hash.
    """
    with _client() as client:
        if isinstance(dest, str):
            result = client.get_url(
                path, dest, makedirs, saltenv, source_hash=source_hash
            )
        else:
            result = client.get_url(
                path, None, makedirs, saltenv, no_cache=True, source_hash=source_hash
            )
        if not result:
            log.error(
                "Unable to fetch file %s from saltenv %s.",
                salt.utils.url.redact_http_basic_auth(path),
                saltenv,
            )
            return result
        if isinstance(dest, str):
            # Return the cache path on the minion, not the local one
            result = client.target_map[result]
        return salt.utils.stringutils.to_unicode(result)


def get_file_str(path, saltenv="base"):
    """
    Download a file from a URL to the Minion cache directory and return the
    contents of that file.

    Returns ``False`` if Salt was unable to cache a file from a URL.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.get_file_str salt://my/file

    path
        The path on the fileserver, like ``salt://foo/bar/``. It is possible
        to specify the ``saltenv`` using the querystring syntax:
        ``salt://foo/bar?saltenv=config``

    saltenv
        Salt fileserver environment from which to retrieve the file.
    """
    fn_ = cache_file(path, saltenv)
    if isinstance(fn_, str):
        try:
            with salt.utils.files.fopen(fn_, "r") as fp_:
                return salt.utils.stringutils.to_unicode(fp_.read())
        except OSError:
            return False
    return fn_


def cache_file(path, saltenv="base", source_hash=None, verify_ssl=True, use_etag=False):
    """
    Cache a single file on the Minion.
    Returns the location of the new cached file on the Minion.
    If the path being cached is a ``salt://`` URI, and the path does not exist,
    then ``False`` will be returned.

    If the path refers to a fileserver path (``salt://`` URI) and this is a state run,
    the file will also be added to the package of files that's sent to the minion
    for executing the state run (this behaves like ``extra_filerefs``).

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.cache_file salt://path/to/file

    path
        The path on the fileserver, like ``salt://foo/bar/``. It is possible
        to specify the ``saltenv`` using the querystring syntax:
        ``salt://foo/bar?saltenv=config``

    saltenv
        Salt fileserver environment from which to retrieve the file. Ignored if
        ``path`` is not a ``salt://`` URL. Defaults to ``base``.

    source_hash
        If ``name`` is an http(s) or ftp URL and the file exists in the
        minion's file cache, this option can be passed to keep the minion from
        re-downloading the file if the cached copy matches the specified hash.

        .. versionadded:: 2018.3.0

    verify_ssl
        If ``False``, remote https file sources (``https://``) and source_hash
        will not attempt to validate the servers certificate. Default is True.

        .. versionadded:: 3002

    use_etag
        If ``True``, remote http/https file sources will attempt to use the
        ETag header to determine if the remote file needs to be downloaded.
        This provides a lightweight mechanism for promptly refreshing files
        changed on a web server without requiring a full hash comparison via
        the ``source_hash`` parameter.

        .. versionadded:: 3005

    .. note::
        You can instrumentalize this function in your ``sls`` files to workaround a
        limitation in how ``salt-ssh`` handles Jinja imports:

        Imports in templates that will be rendered on the minion (usually during
        ``file.managed`` calls) will fail since the corresponding file is not
        sent to the minion by default.

        By caching it explicitly in your states, you can ensure it will be included
        in the filerefs that will be sent to the minion.

        .. code-block:: jinja

            # /srv/salt/my/config.sls
            {%- do salt["cp.cache_file"]("salt://my/map.jinja") %}

            Serialize config:
              file.managed:
                - name: /etc/my/config.conf
                - source: salt://my/files/config.conf.j2
                - template: jinja

            # /srv/salt/my/config.conf.j2
            {%- from "my/map.jinja" import mapdata with context %}
            myconf = {{ mapdata["foo"] }}

            # /srv/salt/my/map.jinja
            {%- set mapdata = {"foo": "bar"} %}
    """
    path = salt.utils.data.decode(path)
    saltenv = salt.utils.data.decode(saltenv)

    url_data = urllib.parse.urlparse(path)
    if url_data.scheme in ("file", ""):
        return __salt__["cp.cache_file_ssh"](
            path,
            saltenv=saltenv,
            source_hash=source_hash,
            verify_ssl=verify_ssl,
            use_etag=use_etag,
        )

    contextkey = "{}_|-{}_|-{}".format("cp.cache_file", path, saltenv)
    filerefs_ckey = "_cp_extra_filerefs"
    url_data = urllib.parse.urlparse(path)
    path_is_remote = url_data.scheme in salt.utils.files.REMOTE_PROTOS

    def _check_return(result):
        if result and url_data.scheme == "salt":
            if filerefs_ckey not in __context__:
                __context__[filerefs_ckey] = []
            if path not in __context__[filerefs_ckey]:
                __context__[filerefs_ckey].append(path)
        return result

    with _client() as client:
        try:
            if path_is_remote and contextkey in __context__:
                # Prevent multiple caches in the same salt run. Affects remote URLs
                # since the master won't know their hash, so the fileclient
                # wouldn't be able to prevent multiple caches if we try to cache
                # the remote URL more than once.
                if client._path_exists(__context__[contextkey]):
                    return _check_return(__context__[contextkey])
                else:
                    # File is in __context__ but no longer exists in the minion
                    # cache, get rid of the context key and re-cache below.
                    # Accounts for corner case where file is removed from minion
                    # cache between cp.cache_file calls in the same salt-run.
                    __context__.pop(contextkey)
        except AttributeError:
            pass

        # saltenv split from path is performed in client
        result = client.cache_file(
            path,
            saltenv,
            source_hash=source_hash,
            verify_ssl=verify_ssl,
            use_etag=use_etag,
        )
        if not result and not use_etag:
            log.error("Unable to cache file '%s' from saltenv '%s'.", path, saltenv)
        if result:
            # Return the cache path on the minion, not the local one
            result = client.target_map[result]
        if path_is_remote:
            # Cache was successful, store the result in __context__ to prevent
            # multiple caches (see above).
            __context__[contextkey] = result
        return _check_return(result)


def cache_files(paths, saltenv="base"):
    """
    Used to gather many files from the Master, the gathered files will be
    saved in the minion cachedir reflective to the paths retrieved from the
    Master.

    .. note::
        This can take a long time since each file is transferred separately.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.cache_files salt://pathto/file1,salt://pathto/file1

    There are two ways of defining the fileserver environment (a.k.a.
    ``saltenv``) from which to cache the files. One is to use the ``saltenv``
    parameter, and the other is to use a querystring syntax in the ``salt://``
    URL. The below two examples are equivalent:

    .. code-block:: bash

        salt '*' cp.cache_files salt://foo/bar.conf,salt://foo/baz.conf saltenv=config
        salt '*' cp.cache_files salt://foo/bar.conf?saltenv=config,salt://foo/baz.conf?saltenv=config

    The querystring method is less useful when all files are being cached from
    the same environment, but is a good way of caching files from multiple
    different environments in the same command. For example, the below command
    will cache the first file from the ``config1`` environment, and the second
    one from the ``config2`` environment.

    .. code-block:: bash

        salt '*' cp.cache_files salt://foo/bar.conf?saltenv=config1,salt://foo/bar.conf?saltenv=config2

    .. note::
        It may be necessary to quote the URL when using the querystring method,
        depending on the shell being used to run the command.
    """
    # FIXME: transfer using tar
    ret = []
    if isinstance(paths, str):
        paths = paths.split(",")
    for path in paths:
        ret.append(cache_file(path, saltenv))
    return ret


def cache_dir(
    path, saltenv="base", include_empty=False, include_pat=None, exclude_pat=None
):
    """
    Download and cache everything under a directory from the master.

    .. note::
        This can take a long time since each file is transferred separately.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_dir salt://path/to/dir
        salt '*' cp.cache_dir salt://path/to/dir include_pat='E@*.py$'

    path
        The path on the fileserver, like ``salt://foo/bar/``. It is possible
        to specify the ``saltenv`` using the querystring syntax:
        ``salt://foo/bar?saltenv=config``

    saltenv
        Salt fileserver environment from which to retrieve the directory.
        Defaults to ``base``.

    include_empty
        Whether to cache empty directories as well. Defaults to false.

    include_pat : None
        Glob or regex to narrow down the files cached from the given path. If
        matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. versionadded:: 2014.7.0

    exclude_pat : None
        Glob or regex to exclude certain files from being cached from the given
        path. If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. note::

            If used with ``include_pat``, files matching this pattern will be
            excluded from the subset of files defined by ``include_pat``.

        .. versionadded:: 2014.7.0
    """
    # FIXME: transfer using tar
    with _client() as client:
        ret = client.cache_dir(path, saltenv, include_empty, include_pat, exclude_pat)
        if not ret:
            return ret
        return [client.target_map[x] for x in ret]


def cache_master(saltenv="base"):
    """
    Retrieve all of the files on the master and cache them locally.

    .. note::
        This can take a long time since each file is transferred separately.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.cache_master
    """
    # FIXME: transfer using tar
    with _client() as client:
        ret = client.cache_master(saltenv)
        if not ret:
            return ret
        parsed = []
        for file in ret:
            try:
                parsed.append(client.target_map[file])
            except KeyError:
                # Usually because file is False. We can't easily know which one though
                log.error("Failed transferring a file")
        return parsed


def list_states(saltenv="base"):
    """
    List all of the available state files in an environment.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.list_states

    saltenv
        Salt fileserver environment from which to list states.
        Defaults to ``base``.
    """
    return __context__["fileclient"].list_states(saltenv)


def list_master(saltenv="base", prefix=""):
    """
    List all of the files stored on the master.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.list_master

    saltenv
        Salt fileserver environment from which to list files.
        Defaults to ``base``.

    prefix
        Only list files under this prefix. Defaults to empty.
    """
    return __context__["fileclient"].file_list(saltenv, prefix)


def list_master_dirs(saltenv="base", prefix=""):
    """
    List all of the directories stored on the master.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.list_master_dirs

    saltenv
        Salt fileserver environment from which to list directories.
        Defaults to ``base``.

    prefix
        Only list directories under this prefix. Defaults to empty.
    """
    return __context__["fileclient"].dir_list(saltenv, prefix)


def list_master_symlinks(saltenv="base", prefix=""):
    """
    List all of the symlinks stored on the master.
    Will return a mapping of symlink names to absolute paths.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.list_master_symlinks

    saltenv
        Salt fileserver environment from which to list symlinks.
        Defaults to ``base``.

    prefix
        Only list symlinks under this prefix. Defaults to empty.
    """
    return __context__["fileclient"].symlink_list(saltenv, prefix)


def is_cached(path, saltenv="base"):
    """
    Returns the full path to a file if it is cached locally on the minion
    as well as the SSH master-minion, otherwise returns a blank string.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.is_cached salt://path/to/file

    path
        The path to check.

    saltenv
        Salt fileserver environment the file was cached from.
        Defaults to ``base``.
    """
    # saltenv split is done in client
    with _client() as client:
        ret = client.is_cached(path, saltenv)
        if not ret:
            return ret
        return str(client.convert_path(ret))


def hash_file(path, saltenv="base"):
    """
    Return the hash of a file. Supports ``salt://`` URIs and local files.
    Local files should be specified with their absolute paths, without the
    ``file://`` scheme.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.hash_file salt://path/to/file
        salt-ssh '*' cp.hash_file /path/to/file

    path
        The path to return the hash for.

    saltenv
        Salt fileserver environment from which the file should be hashed.
        Defaults to ``base``.
    """
    path, senv = salt.utils.url.split_env(path)
    if senv:
        saltenv = senv
    url_data = urllib.parse.urlparse(path)
    if url_data.scheme in ("file", ""):
        return __salt__["cp.hash_file_ssh"](path, saltenv)
    with _client() as client:
        return client.hash_file(path, saltenv)


def convert_cache_path(path, cachedir=None, master=True):
    """
    It converts a path received by caching a file to the minion cache to the
    corresponding one in the local master cache (or the other way around).

    .. note::

        This function is exclusive to the SSH wrapper module and is mostly
        intended for other wrapper modules to use, not on the CLI.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' cp.convert_cache_path /var/tmp/.root_abc123_salt/running_data/var/cache/salt/minion/files/base/foo.txt

    path
        The path to convert. It has to be in one of the (remote or SSH master-minion)
        cachedirs to be converted, otherwise will be returned verbatim.

    cachedir
        An optional cachedir override that was used when caching the file.

    master
        Whether to convert the path to the master-side path. Defaults
        to true (since this module returns the minion paths otherwise).
    """
    with _client() as client:
        return str(client.convert_path(path, cachedir, master))


def _gather_pillar(pillarenv, pillar_override):
    """
    The opts used during pillar rendering should contain the master
    opts in the root namespace. self.opts is the modified minion opts,
    containing the original master opts in __master_opts__.
    """
    popts = {}
    # Pillar compilation needs the master opts primarily,
    # same as during regular operation.
    popts.update(__opts__)
    popts.update(__opts__.get("__master_opts__", {}))
    pillar = salt.pillar.get_pillar(
        popts,
        __grains__.value(),
        __salt__.kwargs["id_"],
        __opts__["saltenv"] or "base",
        pillar_override=pillar_override,
        pillarenv=pillarenv,
    )
    return pillar.compile_pillar()


def _render_filenames(path, dest, saltenv, template, **kw):
    """
    Process markup in the :param:`path` and :param:`dest` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    """
    if not template:
        return (path, dest)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            f"Attempted to render file paths with unavailable engine {template}"
        )

    kwargs = {}
    kwargs["salt"] = __salt__.value()
    if "pillarenv" in kw or "pillar" in kw:
        pillarenv = kw.get("pillarenv", __opts__.get("pillarenv"))
        kwargs["pillar"] = _gather_pillar(pillarenv, kw.get("pillar"))
    else:
        kwargs["pillar"] = __pillar__.value()
    kwargs["grains"] = __grains__.value()
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

    path = _render(path)
    dest = _render(dest)
    return (path, dest)


class SSHCpClient(salt.fileclient.FSClient):
    """
    A FileClient that replicates between SSH master-minion and remote minion caches
    """

    def __init__(self, opts, shell, tgt):  # pylint: disable=W0231
        salt.fileclient.FSClient.__init__(self, opts)  # pylint: disable=W0233
        self.shell = shell
        self.tgt = tgt
        # Internally, we need to return master paths, but in the wrapper functions,
        # we usually want to return the effective path on the minion.
        # This client is used for a single execution, thus we can easily save
        # all affected file paths for a lookup later.
        self.target_map = {}

    def _local_path_exists(self, path):
        file = self.convert_path(path, master=True)
        return file.exists()

    def _remote_path_exists(self, path):
        # ensure it's the minion path
        path = self.convert_path(path)
        _, _, retcode = self.shell.exec_cmd("test -e " + shlex.quote(str(path)))
        return not retcode

    def _path_exists(self, path):
        return self._local_path_exists(path) and self._remote_path_exists(path)

    def cache_local_file(self, path, **kwargs):
        raise CommandExecutionError("Cannot cache local files via salt-ssh")

    def is_cached(self, path, saltenv="base", cachedir=None):
        """
        Returns the full path to a file if it is cached both locally on the
        SSH master-minion and the minion, otherwise returns a blank string
        """
        if path.startswith("salt://"):
            path, senv = salt.utils.url.parse(path)
            if senv:
                saltenv = senv

        escaped = True if salt.utils.url.is_escaped(path) else False

        # also strip escape character '|'
        localsfilesdest = os.path.join(
            self.opts["cachedir"], "localfiles", path.lstrip("|/")
        )
        filesdest = os.path.join(
            self.opts["cachedir"], "files", saltenv, path.lstrip("|/")
        )
        extrndest = self._extrn_path(path, saltenv, cachedir=cachedir)

        if self._path_exists(filesdest):
            return salt.utils.url.escape(filesdest) if escaped else filesdest
        # While we do not cache minion-local files back on the master,
        # we can inspect the minion cache dir remotely
        if self._remote_path_exists(localsfilesdest):
            return (
                salt.utils.url.escape(localsfilesdest) if escaped else localsfilesdest
            )
        if self._path_exists(extrndest):
            return extrndest

        return ""

    def get_cachedir(
        self, cachedir=None, master=True
    ):  # pylint: disable=arguments-differ
        prefix = []
        if master:
            prefix = ["salt-ssh", self.tgt]
        if cachedir is None:
            cachedir = os.path.join(self.opts["cachedir"], *prefix)
        elif not os.path.isabs(cachedir):
            cachedir = os.path.join(self.opts["cachedir"], *prefix, cachedir)
        elif master:
            # The root cachedir on the master-side should not be overridden
            cachedir = os.path.join(
                self.opts["cachedir"],
                *prefix,
                "absolute_root",
                str(Path(*cachedir.split(os.sep)[1:])),
            )
        return cachedir

    def convert_path(self, path, cachedir=None, master=False):
        """
        Convert a cache path from master/minion to the other.

        Both use the same cachedir in salt-ssh, but our fileclient
        here caches to a subdir on the master. Remove/add it from/to
        the path.
        """
        path = Path(path)
        master_cachedir = Path(self.get_cachedir(cachedir, master=True))
        minion_cachedir = Path(self.get_cachedir(cachedir, master=False))
        if master:
            # This check could be path.is_relative_to(curr_prefix),
            # but that requires Python 3.9
            if master_cachedir in path.parents:
                return path
            return master_cachedir / path.relative_to(minion_cachedir)
        if master_cachedir not in path.parents:
            return path
        return minion_cachedir / path.relative_to(master_cachedir)

    def _send_file(self, src, dest, makedirs, cachedir):
        def _error(stdout, stderr):
            log.error("Failed sending file: %s", stderr or stdout)
            if Path(self.get_cachedir(cachedir)) in Path(src).parents:
                # remove the cached file if the transfer fails
                Path(src).unlink(missing_ok=True)
            return False

        for path in (src, dest):
            if not Path(path).is_absolute():
                raise ValueError(
                    f"Paths must be absolute, got '{path}' as {'src' if path == src else 'dest'}"
                )
        src, dest = str(src), str(dest)  # ensure we're using strings
        stdout, stderr, retcode = self.shell.send(src, dest, makedirs)
        if retcode and makedirs and "Not a directory" in stderr:
            # This means the file path contains a parent that is currently a file
            # Remove it, but only if it's in our cache dir
            minion_cachedir = Path(self.get_cachedir(cachedir, master=False))
            dest = cur = Path(dest)
            while minion_cachedir in cur.parents:
                if self._isfile(cur):
                    if not self._rmpath(cur):
                        return _error(stdout, stderr)
                    dest = str(dest)
                    break
                cur = cur.parent
            else:
                return _error(stdout, stderr)
            # The offending file was removed, retry
            stdout, stderr, retcode = self.shell.send(src, dest, makedirs)
        if retcode:
            return _error(stdout, stderr)
        self.target_map[src] = dest
        # we need to return the local source for internal functionality
        return src

    def _isdir(self, path):
        _, _, retcode = self.shell.exec_cmd("test -d " + shlex.quote(str(path)))
        return not retcode

    def _isfile(self, path):
        _, _, retcode = self.shell.exec_cmd("test -f " + shlex.quote(str(path)))
        return not retcode

    def _rmpath(self, path, cachedir=None):
        path = Path(path)
        if not path or not path.is_absolute() or str(path) == "/":
            raise ValueError(
                f"Not deleting unspecified, relative or root path: '{path}'"
            )
        minion_cachedir = Path(self.get_cachedir(cachedir, master=False))
        if minion_cachedir not in path.parents and path != minion_cachedir:
            raise ValueError(
                f"Not recursively deleting a path outside of the cachedir. Path: '{path}'"
            )
        stdout, stderr, retcode = self.shell.exec_cmd(
            "rm -rf " + shlex.quote(str(path))
        )
        if retcode:
            log.error("Failed deleting path '%s': %s", path, stderr or stdout)
        return not retcode

    def get_url(
        self,
        url,
        dest,
        makedirs=False,
        saltenv="base",
        no_cache=False,
        cachedir=None,
        source_hash=None,
        verify_ssl=True,
        use_etag=False,
    ):
        url_data = urllib.parse.urlparse(url)
        if url_data.scheme in ("file", ""):
            # This should be executed on the minion (unwrapped)
            log.error("The file:// scheme is not supported via the salt-ssh cp wrapper")
            return False
        # Ensure we don't send the file twice
        if url_data.scheme == "salt":
            result = self.get_file(url, dest, makedirs, saltenv, cachedir=cachedir)
            if result and dest is None:
                with salt.utils.files.fopen(result, "rb") as fp_:
                    data = fp_.read()
                return data
            return result
        cached = super().get_url(
            url,
            "",
            makedirs=True,
            saltenv=saltenv,
            no_cache=no_cache,
            cachedir=cachedir,
            source_hash=source_hash,
            verify_ssl=verify_ssl,
            use_etag=use_etag,
        )
        if not cached:
            return cached
        if not isinstance(dest, str) and no_cache:
            # Only if dest is None and no_cache is True, the contents
            # will be found in cached, otherwise the regular fileclient
            # behaves the same as with dest == ""
            return cached
        strict = False
        if not dest:
            # The file needs to be cached to the minion cache.
            # We're using the same cachedir on the ssh master and the minion,
            # but for the master cache, we appended a subdir. Remove it.
            makedirs = True
            dest = str(self.convert_path(cached, cachedir))
            strict = True
        # This is not completely foolproof, but should do the job most
        # of the time and is mostly how the regular client handles it.
        if dest.endswith("/") or self._isdir(dest):
            if not dest.endswith("/"):
                if (
                    strict
                    or self.get_cachedir(cachedir, master=False) in Path(dest).parents
                ):
                    strict = True
                    if not self._rmpath(dest):
                        Path(cached).unlink(missing_ok=True)
                        return False
            if not strict:
                if (
                    url_data.query
                    or len(url_data.path) > 1
                    and not url_data.path.endswith("/")
                ):
                    strpath = url.split("/")[-1]
                else:
                    strpath = "index.html"
                dest = os.path.join(dest, strpath)
        return self._send_file(cached, dest, makedirs, cachedir)

    def get_file(
        self, path, dest="", makedirs=False, saltenv="base", gzip=None, cachedir=None
    ):
        """
        Get a single file from the salt-master
        path must be a salt server location, aka, salt://path/to/file, if
        dest is omitted, then the downloaded file will be placed in the minion
        cache
        """
        src = super().get_file(
            path,
            "",
            makedirs=True,
            saltenv=saltenv,
            cachedir=cachedir,
        )
        if not src:
            return src
        strict = False
        # Passing None evokes the same behavior as an empty string
        # in the parent class as well, which we want to replicate.
        if not dest:
            # The file needs to be cached to the minion cache.
            # We're using the same cachedir on the ssh master and the minion,
            # but for the master cache, we appended a subdir. Remove it.
            makedirs = True
            dest = str(self.convert_path(src, cachedir))
            strict = True

        # This is not completely foolproof, but should do the job most
        # of the time and is mostly how the regular client handles it.
        if dest.endswith("/") or self._isdir(dest):
            if not dest.endswith("/"):
                if (
                    strict
                    or self.get_cachedir(cachedir, master=False) in Path(dest).parents
                ):
                    strict = True
                    if not self._rmpath(dest):
                        Path(src).unlink(missing_ok=True)
                        return ""
            if not strict:
                dest = os.path.join(dest, os.path.basename(src))
        # TODO replicate hash checks to avoid unnecessary transfers,
        # possibly in _send_file to also account for other sources
        return self._send_file(src, dest, makedirs, cachedir)

    def get_template(
        self,
        url,
        dest,
        template="jinja",
        makedirs=False,
        saltenv="base",
        cachedir=None,
        **kwargs,
    ):
        """
        Cache a file then process it as a template
        """
        res = super().get_template(
            url,
            "",
            template=template,
            makedirs=makedirs,
            saltenv=saltenv,
            cachedir=cachedir,
            **kwargs,
        )
        if not res:
            return res
        strict = False
        if not dest:
            # The file needs to be cached to the minion cache.
            # We're using the same cachedir on the ssh master and the minion,
            # but for the master cache, we appended a subdir. Remove it.
            makedirs = True
            dest = str(self.convert_path(res, cachedir))
            strict = True
        if dest.endswith("/") or self._isdir(dest):
            if not dest.endswith("/"):
                if (
                    strict
                    or self.get_cachedir(cachedir, master=False) in Path(dest).parents
                ):
                    strict = True
                    if not self._rmpath(dest):
                        Path(res).unlink(missing_ok=True)
                        return ""
            if not strict:
                dest = os.path.join(dest, os.path.basename(res))
        return self._send_file(res, dest, makedirs, cachedir)

    def _extrn_path(self, url, saltenv, cachedir=None):
        # _extrn_path accesses self.opts["cachedir"] directly,
        # so we have to wrap it here to ensure our master prefix works
        res = super()._extrn_path(url, saltenv, cachedir=cachedir)
        return str(self.convert_path(res, cachedir, master=True))

    def cache_dest(self, url, saltenv="base", cachedir=None):
        """
        Return the expected cache location for the specified URL and
        environment.
        """
        # cache_dest accesses self.opts["cachedir"] directly,
        # so we have to wrap it here to ensure our master prefix works
        res = super().cache_dest(url, saltenv=saltenv, cachedir=cachedir)
        return str(self.convert_path(res, cachedir, master=True))

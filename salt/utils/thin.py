"""
Generate the salt thin tarball from the installed python files
"""

import contextvars as py_contextvars
import copy
import importlib.util
import logging
import os
import shutil
import site
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import distro
import jinja2
import looseversion
import msgpack
import packaging
import yaml

import salt
import salt.exceptions
import salt.ext.tornado as tornado
import salt.utils.files
import salt.utils.hashutils
import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
import salt.version

# This is needed until we drop support for python 3.6
has_immutables = False
try:
    import immutables

    has_immutables = True
except ImportError:
    pass


try:
    import zlib
except ImportError:
    zlib = None

# pylint: disable=import-error,no-name-in-module
try:
    import certifi
except ImportError:
    certifi = None

try:
    import singledispatch
except ImportError:
    singledispatch = None

try:
    import singledispatch_helpers
except ImportError:
    singledispatch_helpers = None

try:
    import backports_abc
except ImportError:
    import salt.ext.backports_abc as backports_abc

try:
    # New Jinja only
    import markupsafe
except ImportError:
    markupsafe = None


try:
    # Older python where the backport from pypi is installed
    from backports import ssl_match_hostname
except ImportError:
    # Other older python we use our bundled copy
    try:
        from salt.ext import ssl_match_hostname
    except ImportError:
        ssl_match_hostname = None

concurrent = None


log = logging.getLogger(__name__)


def import_module(name, path):
    """
    Import a module from a specific path. Path can be a full or relative path
    to a .py file.

    :name: The name of the module to import
    :path: The path of the module to import
    """
    try:
        spec = importlib.util.spec_from_file_location(name, path)
    except ValueError:
        spec = None
    if spec is not None:
        lib = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(lib)
        except OSError:
            pass
        else:
            return lib


def getsitepackages():
    """
    Some versions of Virtualenv ship a site.py without getsitepackages. This
    method will first try and return sitepackages from the default site module
    if no method exists we will try importing the site module from every other
    path in sys.paths until we find a getsitepackages method to return the
    results from. If for some reason no gesitepackages method can be found a
    RuntimeError will be raised

    :return: A list containing all global site-packages directories.
    """
    if hasattr(site, "getsitepackages"):
        return site.getsitepackages()
    for path in sys.path:
        lib = import_module("site", os.path.join(path, "site.py"))
        if hasattr(lib, "getsitepackages"):
            return lib.getsitepackages()
    raise RuntimeError("Unable to locate a getsitepackages method")


def find_site_modules(name):
    """
    Finds and imports a module from site packages directories.

    :name: The name of the module to import
    :return: A list of imported modules, if no modules are imported an empty
             list is returned.
    """
    libs = []
    site_paths = []
    try:
        site_paths = getsitepackages()
    except RuntimeError:
        log.debug("No site package directories found")
    for site_path in site_paths:
        path = os.path.join(site_path, "{}.py".format(name))
        lib = import_module(name, path)
        if lib:
            libs.append(lib)
        path = os.path.join(site_path, name, "__init__.py")
        lib = import_module(name, path)
        if lib:
            libs.append(lib)
    return libs


def _get_salt_call(*dirs, **namespaces):
    """
    Return salt-call source, based on configuration.
    This will include additional namespaces for another versions of Salt,
    if needed (e.g. older interpreters etc).

    :dirs: List of directories to include in the system path
    :namespaces: Dictionary of namespace
    :return:
    """
    template = """# -*- coding: utf-8 -*-
import os
import sys

# Namespaces is a map: {namespace: major/minor version}, like {'2016.11.4': [2, 6]}
# Appears only when configured in Master configuration.
namespaces = %namespaces%

# Default system paths alongside the namespaces
syspaths = %dirs%
syspaths.append('py{0}'.format(sys.version_info[0]))

curr_ver = (sys.version_info[0], sys.version_info[1],)

namespace = ''
for ns in namespaces:
    if curr_ver == tuple(namespaces[ns]):
        namespace = ns
        break

for base in syspaths:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                    namespace and os.path.join(namespace, base) or base))

if __name__ == '__main__':
    from salt.scripts import salt_call
    salt_call()
"""

    for tgt, cnt in [("%dirs%", dirs), ("%namespaces%", namespaces)]:
        template = template.replace(tgt, salt.utils.json.dumps(cnt))

    return salt.utils.stringutils.to_bytes(template)


def thin_path(cachedir):
    """
    Return the path to the thin tarball
    """
    return os.path.join(cachedir, "thin", "thin.tgz")


def _is_shareable(mod):
    """
    Return True if module is share-able between major Python versions.

    :param mod:
    :return:
    """
    # This list is subject to change
    shareable = ["salt", "jinja2", "msgpack", "certifi"]

    return os.path.basename(mod) in shareable


def _add_dependency(container, obj):
    """
    Add a dependency to the top list.

    :param obj:
    :param is_file:
    :return:
    """
    if os.path.basename(obj.__file__).split(".")[0] == "__init__":
        container.append(os.path.dirname(obj.__file__))
    else:
        container.append(obj.__file__.replace(".pyc", ".py"))


def gte():
    """
    This function is called externally from the alternative
    Python interpreter from within _get_tops function.

    :param extra_mods:
    :param so_mods:
    :return:
    """
    extra = salt.utils.json.loads(sys.argv[1])
    tops = get_tops(**extra)

    return salt.utils.json.dumps(tops, ensure_ascii=False)


def get_tops_python(py_ver, exclude=None, ext_py_ver=None):
    """
    Get top directories for the ssh_ext_alternatives dependencies
    automatically for the given python version. This allows
    the user to add the dependency paths automatically.

    :param py_ver:
        python binary to use to detect binaries

    :param exclude:
        list of modules not to auto detect

    :param ext_py_ver:
        the py-version from the ssh_ext_alternatives config
    """
    files = {}
    mods = [
        "jinja2",
        "yaml",
        "tornado",
        "msgpack",
        "certifi",
        "singledispatch",
        "concurrent",
        "singledispatch_helpers",
        "ssl_match_hostname",
        "markupsafe",
        "backports_abc",
        "looseversion",
        "packaging",
    ]
    if ext_py_ver and tuple(ext_py_ver) >= (3, 0):
        mods.append("distro")

    for mod in mods:
        if exclude and mod in exclude:
            continue

        if not salt.utils.path.which(py_ver):
            log.error("%s does not exist. Could not auto detect dependencies", py_ver)
            return {}
        py_shell_cmd = [py_ver, "-c", "import {0}; print({0}.__file__)".format(mod)]
        cmd = subprocess.Popen(py_shell_cmd, stdout=subprocess.PIPE)
        stdout, _ = cmd.communicate()
        mod_file = os.path.abspath(salt.utils.data.decode(stdout).rstrip("\n"))

        if not stdout or not os.path.exists(mod_file):
            log.error(
                "Could not auto detect file location for module %s for python version %s",
                mod,
                py_ver,
            )
            continue

        if os.path.basename(mod_file).split(".")[0] == "__init__":
            mod_file = os.path.dirname(mod_file)
        else:
            mod_file = mod_file.replace("pyc", "py")

        files[mod] = mod_file
    return files


def get_ext_tops(config):
    """
    Get top directories for the dependencies, based on external configuration.

    :return:
    """
    config = copy.deepcopy(config) or {}
    alternatives = {}
    required = ["jinja2", "yaml", "tornado", "msgpack"]
    tops = []
    for ns, cfg in config.items():
        alternatives[ns] = cfg
        locked_py_version = cfg.get("py-version")
        err_msg = None
        if not locked_py_version:
            err_msg = "Alternative Salt library: missing specific locked Python version"
        elif not isinstance(locked_py_version, (tuple, list)):
            err_msg = (
                "Alternative Salt library: specific locked Python version "
                "should be a list of major/minor version"
            )
        if err_msg:
            raise salt.exceptions.SaltSystemExit(err_msg)

        if tuple(locked_py_version) >= (3, 0) and "distro" not in required:
            required.append("distro")

        if cfg.get("dependencies") == "inherit":
            # TODO: implement inheritance of the modules from _here_
            raise NotImplementedError("This feature is not yet implemented")
        else:
            for dep in cfg.get("dependencies"):
                mod = cfg["dependencies"][dep] or ""
                if not mod:
                    log.warning("Module %s has missing configuration", dep)
                    continue
                elif mod.endswith(".py") and not os.path.isfile(mod):
                    log.warning(
                        "Module %s configured with not a file or does not exist: %s",
                        dep,
                        mod,
                    )
                    continue
                elif not mod.endswith(".py") and not os.path.isfile(
                    os.path.join(mod, "__init__.py")
                ):
                    log.warning(
                        "Module %s is not a Python importable module with %s", dep, mod
                    )
                    continue
                tops.append(mod)

                if dep in required:
                    required.pop(required.index(dep))

            required = ", ".join(required)
            if required:
                msg = (
                    "Missing dependencies for the alternative version"
                    " in the external configuration: {}".format(required)
                )
                log.error(msg)
                raise salt.exceptions.SaltSystemExit(msg=msg)
        alternatives[ns]["dependencies"] = tops
    return alternatives


def _get_ext_namespaces(config):
    """
    Get namespaces from the existing configuration.

    :param config:
    :return:
    """
    namespaces = {}
    if not config:
        return namespaces

    for ns in config:
        constraint_version = tuple(config[ns].get("py-version", []))
        if not constraint_version:
            raise salt.exceptions.SaltSystemExit(
                "An alternative version is configured, but not defined "
                "to what Python's major/minor version it should be constrained."
            )
        else:
            namespaces[ns] = constraint_version

    return namespaces


def get_tops(extra_mods="", so_mods=""):
    """
    Get top directories for the dependencies, based on Python interpreter.

    :param extra_mods:
    :param so_mods:
    :return:
    """
    tops = []
    mods = [
        salt,
        distro,
        jinja2,
        yaml,
        tornado,
        msgpack,
        certifi,
        singledispatch,
        concurrent,
        singledispatch_helpers,
        ssl_match_hostname,
        markupsafe,
        backports_abc,
        looseversion,
        packaging,
    ]
    modules = find_site_modules("contextvars")
    if modules:
        contextvars = modules[0]
    else:
        contextvars = py_contextvars
    log.debug("Using contextvars %r", contextvars)
    mods.append(contextvars)
    if has_immutables:
        mods.append(immutables)
    for mod in mods:
        if mod:
            log.debug('Adding module to the tops: "%s"', mod.__name__)
            _add_dependency(tops, mod)

    for mod in [m for m in extra_mods.split(",") if m]:
        if mod not in locals() and mod not in globals():
            try:
                locals()[mod] = __import__(mod)
                moddir, modname = os.path.split(locals()[mod].__file__)
                base, _ = os.path.splitext(modname)
                if base == "__init__":
                    tops.append(moddir)
                else:
                    tops.append(os.path.join(moddir, base + ".py"))
            except ImportError as err:
                log.error(
                    'Unable to import extra-module "%s": %s', mod, err, exc_info=True
                )

    for mod in [m for m in so_mods.split(",") if m]:
        try:
            locals()[mod] = __import__(mod)
            tops.append(locals()[mod].__file__)
        except ImportError as err:
            log.error('Unable to import so-module "%s"', mod, exc_info=True)

    return tops


def _get_supported_py_config(tops, extended_cfg):
    """
    Based on the Salt SSH configuration, create a YAML configuration
    for the supported Python interpreter versions. This is then written into the thin.tgz
    archive and then verified by salt.client.ssh.ssh_py_shim.get_executable()

    Note: Current versions of Salt only Support Python 3, but the versions of Python
    (2.7,3.0) remain to include support for ssh_ext_alternatives if user is targeting an
    older version of Salt.
    :return:
    """
    pymap = []
    for py_ver, tops in copy.deepcopy(tops).items():
        py_ver = int(py_ver)
        if py_ver == 2:
            pymap.append("py2:2:7")
        elif py_ver == 3:
            pymap.append("py3:3:0")
    cfg_copy = copy.deepcopy(extended_cfg) or {}
    for ns, cfg in cfg_copy.items():
        pymap.append("{}:{}:{}".format(ns, *cfg.get("py-version")))
    pymap.append("")

    return salt.utils.stringutils.to_bytes(os.linesep.join(pymap))


def _get_thintar_prefix(tarname):
    """
    Make sure thintar temporary name is concurrent and secure.

    :param tarname: name of the chosen tarball
    :return: prefixed tarname
    """
    tfd, tmp_tarname = tempfile.mkstemp(
        dir=os.path.dirname(tarname),
        prefix=".thin-",
        suffix=os.path.splitext(tarname)[1],
    )
    os.close(tfd)

    return tmp_tarname


def _pack_alternative(extended_cfg, digest_collector, tfp):
    # Pack alternative data
    config = copy.deepcopy(extended_cfg)
    # Check if auto_detect is enabled and update dependencies
    for ns, cfg in config.items():
        if cfg.get("auto_detect"):
            py_ver = "python" + str(cfg.get("py-version", [""])[0])
            if cfg.get("py_bin"):
                py_ver = cfg["py_bin"]

            exclude = []
            # get any manually set deps
            deps = config[ns].get("dependencies")
            if deps:
                for dep in deps.keys():
                    exclude.append(dep)
            else:
                config[ns]["dependencies"] = {}

            # get auto deps
            auto_deps = get_tops_python(
                py_ver, exclude=exclude, ext_py_ver=cfg["py-version"]
            )
            for dep in auto_deps:
                config[ns]["dependencies"][dep] = auto_deps[dep]

    for ns, cfg in get_ext_tops(config).items():
        tops = [cfg.get("path")] + cfg.get("dependencies")
        py_ver_major, py_ver_minor = cfg.get("py-version")

        for top in tops:
            top = os.path.normpath(top)
            base, top_dirname = os.path.basename(top), os.path.dirname(top)
            os.chdir(top_dirname)
            site_pkg_dir = (
                _is_shareable(base) and "pyall" or "py{}".format(py_ver_major)
            )
            log.debug(
                'Packing alternative "%s" to "%s/%s" destination',
                base,
                ns,
                site_pkg_dir,
            )
            if not os.path.exists(top):
                log.error(
                    "File path %s does not exist. Unable to add to salt-ssh thin", top
                )
                continue
            if not os.path.isdir(top):
                # top is a single file module
                if os.path.exists(os.path.join(top_dirname, base)):
                    tfp.add(base, arcname=os.path.join(ns, site_pkg_dir, base))
                continue
            for root, dirs, files in salt.utils.path.os_walk(base, followlinks=True):
                for name in files:
                    if not name.endswith((".pyc", ".pyo")):
                        digest_collector.add(os.path.join(root, name))
                        arcname = os.path.join(ns, site_pkg_dir, root, name)
                        if hasattr(tfp, "getinfo"):
                            try:
                                tfp.getinfo(os.path.join(site_pkg_dir, root, name))
                                arcname = None
                            except KeyError:
                                log.debug(
                                    'ZIP: Unable to add "%s" with "getinfo"', arcname
                                )
                        if arcname:
                            tfp.add(os.path.join(root, name), arcname=arcname)


def gen_thin(
    cachedir,
    extra_mods="",
    overwrite=False,
    so_mods="",
    absonly=True,
    compress="gzip",
    extended_cfg=None,
):
    """
    Generate the salt-thin tarball and print the location of the tarball
    Optional additional mods to include (e.g. mako) can be supplied as a comma
    delimited string.  Permits forcing an overwrite of the output file as well.

    CLI Example:

    .. code-block:: bash

        salt-run thin.generate
        salt-run thin.generate mako
        salt-run thin.generate mako,wempy 1
        salt-run thin.generate overwrite=1
    """
    if sys.version_info < (3,):
        raise salt.exceptions.SaltSystemExit(
            'The minimum required python version to run salt-ssh is "3".'
        )
    if compress not in ["gzip", "zip"]:
        log.warning(
            'Unknown compression type: "%s". Falling back to "gzip" compression.',
            compress,
        )
        compress = "gzip"

    thindir = os.path.join(cachedir, "thin")
    if not os.path.isdir(thindir):
        os.makedirs(thindir)
    thintar = os.path.join(thindir, "thin." + (compress == "gzip" and "tgz" or "zip"))
    thinver = os.path.join(thindir, "version")
    pythinver = os.path.join(thindir, ".thin-gen-py-version")
    salt_call = os.path.join(thindir, "salt-call")
    pymap_cfg = os.path.join(thindir, "supported-versions")
    code_checksum = os.path.join(thindir, "code-checksum")
    digest_collector = salt.utils.hashutils.DigestCollector()

    with salt.utils.files.fopen(salt_call, "wb") as fp_:
        fp_.write(_get_salt_call("pyall", **_get_ext_namespaces(extended_cfg)))

    if os.path.isfile(thintar):
        if not overwrite:
            if os.path.isfile(thinver):
                with salt.utils.files.fopen(thinver) as fh_:
                    overwrite = fh_.read() != salt.version.__version__
                if overwrite is False and os.path.isfile(pythinver):
                    with salt.utils.files.fopen(pythinver) as fh_:
                        overwrite = fh_.read() != str(sys.version_info[0])
            else:
                overwrite = True

        if overwrite:
            try:
                log.debug("Removing %s archive file", thintar)
                os.remove(thintar)
            except OSError as exc:
                log.error("Error while removing %s file: %s", thintar, exc)
                if os.path.exists(thintar):
                    raise salt.exceptions.SaltSystemExit(
                        "Unable to remove {} file. See logs for details.".format(
                            thintar
                        )
                    )
        else:
            return thintar

    tops_failure_msg = "Failed %s tops for Python binary %s."
    tops_py_version_mapping = {}
    tops = get_tops(extra_mods=extra_mods, so_mods=so_mods)
    tops_py_version_mapping[sys.version_info.major] = tops

    with salt.utils.files.fopen(pymap_cfg, "wb") as fp_:
        fp_.write(
            _get_supported_py_config(
                tops=tops_py_version_mapping, extended_cfg=extended_cfg
            )
        )

    tmp_thintar = _get_thintar_prefix(thintar)
    if compress == "gzip":
        tfp = tarfile.open(tmp_thintar, "w:gz", dereference=True)
    elif compress == "zip":
        tfp = zipfile.ZipFile(
            tmp_thintar,
            "w",
            compression=zlib and zipfile.ZIP_DEFLATED or zipfile.ZIP_STORED,
        )
        tfp.add = tfp.write
    try:  # cwd may not exist if it was removed but salt was run from it
        start_dir = os.getcwd()
    except OSError:
        start_dir = None
    tempdir = None

    # Pack default data
    log.debug("Packing default libraries based on current Salt version")
    for py_ver, tops in tops_py_version_mapping.items():
        for top in tops:
            if absonly and not os.path.isabs(top):
                continue
            base = os.path.basename(top)
            top_dirname = os.path.dirname(top)
            if os.path.isdir(top_dirname):
                os.chdir(top_dirname)
            else:
                # This is likely a compressed python .egg
                tempdir = tempfile.mkdtemp()
                egg = zipfile.ZipFile(top_dirname)
                egg.extractall(tempdir)
                top = os.path.join(tempdir, base)
                os.chdir(tempdir)

            site_pkg_dir = _is_shareable(base) and "pyall" or "py{}".format(py_ver)

            log.debug('Packing "%s" to "%s" destination', base, site_pkg_dir)
            if not os.path.isdir(top):
                # top is a single file module
                if os.path.exists(os.path.join(top_dirname, base)):
                    tfp.add(base, arcname=os.path.join(site_pkg_dir, base))
                continue
            for root, dirs, files in salt.utils.path.os_walk(base, followlinks=True):
                for name in files:
                    if not name.endswith((".pyc", ".pyo")):
                        digest_collector.add(os.path.join(root, name))
                        arcname = os.path.join(site_pkg_dir, root, name)
                        if hasattr(tfp, "getinfo"):
                            try:
                                # This is a little slow but there's no clear way to detect duplicates
                                tfp.getinfo(os.path.join(site_pkg_dir, root, name))
                                arcname = None
                            except KeyError:
                                log.debug(
                                    'ZIP: Unable to add "%s" with "getinfo"', arcname
                                )
                        if arcname:
                            tfp.add(os.path.join(root, name), arcname=arcname)

            if tempdir is not None:
                shutil.rmtree(tempdir)
                tempdir = None

    if extended_cfg:
        log.debug("Packing libraries based on alternative Salt versions")
        _pack_alternative(extended_cfg, digest_collector, tfp)

    os.chdir(thindir)
    with salt.utils.files.fopen(thinver, "w+") as fp_:
        fp_.write(salt.version.__version__)
    with salt.utils.files.fopen(pythinver, "w+") as fp_:
        fp_.write(str(sys.version_info.major))
    with salt.utils.files.fopen(code_checksum, "w+") as fp_:
        fp_.write(digest_collector.digest())
    os.chdir(os.path.dirname(thinver))

    for fname in [
        "version",
        ".thin-gen-py-version",
        "salt-call",
        "supported-versions",
        "code-checksum",
    ]:
        tfp.add(fname)

    if start_dir and os.access(start_dir, os.R_OK) and os.access(start_dir, os.X_OK):
        os.chdir(start_dir)
    tfp.close()

    shutil.move(tmp_thintar, thintar)

    return thintar


def thin_sum(cachedir, form="sha1"):
    """
    Return the checksum of the current thin tarball
    """
    thintar = gen_thin(cachedir)
    code_checksum_path = os.path.join(cachedir, "thin", "code-checksum")
    if os.path.isfile(code_checksum_path):
        with salt.utils.files.fopen(code_checksum_path, "r") as fh:
            code_checksum = "'{}'".format(fh.read().strip())
    else:
        code_checksum = "'0'"

    return code_checksum, salt.utils.hashutils.get_hash(thintar, form)


def gen_min(
    cachedir,
    extra_mods="",
    overwrite=False,
    so_mods="",
):
    """
    Generate the salt-min tarball and print the location of the tarball
    Optional additional mods to include (e.g. mako) can be supplied as a comma
    delimited string.  Permits forcing an overwrite of the output file as well.

    CLI Example:

    .. code-block:: bash

        salt-run min.generate
        salt-run min.generate mako
        salt-run min.generate mako,wempy 1
        salt-run min.generate overwrite=1
    """
    mindir = os.path.join(cachedir, "min")
    if not os.path.isdir(mindir):
        os.makedirs(mindir)
    mintar = os.path.join(mindir, "min.tgz")
    minver = os.path.join(mindir, "version")
    pyminver = os.path.join(mindir, ".min-gen-py-version")
    salt_call = os.path.join(mindir, "salt-call")
    with salt.utils.files.fopen(salt_call, "wb") as fp_:
        fp_.write(_get_salt_call())
    if os.path.isfile(mintar):
        if not overwrite:
            if os.path.isfile(minver):
                with salt.utils.files.fopen(minver) as fh_:
                    overwrite = fh_.read() != salt.version.__version__
                if overwrite is False and os.path.isfile(pyminver):
                    with salt.utils.files.fopen(pyminver) as fh_:
                        overwrite = fh_.read() != str(sys.version_info[0])
            else:
                overwrite = True

        if overwrite:
            try:
                os.remove(mintar)
            except OSError:
                pass
        else:
            return mintar

    tops_py_version_mapping = {}
    tops = get_tops(extra_mods=extra_mods, so_mods=so_mods)
    tops_py_version_mapping["3"] = tops

    tfp = tarfile.open(mintar, "w:gz", dereference=True)
    try:  # cwd may not exist if it was removed but salt was run from it
        start_dir = os.getcwd()
    except OSError:
        start_dir = None
    tempdir = None

    # This is the absolute minimum set of files required to run salt-call
    min_files = (
        "salt/__init__.py",
        "salt/utils",
        "salt/utils/__init__.py",
        "salt/utils/atomicfile.py",
        "salt/utils/validate",
        "salt/utils/validate/__init__.py",
        "salt/utils/validate/path.py",
        "salt/utils/decorators",
        "salt/utils/decorators/__init__.py",
        "salt/utils/cache.py",
        "salt/utils/xdg.py",
        "salt/utils/odict.py",
        "salt/utils/minions.py",
        "salt/utils/dicttrim.py",
        "salt/utils/sdb.py",
        "salt/utils/migrations.py",
        "salt/utils/files.py",
        "salt/utils/parsers.py",
        "salt/utils/locales.py",
        "salt/utils/lazy.py",
        "salt/utils/s3.py",
        "salt/utils/dictupdate.py",
        "salt/utils/verify.py",
        "salt/utils/args.py",
        "salt/utils/kinds.py",
        "salt/utils/xmlutil.py",
        "salt/utils/debug.py",
        "salt/utils/jid.py",
        "salt/utils/openstack",
        "salt/utils/openstack/__init__.py",
        "salt/utils/openstack/swift.py",
        "salt/utils/asynchronous.py",
        "salt/utils/process.py",
        "salt/utils/jinja.py",
        "salt/utils/rsax931.py",
        "salt/utils/context.py",
        "salt/utils/minion.py",
        "salt/utils/error.py",
        "salt/utils/aws.py",
        "salt/utils/timed_subprocess.py",
        "salt/utils/zeromq.py",
        "salt/utils/schedule.py",
        "salt/utils/url.py",
        "salt/utils/yamlencoding.py",
        "salt/utils/network.py",
        "salt/utils/http.py",
        "salt/utils/gzip_util.py",
        "salt/utils/vt.py",
        "salt/utils/templates.py",
        "salt/utils/aggregation.py",
        "salt/utils/yaml.py",
        "salt/utils/yamldumper.py",
        "salt/utils/yamlloader.py",
        "salt/utils/event.py",
        "salt/utils/state.py",
        "salt/serializers",
        "salt/serializers/__init__.py",
        "salt/serializers/yamlex.py",
        "salt/template.py",
        "salt/_compat.py",
        "salt/loader.py",
        "salt/client",
        "salt/client/__init__.py",
        "salt/ext",
        "salt/ext/__init__.py",
        "salt/ext/six.py",
        "salt/ext/ipaddress.py",
        "salt/version.py",
        "salt/syspaths.py",
        "salt/defaults",
        "salt/defaults/__init__.py",
        "salt/defaults/exitcodes.py",
        "salt/renderers",
        "salt/renderers/__init__.py",
        "salt/renderers/jinja.py",
        "salt/renderers/yaml.py",
        "salt/modules",
        "salt/modules/__init__.py",
        "salt/modules/test.py",
        "salt/modules/selinux.py",
        "salt/modules/cmdmod.py",
        "salt/modules/saltutil.py",
        "salt/minion.py",
        "salt/pillar",
        "salt/pillar/__init__.py",
        "salt/utils/textformat.py",
        "salt/log_handlers",
        "salt/log_handlers/__init__.py",
        "salt/_logging/__init__.py",
        "salt/_logging/handlers.py",
        "salt/_logging/impl.py",
        "salt/_logging/mixins.py",
        "salt/cli",
        "salt/cli/__init__.py",
        "salt/cli/caller.py",
        "salt/cli/daemons.py",
        "salt/cli/salt.py",
        "salt/cli/call.py",
        "salt/fileserver",
        "salt/fileserver/__init__.py",
        "salt/channel",
        "salt/channel/__init__.py",
        "salt/channel/client.py",
        "salt/transport",  # XXX Are the transport imports still needed?
        "salt/transport/__init__.py",
        "salt/transport/client.py",
        "salt/exceptions.py",
        "salt/grains",
        "salt/grains/__init__.py",
        "salt/grains/extra.py",
        "salt/scripts.py",
        "salt/state.py",
        "salt/fileclient.py",
        "salt/crypt.py",
        "salt/config.py",
        "salt/beacons",
        "salt/beacons/__init__.py",
        "salt/payload.py",
        "salt/output",
        "salt/output/__init__.py",
        "salt/output/nested.py",
    )

    for py_ver, tops in tops_py_version_mapping.items():
        for top in tops:
            base = os.path.basename(top)
            top_dirname = os.path.dirname(top)
            if os.path.isdir(top_dirname):
                os.chdir(top_dirname)
            else:
                # This is likely a compressed python .egg
                tempdir = tempfile.mkdtemp()
                egg = zipfile.ZipFile(top_dirname)
                egg.extractall(tempdir)
                top = os.path.join(tempdir, base)
                os.chdir(tempdir)
            if not os.path.isdir(top):
                # top is a single file module
                tfp.add(base, arcname=os.path.join("py{}".format(py_ver), base))
                continue
            for root, dirs, files in salt.utils.path.os_walk(base, followlinks=True):
                for name in files:
                    if name.endswith((".pyc", ".pyo")):
                        continue
                    if (
                        root.startswith("salt")
                        and os.path.join(root, name) not in min_files
                    ):
                        continue
                    tfp.add(
                        os.path.join(root, name),
                        arcname=os.path.join("py{}".format(py_ver), root, name),
                    )
            if tempdir is not None:
                shutil.rmtree(tempdir)
                tempdir = None

    os.chdir(mindir)
    tfp.add("salt-call")
    with salt.utils.files.fopen(minver, "w+") as fp_:
        fp_.write(salt.version.__version__)
    with salt.utils.files.fopen(pyminver, "w+") as fp_:
        fp_.write(str(sys.version_info[0]))
    os.chdir(os.path.dirname(minver))
    tfp.add("version")
    tfp.add(".min-gen-py-version")
    if start_dir:
        os.chdir(start_dir)
    tfp.close()
    return mintar


def min_sum(cachedir, form="sha1"):
    """
    Return the checksum of the current thin tarball
    """
    mintar = gen_min(cachedir)
    return salt.utils.hashutils.get_hash(mintar, form)

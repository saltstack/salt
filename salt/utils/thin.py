# -*- coding: utf-8 -*-
"""
Generate the salt thin tarball from the installed python files
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

# Import third party libs
import jinja2
import msgpack

# Import salt libs
import salt
import salt.exceptions
import salt.ext.six as _six
import salt.ext.tornado as tornado
import salt.utils.files
import salt.utils.hashutils
import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
import salt.version
import yaml

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
# pylint: enable=import-error,no-name-in-module


if _six.PY2:
    import concurrent
else:
    concurrent = None


log = logging.getLogger(__name__)


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


def get_ext_tops(config):
    """
    Get top directories for the dependencies, based on external configuration.

    :return:
    """
    config = copy.deepcopy(config)
    alternatives = {}
    required = ["jinja2", "yaml", "tornado", "msgpack"]
    tops = []
    for ns, cfg in salt.ext.six.iteritems(config or {}):
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
                raise salt.exceptions.SaltSystemExit(msg)
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
    for mod in [
        salt,
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
    ]:
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
                log.exception(err)
                log.error('Unable to import extra-module "%s"', mod)

    for mod in [m for m in so_mods.split(",") if m]:
        try:
            locals()[mod] = __import__(mod)
            tops.append(locals()[mod].__file__)
        except ImportError as err:
            log.exception(err)
            log.error('Unable to import so-module "%s"', mod)

    return tops


def _get_supported_py_config(tops, extended_cfg):
    """
    Based on the Salt SSH configuration, create a YAML configuration
    for the supported Python interpreter versions. This is then written into the thin.tgz
    archive and then verified by salt.client.ssh.ssh_py_shim.get_executable()

    Note: Minimum default of 2.x versions is 2.7 and 3.x is 3.0, unless specified in namespaces.

    :return:
    """
    pymap = []
    for py_ver, tops in _six.iteritems(copy.deepcopy(tops)):
        py_ver = int(py_ver)
        if py_ver == 2:
            pymap.append("py2:2:7")
        elif py_ver == 3:
            pymap.append("py3:3:0")

    for ns, cfg in _six.iteritems(copy.deepcopy(extended_cfg) or {}):
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


def gen_thin(
    cachedir,
    extra_mods="",
    overwrite=False,
    so_mods="",
    python2_bin="python2",
    python3_bin="python3",
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
    if sys.version_info < (2, 6):
        raise salt.exceptions.SaltSystemExit(
            'The minimum required python version to run salt-ssh is "2.6".'
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
                        overwrite = fh_.read() != str(
                            sys.version_info[0]
                        )  # future lint: disable=blacklisted-function
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
    if _six.PY3:
        # Let's check for the minimum python 2 version requirement, 2.6
        if not salt.utils.path.which(python2_bin):
            log.debug(
                "%s binary does not exist. Will not detect Python 2 version",
                python2_bin,
            )
        else:
            py_shell_cmd = "{} -c 'import sys;sys.stdout.write(\"%s.%s\\n\" % sys.version_info[:2]);'".format(
                python2_bin
            )
            cmd = subprocess.Popen(py_shell_cmd, stdout=subprocess.PIPE, shell=True)
            stdout, _ = cmd.communicate()
            if cmd.returncode == 0:
                py2_version = tuple(
                    int(n) for n in stdout.decode("utf-8").strip().split(".")
                )
                if py2_version < (2, 6):
                    raise salt.exceptions.SaltSystemExit(
                        'The minimum required python version to run salt-ssh is "2.6".'
                        'The version reported by "{0}" is "{1}". Please try "salt-ssh '
                        '--python2-bin=<path-to-python-2.6-binary-or-higher>".'.format(
                            python2_bin, stdout.strip()
                        )
                    )
            else:
                log.debug("Unable to detect %s version", python2_bin)
                log.debug(stdout)

    tops_failure_msg = "Failed %s tops for Python binary %s."
    python_check_msg = (
        "%s binary does not exist. Will not attempt to generate tops for Python %s"
    )
    tops_py_version_mapping = {}
    tops = get_tops(extra_mods=extra_mods, so_mods=so_mods)
    tops_py_version_mapping[sys.version_info.major] = tops

    # Collect tops, alternative to 2.x version
    if _six.PY2 and sys.version_info.major == 2:
        # Get python 3 tops
        if not salt.utils.path.which(python3_bin):
            log.debug(python_check_msg, python3_bin, "3")
        else:
            py_shell_cmd = "{0} -c 'import salt.utils.thin as t;print(t.gte())' '{1}'".format(
                python3_bin,
                salt.utils.json.dumps({"extra_mods": extra_mods, "so_mods": so_mods}),
            )
            cmd = subprocess.Popen(
                py_shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
            )
            stdout, stderr = cmd.communicate()
            if cmd.returncode == 0:
                try:
                    tops = salt.utils.json.loads(stdout)
                    tops_py_version_mapping["3"] = tops
                except ValueError as err:
                    log.error(tops_failure_msg, "parsing", python3_bin)
                    log.exception(err)
            else:
                log.debug(tops_failure_msg, "collecting", python3_bin)
                log.debug(stderr)

    # Collect tops, alternative to 3.x version
    if _six.PY3 and sys.version_info.major == 3:
        # Get python 2 tops
        if not salt.utils.path.which(python2_bin):
            log.debug(python_check_msg, python2_bin, "2")
        else:
            py_shell_cmd = "{0} -c 'import salt.utils.thin as t;print(t.gte())' '{1}'".format(
                python2_bin,
                salt.utils.json.dumps({"extra_mods": extra_mods, "so_mods": so_mods}),
            )
            cmd = subprocess.Popen(
                py_shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
            )
            stdout, stderr = cmd.communicate()
            if cmd.returncode == 0:
                try:
                    tops = salt.utils.json.loads(stdout.decode("utf-8"))
                    tops_py_version_mapping["2"] = tops
                except ValueError as err:
                    log.error(tops_failure_msg, "parsing", python2_bin)
                    log.exception(err)
            else:
                log.debug(tops_failure_msg, "collecting", python2_bin)
                log.debug(stderr)

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
    for py_ver, tops in _six.iteritems(tops_py_version_mapping):
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

    # Pack alternative data
    if extended_cfg:
        log.debug("Packing libraries based on alternative Salt versions")
    for ns, cfg in _six.iteritems(get_ext_tops(extended_cfg)):
        tops = [cfg.get("path")] + cfg.get("dependencies")
        py_ver_major, py_ver_minor = cfg.get("py-version")
        for top in tops:
            base, top_dirname = os.path.basename(top), os.path.dirname(top)
            os.chdir(top_dirname)
            site_pkg_dir = (
                _is_shareable(base) and "pyall" or "py{0}".format(py_ver_major)
            )
            log.debug(
                'Packing alternative "%s" to "%s/%s" destination',
                base,
                ns,
                site_pkg_dir,
            )
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

    os.chdir(thindir)
    with salt.utils.files.fopen(thinver, "w+") as fp_:
        fp_.write(salt.version.__version__)
    with salt.utils.files.fopen(pythinver, "w+") as fp_:
        fp_.write(
            str(sys.version_info.major)
        )  # future lint: disable=blacklisted-function
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

    if start_dir:
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
            code_checksum = "'{0}'".format(fh.read().strip())
    else:
        code_checksum = "'0'"

    return code_checksum, salt.utils.hashutils.get_hash(thintar, form)


def gen_min(
    cachedir,
    extra_mods="",
    overwrite=False,
    so_mods="",
    python2_bin="python2",
    python3_bin="python3",
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
                        overwrite = fh_.read() != str(
                            sys.version_info[0]
                        )  # future lint: disable=blacklisted-function
            else:
                overwrite = True

        if overwrite:
            try:
                os.remove(mintar)
            except OSError:
                pass
        else:
            return mintar
    if _six.PY3:
        # Let's check for the minimum python 2 version requirement, 2.6
        py_shell_cmd = (
            python2_bin + " -c 'from __future__ import print_function; import sys; "
            'print("{0}.{1}".format(*(sys.version_info[:2])));\''
        )
        cmd = subprocess.Popen(py_shell_cmd, stdout=subprocess.PIPE, shell=True)
        stdout, _ = cmd.communicate()
        if cmd.returncode == 0:
            py2_version = tuple(
                int(n) for n in stdout.decode("utf-8").strip().split(".")
            )
            if py2_version < (2, 6):
                # Bail!
                raise salt.exceptions.SaltSystemExit(
                    'The minimum required python version to run salt-ssh is "2.6".'
                    'The version reported by "{0}" is "{1}". Please try "salt-ssh '
                    '--python2-bin=<path-to-python-2.6-binary-or-higher>".'.format(
                        python2_bin, stdout.strip()
                    )
                )
    elif sys.version_info < (2, 6):
        # Bail! Though, how did we reached this far in the first place.
        raise salt.exceptions.SaltSystemExit(
            'The minimum required python version to run salt-ssh is "2.6".'
        )

    tops_py_version_mapping = {}
    tops = get_tops(extra_mods=extra_mods, so_mods=so_mods)
    if _six.PY2:
        tops_py_version_mapping["2"] = tops
    else:
        tops_py_version_mapping["3"] = tops

    # TODO: Consider putting known py2 and py3 compatible libs in it's own sharable directory.
    #       This would reduce the min size.
    if _six.PY2 and sys.version_info[0] == 2:
        # Get python 3 tops
        py_shell_cmd = (
            python3_bin + " -c 'import sys; import json; import salt.utils.thin; "
            "print(json.dumps(salt.utils.thin.get_tops(**(json.loads(sys.argv[1]))), ensure_ascii=False)); exit(0);' "
            "'{0}'".format(
                salt.utils.json.dumps({"extra_mods": extra_mods, "so_mods": so_mods})
            )
        )
        cmd = subprocess.Popen(
            py_shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        stdout, stderr = cmd.communicate()
        if cmd.returncode == 0:
            try:
                tops = salt.utils.json.loads(stdout)
                tops_py_version_mapping["3"] = tops
            except ValueError:
                pass
    if _six.PY3 and sys.version_info[0] == 3:
        # Get python 2 tops
        py_shell_cmd = (
            python2_bin + " -c 'from __future__ import print_function; "
            "import sys; import json; import salt.utils.thin; "
            "print(json.dumps(salt.utils.thin.get_tops(**(json.loads(sys.argv[1]))), ensure_ascii=False)); exit(0);' "
            "'{0}'".format(
                salt.utils.json.dumps({"extra_mods": extra_mods, "so_mods": so_mods})
            )
        )
        cmd = subprocess.Popen(
            py_shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        stdout, stderr = cmd.communicate()
        if cmd.returncode == 0:
            try:
                tops = salt.utils.json.loads(stdout.decode("utf-8"))
                tops_py_version_mapping["2"] = tops
            except ValueError:
                pass

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
        "salt/log",
        "salt/log/__init__.py",
        "salt/log/handlers",
        "salt/log/handlers/__init__.py",
        "salt/log/mixins.py",
        "salt/log/setup.py",
        "salt/cli",
        "salt/cli/__init__.py",
        "salt/cli/caller.py",
        "salt/cli/daemons.py",
        "salt/cli/salt.py",
        "salt/cli/call.py",
        "salt/fileserver",
        "salt/fileserver/__init__.py",
        "salt/transport",
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

    for py_ver, tops in _six.iteritems(tops_py_version_mapping):
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
                tfp.add(base, arcname=os.path.join("py{0}".format(py_ver), base))
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
                        arcname=os.path.join("py{0}".format(py_ver), root, name),
                    )
            if tempdir is not None:
                shutil.rmtree(tempdir)
                tempdir = None

    os.chdir(mindir)
    tfp.add("salt-call")
    with salt.utils.files.fopen(minver, "w+") as fp_:
        fp_.write(salt.version.__version__)
    with salt.utils.files.fopen(pyminver, "w+") as fp_:
        fp_.write(str(sys.version_info[0]))  # future lint: disable=blacklisted-function
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

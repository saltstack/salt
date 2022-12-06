"""
This module provides the point of entry to SPM, the Salt Package Manager

.. versionadded:: 2015.8.0
"""

import hashlib
import logging
import os
import shutil
import sys
import tarfile

import salt.cache
import salt.client
import salt.config
import salt.loader
import salt.syspaths as syspaths
import salt.utils.files
import salt.utils.http as http
import salt.utils.path
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from salt.template import compile_template

try:
    import grp
    import pwd
except ImportError:
    pass


log = logging.getLogger(__name__)

FILE_TYPES = ("c", "d", "g", "l", "r", "s", "m")
# c: config file
# d: documentation file
# g: ghost file (i.e. the file contents are not included in the package payload)
# l: license file
# r: readme file
# s: SLS file
# m: Salt module


class SPMException(Exception):
    """
    Base class for SPMClient exceptions
    """


class SPMInvocationError(SPMException):
    """
    Wrong number of arguments or other usage error
    """


class SPMPackageError(SPMException):
    """
    Problem with package file or package installation
    """


class SPMDatabaseError(SPMException):
    """
    SPM database not found, etc
    """


class SPMOperationCanceled(SPMException):
    """
    SPM install or uninstall was canceled
    """


class SPMClient:
    """
    Provide an SPM Client
    """

    def __init__(self, ui, opts=None):  # pylint: disable=W0231
        self.ui = ui
        if not opts:
            opts = salt.config.spm_config(os.path.join(syspaths.CONFIG_DIR, "spm"))
        self.opts = opts
        self.db_prov = self.opts.get("spm_db_provider", "sqlite3")
        self.files_prov = self.opts.get("spm_files_provider", "local")
        self._prep_pkgdb()
        self._prep_pkgfiles()
        self.db_conn = None
        self.files_conn = None
        self._init()

    def _prep_pkgdb(self):
        self.pkgdb = salt.loader.pkgdb(self.opts)

    def _prep_pkgfiles(self):
        self.pkgfiles = salt.loader.pkgfiles(self.opts)

    def _init(self):
        if not self.db_conn:
            self.db_conn = self._pkgdb_fun("init")
        if not self.files_conn:
            self.files_conn = self._pkgfiles_fun("init")

    def _close(self):
        if self.db_conn:
            self.db_conn.close()

    def run(self, args):
        """
        Run the SPM command
        """
        command = args[0]
        try:
            if command == "install":
                self._install(args)
            elif command == "local":
                self._local(args)
            elif command == "repo":
                self._repo(args)
            elif command == "remove":
                self._remove(args)
            elif command == "build":
                self._build(args)
            elif command == "update_repo":
                self._download_repo_metadata(args)
            elif command == "create_repo":
                self._create_repo(args)
            elif command == "files":
                self._list_files(args)
            elif command == "info":
                self._info(args)
            elif command == "list":
                self._list(args)
            elif command == "close":
                self._close()
            else:
                raise SPMInvocationError("Invalid command '{}'".format(command))
        except SPMException as exc:
            self.ui.error(str(exc))

    def _pkgdb_fun(self, func, *args, **kwargs):
        try:
            return getattr(getattr(self.pkgdb, self.db_prov), func)(*args, **kwargs)
        except AttributeError:
            return self.pkgdb["{}.{}".format(self.db_prov, func)](*args, **kwargs)

    def _pkgfiles_fun(self, func, *args, **kwargs):
        try:
            return getattr(getattr(self.pkgfiles, self.files_prov), func)(
                *args, **kwargs
            )
        except AttributeError:
            return self.pkgfiles["{}.{}".format(self.files_prov, func)](*args, **kwargs)

    def _list(self, args):
        """
        Process local commands
        """
        args.pop(0)
        command = args[0]
        if command == "packages":
            self._list_packages(args)
        elif command == "files":
            self._list_files(args)
        elif command == "repos":
            self._repo_list(args)
        else:
            raise SPMInvocationError("Invalid list command '{}'".format(command))

    def _local(self, args):
        """
        Process local commands
        """
        args.pop(0)
        command = args[0]
        if command == "install":
            self._local_install(args)
        elif command == "files":
            self._local_list_files(args)
        elif command == "info":
            self._local_info(args)
        else:
            raise SPMInvocationError("Invalid local command '{}'".format(command))

    def _repo(self, args):
        """
        Process repo commands
        """
        args.pop(0)
        command = args[0]
        if command == "list":
            self._repo_list(args)
        elif command == "packages":
            self._repo_packages(args)
        elif command == "search":
            self._repo_packages(args, search=True)
        elif command == "update":
            self._download_repo_metadata(args)
        elif command == "create":
            self._create_repo(args)
        else:
            raise SPMInvocationError("Invalid repo command '{}'".format(command))

    def _repo_packages(self, args, search=False):
        """
        List packages for one or more configured repos
        """
        packages = []
        repo_metadata = self._get_repo_metadata()
        for repo in repo_metadata:
            for pkg in repo_metadata[repo]["packages"]:
                if args[1] in pkg:
                    version = repo_metadata[repo]["packages"][pkg]["info"]["version"]
                    release = repo_metadata[repo]["packages"][pkg]["info"]["release"]
                    packages.append((pkg, version, release, repo))
        for pkg in sorted(packages):
            self.ui.status("{}\t{}-{}\t{}".format(pkg[0], pkg[1], pkg[2], pkg[3]))
        return packages

    def _repo_list(self, args):
        """
        List configured repos

        This can be called either as a ``repo`` command or a ``list`` command
        """
        repo_metadata = self._get_repo_metadata()
        for repo in repo_metadata:
            self.ui.status(repo)

    def _install(self, args):
        """
        Install a package from a repo
        """
        if len(args) < 2:
            raise SPMInvocationError("A package must be specified")

        caller_opts = self.opts.copy()
        caller_opts["file_client"] = "local"
        self.caller = salt.client.Caller(mopts=caller_opts)
        self.client = salt.client.get_local_client(self.opts["conf_file"])
        cache = salt.cache.Cache(self.opts)

        packages = args[1:]
        file_map = {}
        optional = []
        recommended = []
        to_install = []
        for pkg in packages:
            if pkg.endswith(".spm"):
                if self._pkgfiles_fun("path_exists", pkg):
                    comps = pkg.split("-")
                    comps = os.path.split("-".join(comps[:-2]))
                    pkg_name = comps[-1]

                    formula_tar = tarfile.open(pkg, "r:bz2")
                    formula_ref = formula_tar.extractfile("{}/FORMULA".format(pkg_name))
                    formula_def = salt.utils.yaml.safe_load(formula_ref)

                    file_map[pkg_name] = pkg
                    to_, op_, re_ = self._check_all_deps(
                        pkg_name=pkg_name, pkg_file=pkg, formula_def=formula_def
                    )
                    to_install.extend(to_)
                    optional.extend(op_)
                    recommended.extend(re_)
                    formula_tar.close()
                else:
                    raise SPMInvocationError("Package file {} not found".format(pkg))
            else:
                to_, op_, re_ = self._check_all_deps(pkg_name=pkg)
                to_install.extend(to_)
                optional.extend(op_)
                recommended.extend(re_)

        optional = set(filter(len, optional))
        if optional:
            self.ui.status(
                "The following dependencies are optional:\n\t{}\n".format(
                    "\n\t".join(optional)
                )
            )
        recommended = set(filter(len, recommended))
        if recommended:
            self.ui.status(
                "The following dependencies are recommended:\n\t{}\n".format(
                    "\n\t".join(recommended)
                )
            )

        to_install = set(filter(len, to_install))
        msg = "Installing packages:\n\t{}\n".format("\n\t".join(to_install))
        if not self.opts["assume_yes"]:
            self.ui.confirm(msg)

        repo_metadata = self._get_repo_metadata()

        dl_list = {}
        for package in to_install:
            if package in file_map:
                self._install_indv_pkg(package, file_map[package])
            else:
                for repo in repo_metadata:
                    repo_info = repo_metadata[repo]
                    if package in repo_info["packages"]:
                        dl_package = False
                        repo_ver = repo_info["packages"][package]["info"]["version"]
                        repo_rel = repo_info["packages"][package]["info"]["release"]
                        repo_url = repo_info["info"]["url"]
                        if package in dl_list:
                            # Check package version, replace if newer version
                            if repo_ver == dl_list[package]["version"]:
                                # Version is the same, check release
                                if repo_rel > dl_list[package]["release"]:
                                    dl_package = True
                                elif repo_rel == dl_list[package]["release"]:
                                    # Version and release are the same, give
                                    # preference to local (file://) repos
                                    if dl_list[package]["source"].startswith("file://"):
                                        if not repo_url.startswith("file://"):
                                            dl_package = True
                            elif repo_ver > dl_list[package]["version"]:
                                dl_package = True
                        else:
                            dl_package = True

                        if dl_package is True:
                            # Put together download directory
                            cache_path = os.path.join(self.opts["spm_cache_dir"], repo)

                            # Put together download paths
                            dl_url = "{}/{}".format(
                                repo_info["info"]["url"],
                                repo_info["packages"][package]["filename"],
                            )
                            out_file = os.path.join(
                                cache_path, repo_info["packages"][package]["filename"]
                            )
                            dl_list[package] = {
                                "version": repo_ver,
                                "release": repo_rel,
                                "source": dl_url,
                                "dest_dir": cache_path,
                                "dest_file": out_file,
                            }

        for package in dl_list:
            dl_url = dl_list[package]["source"]
            cache_path = dl_list[package]["dest_dir"]
            out_file = dl_list[package]["dest_file"]

            # Make sure download directory exists
            if not os.path.exists(cache_path):
                os.makedirs(cache_path)

            # Download the package
            if dl_url.startswith("file://"):
                dl_url = dl_url.replace("file://", "")
                shutil.copyfile(dl_url, out_file)
            else:
                with salt.utils.files.fopen(out_file, "wb") as outf:
                    outf.write(
                        self._query_http(dl_url, repo_info["info"], decode_body=False)
                    )

        # First we download everything, then we install
        for package in dl_list:
            out_file = dl_list[package]["dest_file"]
            # Kick off the install
            self._install_indv_pkg(package, out_file)
        return

    def _local_install(self, args, pkg_name=None):
        """
        Install a package from a file
        """
        if len(args) < 2:
            raise SPMInvocationError("A package file must be specified")

        self._install(args)

    def _check_all_deps(self, pkg_name=None, pkg_file=None, formula_def=None):
        """
        Starting with one package, check all packages for dependencies
        """
        if pkg_file and not os.path.exists(pkg_file):
            raise SPMInvocationError("Package file {} not found".format(pkg_file))

        self.repo_metadata = self._get_repo_metadata()
        if not formula_def:
            for repo in self.repo_metadata:
                if not isinstance(self.repo_metadata[repo]["packages"], dict):
                    continue
                if pkg_name in self.repo_metadata[repo]["packages"]:
                    formula_def = self.repo_metadata[repo]["packages"][pkg_name]["info"]

        if not formula_def:
            raise SPMInvocationError("Unable to read formula for {}".format(pkg_name))

        # Check to see if the package is already installed
        pkg_info = self._pkgdb_fun("info", pkg_name, self.db_conn)
        pkgs_to_install = []
        if pkg_info is None or self.opts["force"]:
            pkgs_to_install.append(pkg_name)
        elif pkg_info is not None and not self.opts["force"]:
            raise SPMPackageError(
                "Package {} already installed, not installing again".format(
                    formula_def["name"]
                )
            )

        optional_install = []
        recommended_install = []
        if (
            "dependencies" in formula_def
            or "optional" in formula_def
            or "recommended" in formula_def
        ):
            self.avail_pkgs = {}
            for repo in self.repo_metadata:
                if not isinstance(self.repo_metadata[repo]["packages"], dict):
                    continue
                for pkg in self.repo_metadata[repo]["packages"]:
                    self.avail_pkgs[pkg] = repo

            needs, unavail, optional, recommended = self._resolve_deps(formula_def)

            if len(unavail) > 0:
                raise SPMPackageError(
                    "Cannot install {}, the following dependencies are needed:\n\n{}".format(
                        formula_def["name"], "\n".join(unavail)
                    )
                )

            if optional:
                optional_install.extend(optional)
                for dep_pkg in optional:
                    pkg_info = self._pkgdb_fun("info", formula_def["name"])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = "{} [Installed]".format(dep_pkg)
                    optional_install.append(msg)

            if recommended:
                recommended_install.extend(recommended)
                for dep_pkg in recommended:
                    pkg_info = self._pkgdb_fun("info", formula_def["name"])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = "{} [Installed]".format(dep_pkg)
                    recommended_install.append(msg)

            if needs:
                pkgs_to_install.extend(needs)
                for dep_pkg in needs:
                    pkg_info = self._pkgdb_fun("info", formula_def["name"])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = "{} [Installed]".format(dep_pkg)

        return pkgs_to_install, optional_install, recommended_install

    def _install_indv_pkg(self, pkg_name, pkg_file):
        """
        Install one individual package
        """
        self.ui.status("... installing {}".format(pkg_name))
        formula_tar = tarfile.open(pkg_file, "r:bz2")
        formula_ref = formula_tar.extractfile("{}/FORMULA".format(pkg_name))
        formula_def = salt.utils.yaml.safe_load(formula_ref)

        for field in ("version", "release", "summary", "description"):
            if field not in formula_def:
                raise SPMPackageError(
                    "Invalid package: the {} was not found".format(field)
                )

        pkg_files = formula_tar.getmembers()

        # First pass: check for files that already exist
        existing_files = self._pkgfiles_fun(
            "check_existing", pkg_name, pkg_files, formula_def
        )

        if existing_files and not self.opts["force"]:
            raise SPMPackageError(
                "Not installing {} due to existing files:\n\n{}".format(
                    pkg_name, "\n".join(existing_files)
                )
            )

        # We've decided to install
        self._pkgdb_fun("register_pkg", pkg_name, formula_def, self.db_conn)

        # Run the pre_local_state script, if present
        if "pre_local_state" in formula_def:
            high_data = self._render(formula_def["pre_local_state"], formula_def)
            ret = self.caller.cmd("state.high", data=high_data)
        if "pre_tgt_state" in formula_def:
            log.debug("Executing pre_tgt_state script")
            high_data = self._render(formula_def["pre_tgt_state"]["data"], formula_def)
            tgt = formula_def["pre_tgt_state"]["tgt"]
            ret = self.client.run_job(
                tgt=formula_def["pre_tgt_state"]["tgt"],
                fun="state.high",
                tgt_type=formula_def["pre_tgt_state"].get("tgt_type", "glob"),
                timout=self.opts["timeout"],
                data=high_data,
            )

        # No defaults for this in config.py; default to the current running
        # user and group
        if salt.utils.platform.is_windows():
            uname = gname = salt.utils.win_functions.get_current_user()
            uname_sid = salt.utils.win_functions.get_sid_from_name(uname)
            uid = self.opts.get("spm_uid", uname_sid)
            gid = self.opts.get("spm_gid", uname_sid)
        else:
            uid = self.opts.get("spm_uid", os.getuid())
            gid = self.opts.get("spm_gid", os.getgid())
            uname = pwd.getpwuid(uid)[0]
            gname = grp.getgrgid(gid)[0]

        # Second pass: install the files
        for member in pkg_files:
            member.uid = uid
            member.gid = gid
            member.uname = uname
            member.gname = gname

            out_path = self._pkgfiles_fun(
                "install_file",
                pkg_name,
                formula_tar,
                member,
                formula_def,
                self.files_conn,
            )
            if out_path is not False:
                if member.isdir():
                    digest = ""
                else:
                    self._verbose(
                        "Installing file {} to {}".format(member.name, out_path),
                        log.trace,
                    )
                    file_hash = hashlib.sha1()
                    digest = self._pkgfiles_fun(
                        "hash_file",
                        os.path.join(out_path, member.name),
                        file_hash,
                        self.files_conn,
                    )
                self._pkgdb_fun(
                    "register_file", pkg_name, member, out_path, digest, self.db_conn
                )

        # Run the post_local_state script, if present
        if "post_local_state" in formula_def:
            log.debug("Executing post_local_state script")
            high_data = self._render(formula_def["post_local_state"], formula_def)
            self.caller.cmd("state.high", data=high_data)
        if "post_tgt_state" in formula_def:
            log.debug("Executing post_tgt_state script")
            high_data = self._render(formula_def["post_tgt_state"]["data"], formula_def)
            tgt = formula_def["post_tgt_state"]["tgt"]
            ret = self.client.run_job(
                tgt=formula_def["post_tgt_state"]["tgt"],
                fun="state.high",
                tgt_type=formula_def["post_tgt_state"].get("tgt_type", "glob"),
                timout=self.opts["timeout"],
                data=high_data,
            )

        formula_tar.close()

    def _resolve_deps(self, formula_def):
        """
        Return a list of packages which need to be installed, to resolve all
        dependencies
        """
        pkg_info = self.pkgdb["{}.info".format(self.db_prov)](formula_def["name"])
        if not isinstance(pkg_info, dict):
            pkg_info = {}

        can_has = {}
        cant_has = []
        if "dependencies" in formula_def and formula_def["dependencies"] is None:
            formula_def["dependencies"] = ""
        for dep in formula_def.get("dependencies", "").split(","):
            dep = dep.strip()
            if not dep:
                continue
            if self.pkgdb["{}.info".format(self.db_prov)](dep):
                continue

            if dep in self.avail_pkgs:
                can_has[dep] = self.avail_pkgs[dep]
            else:
                cant_has.append(dep)

        optional = formula_def.get("optional", "").split(",")
        recommended = formula_def.get("recommended", "").split(",")

        inspected = []
        to_inspect = can_has.copy()
        while len(to_inspect) > 0:
            dep = next(iter(to_inspect.keys()))
            del to_inspect[dep]

            # Don't try to resolve the same package more than once
            if dep in inspected:
                continue
            inspected.append(dep)

            repo_contents = self.repo_metadata.get(can_has[dep], {})
            repo_packages = repo_contents.get("packages", {})
            dep_formula = repo_packages.get(dep, {}).get("info", {})

            also_can, also_cant, opt_dep, rec_dep = self._resolve_deps(dep_formula)
            can_has.update(also_can)
            cant_has = sorted(set(cant_has + also_cant))
            optional = sorted(set(optional + opt_dep))
            recommended = sorted(set(recommended + rec_dep))

        return can_has, cant_has, optional, recommended

    def _traverse_repos(self, callback, repo_name=None):
        """
        Traverse through all repo files and apply the functionality provided in
        the callback to them
        """
        repo_files = []
        if os.path.exists(self.opts["spm_repos_config"]):
            repo_files.append(self.opts["spm_repos_config"])

        for (dirpath, dirnames, filenames) in salt.utils.path.os_walk(
            "{}.d".format(self.opts["spm_repos_config"])
        ):
            for repo_file in filenames:
                if not repo_file.endswith(".repo"):
                    continue
                repo_files.append(repo_file)

        for repo_file in repo_files:
            repo_path = "{}.d/{}".format(self.opts["spm_repos_config"], repo_file)
            with salt.utils.files.fopen(repo_path) as rph:
                repo_data = salt.utils.yaml.safe_load(rph)
                for repo in repo_data:
                    if repo_data[repo].get("enabled", True) is False:
                        continue
                    if repo_name is not None and repo != repo_name:
                        continue
                    callback(repo, repo_data[repo])

    def _query_http(self, dl_path, repo_info, decode_body=True):
        """
        Download files via http
        """
        query = None
        response = None

        try:
            if "username" in repo_info:
                try:
                    if "password" in repo_info:
                        query = http.query(
                            dl_path,
                            text=True,
                            username=repo_info["username"],
                            password=repo_info["password"],
                            decode_body=decode_body,
                        )
                    else:
                        raise SPMException(
                            "Auth defined, but password is not set for username: '{}'".format(
                                repo_info["username"]
                            )
                        )
                except SPMException as exc:
                    self.ui.error(str(exc))
            else:
                query = http.query(dl_path, text=True, decode_body=decode_body)
        except SPMException as exc:
            self.ui.error(str(exc))

        try:
            if query:
                if "SPM-METADATA" in dl_path:
                    response = salt.utils.yaml.safe_load(query.get("text", "{}"))
                else:
                    response = query.get("text")
            else:
                raise SPMException("Response is empty, please check for Errors above.")
        except SPMException as exc:
            self.ui.error(str(exc))

        return response

    def _download_repo_metadata(self, args):
        """
        Connect to all repos and download metadata
        """
        cache = salt.cache.Cache(self.opts, self.opts["spm_cache_dir"])

        def _update_metadata(repo, repo_info):
            dl_path = "{}/SPM-METADATA".format(repo_info["url"])
            if dl_path.startswith("file://"):
                dl_path = dl_path.replace("file://", "")
                with salt.utils.files.fopen(dl_path, "r") as rpm:
                    metadata = salt.utils.yaml.safe_load(rpm)
            else:
                metadata = self._query_http(dl_path, repo_info)

            cache.store(".", repo, metadata)

        repo_name = args[1] if len(args) > 1 else None
        self._traverse_repos(_update_metadata, repo_name)

    def _get_repo_metadata(self):
        """
        Return cached repo metadata
        """
        cache = salt.cache.Cache(self.opts, self.opts["spm_cache_dir"])
        metadata = {}

        def _read_metadata(repo, repo_info):
            if cache.updated(".", repo) is None:
                log.warning("Updating repo metadata")
                self._download_repo_metadata({})

            metadata[repo] = {
                "info": repo_info,
                "packages": cache.fetch(".", repo),
            }

        self._traverse_repos(_read_metadata)
        return metadata

    def _create_repo(self, args):
        """
        Scan a directory and create an SPM-METADATA file which describes
        all of the SPM files in that directory.
        """
        if len(args) < 2:
            raise SPMInvocationError("A path to a directory must be specified")

        if args[1] == ".":
            repo_path = os.getcwd()
        else:
            repo_path = args[1]

        old_files = []
        repo_metadata = {}
        for (dirpath, dirnames, filenames) in salt.utils.path.os_walk(repo_path):
            for spm_file in filenames:
                if not spm_file.endswith(".spm"):
                    continue
                spm_path = "{}/{}".format(repo_path, spm_file)
                if not tarfile.is_tarfile(spm_path):
                    continue
                comps = spm_file.split("-")
                spm_name = "-".join(comps[:-2])
                spm_fh = tarfile.open(spm_path, "r:bz2")
                formula_handle = spm_fh.extractfile("{}/FORMULA".format(spm_name))
                formula_conf = salt.utils.yaml.safe_load(formula_handle.read())

                use_formula = True
                if spm_name in repo_metadata:
                    # This package is already in the repo; use the latest
                    cur_info = repo_metadata[spm_name]["info"]
                    new_info = formula_conf
                    if int(new_info["version"]) == int(cur_info["version"]):
                        # Version is the same, check release
                        if int(new_info["release"]) < int(cur_info["release"]):
                            # This is an old release; don't use it
                            use_formula = False
                    elif int(new_info["version"]) < int(cur_info["version"]):
                        # This is an old version; don't use it
                        use_formula = False

                    if use_formula is True:
                        # Ignore/archive/delete the old version
                        log.debug(
                            "%s %s-%s had been added, but %s-%s will replace it",
                            spm_name,
                            cur_info["version"],
                            cur_info["release"],
                            new_info["version"],
                            new_info["release"],
                        )
                        old_files.append(repo_metadata[spm_name]["filename"])
                    else:
                        # Ignore/archive/delete the new version
                        log.debug(
                            "%s %s-%s has been found, but is older than %s-%s",
                            spm_name,
                            new_info["version"],
                            new_info["release"],
                            cur_info["version"],
                            cur_info["release"],
                        )
                        old_files.append(spm_file)

                if use_formula is True:
                    log.debug(
                        "adding %s-%s-%s to the repo",
                        formula_conf["name"],
                        formula_conf["version"],
                        formula_conf["release"],
                    )
                    repo_metadata[spm_name] = {
                        "info": formula_conf.copy(),
                    }
                    repo_metadata[spm_name]["filename"] = spm_file

        metadata_filename = "{}/SPM-METADATA".format(repo_path)
        with salt.utils.files.fopen(metadata_filename, "w") as mfh:
            salt.utils.yaml.safe_dump(
                repo_metadata,
                mfh,
                indent=4,
                canonical=False,
                default_flow_style=False,
            )

        log.debug("Wrote %s", metadata_filename)

        for file_ in old_files:
            if self.opts["spm_repo_dups"] == "ignore":
                # ignore old packages, but still only add the latest
                log.debug("%s will be left in the directory", file_)
            elif self.opts["spm_repo_dups"] == "archive":
                # spm_repo_archive_path is where old packages are moved
                if not os.path.exists("./archive"):
                    try:
                        os.makedirs("./archive")
                        log.debug("%s has been archived", file_)
                    except OSError:
                        log.error("Unable to create archive directory")
                try:
                    shutil.move(file_, "./archive")
                except OSError:
                    log.error("Unable to archive %s", file_)
            elif self.opts["spm_repo_dups"] == "delete":
                # delete old packages from the repo
                try:
                    os.remove(file_)
                    log.debug("%s has been deleted", file_)
                except OSError:
                    log.error("Unable to delete %s", file_)
                except OSError:  # pylint: disable=duplicate-except
                    # The file has already been deleted
                    pass

    def _remove(self, args):
        """
        Remove a package
        """
        if len(args) < 2:
            raise SPMInvocationError("A package must be specified")

        packages = args[1:]
        msg = "Removing packages:\n\t{}".format("\n\t".join(packages))

        if not self.opts["assume_yes"]:
            self.ui.confirm(msg)

        for package in packages:
            self.ui.status("... removing {}".format(package))

            if not self._pkgdb_fun("db_exists", self.opts["spm_db"]):
                raise SPMDatabaseError(
                    "No database at {}, cannot remove {}".format(
                        self.opts["spm_db"], package
                    )
                )

            # Look at local repo index
            pkg_info = self._pkgdb_fun("info", package, self.db_conn)
            if pkg_info is None:
                raise SPMInvocationError("Package {} not installed".format(package))

            # Find files that have not changed and remove them
            files = self._pkgdb_fun("list_files", package, self.db_conn)
            dirs = []
            for filerow in files:
                if self._pkgfiles_fun("path_isdir", filerow[0]):
                    dirs.append(filerow[0])
                    continue
                file_hash = hashlib.sha1()
                digest = self._pkgfiles_fun(
                    "hash_file", filerow[0], file_hash, self.files_conn
                )
                if filerow[1] == digest:
                    self._verbose("Removing file {}".format(filerow[0]), log.trace)
                    self._pkgfiles_fun("remove_file", filerow[0], self.files_conn)
                else:
                    self._verbose("Not removing file {}".format(filerow[0]), log.trace)
                self._pkgdb_fun("unregister_file", filerow[0], package, self.db_conn)

            # Clean up directories
            for dir_ in sorted(dirs, reverse=True):
                self._pkgdb_fun("unregister_file", dir_, package, self.db_conn)
                try:
                    self._verbose("Removing directory {}".format(dir_), log.trace)
                    os.rmdir(dir_)
                except OSError:
                    # Leave directories in place that still have files in them
                    self._verbose(
                        "Cannot remove directory {}, probably not empty".format(dir_),
                        log.trace,
                    )

            self._pkgdb_fun("unregister_pkg", package, self.db_conn)

    def _verbose(self, msg, level=log.debug):
        """
        Display verbose information
        """
        if self.opts.get("verbose", False) is True:
            self.ui.status(msg)
        level(msg)

    def _local_info(self, args):
        """
        List info for a package file
        """
        if len(args) < 2:
            raise SPMInvocationError("A package filename must be specified")

        pkg_file = args[1]

        if not os.path.exists(pkg_file):
            raise SPMInvocationError("Package file {} not found".format(pkg_file))

        comps = pkg_file.split("-")
        comps = "-".join(comps[:-2]).split("/")
        name = comps[-1]

        formula_tar = tarfile.open(pkg_file, "r:bz2")
        formula_ref = formula_tar.extractfile("{}/FORMULA".format(name))
        formula_def = salt.utils.yaml.safe_load(formula_ref)

        self.ui.status(self._get_info(formula_def))
        formula_tar.close()

    def _info(self, args):
        """
        List info for a package
        """
        if len(args) < 2:
            raise SPMInvocationError("A package must be specified")

        package = args[1]

        pkg_info = self._pkgdb_fun("info", package, self.db_conn)
        if pkg_info is None:
            raise SPMPackageError("package {} not installed".format(package))
        self.ui.status(self._get_info(pkg_info))

    def _get_info(self, formula_def):
        """
        Get package info
        """
        fields = (
            "name",
            "os",
            "os_family",
            "release",
            "version",
            "dependencies",
            "os_dependencies",
            "os_family_dependencies",
            "summary",
            "description",
        )
        for item in fields:
            if item not in formula_def:
                formula_def[item] = "None"

        if "installed" not in formula_def:
            formula_def["installed"] = "Not installed"

        return (
            "Name: {name}\n"
            "Version: {version}\n"
            "Release: {release}\n"
            "Install Date: {installed}\n"
            "Supported OSes: {os}\n"
            "Supported OS families: {os_family}\n"
            "Dependencies: {dependencies}\n"
            "OS Dependencies: {os_dependencies}\n"
            "OS Family Dependencies: {os_family_dependencies}\n"
            "Summary: {summary}\n"
            "Description:\n"
            "{description}".format(**formula_def)
        )

    def _local_list_files(self, args):
        """
        List files for a package file
        """
        if len(args) < 2:
            raise SPMInvocationError("A package filename must be specified")

        pkg_file = args[1]
        if not os.path.exists(pkg_file):
            raise SPMPackageError("Package file {} not found".format(pkg_file))
        formula_tar = tarfile.open(pkg_file, "r:bz2")
        pkg_files = formula_tar.getmembers()

        for member in pkg_files:
            self.ui.status(member.name)

    def _list_packages(self, args):
        """
        List files for an installed package
        """
        packages = self._pkgdb_fun("list_packages", self.db_conn)
        for package in packages:
            if self.opts["verbose"]:
                status_msg = ",".join(package)
            else:
                status_msg = package[0]
            self.ui.status(status_msg)

    def _list_files(self, args):
        """
        List files for an installed package
        """
        if len(args) < 2:
            raise SPMInvocationError("A package name must be specified")

        package = args[-1]

        files = self._pkgdb_fun("list_files", package, self.db_conn)
        if files is None:
            raise SPMPackageError("package {} not installed".format(package))
        else:
            for file_ in files:
                if self.opts["verbose"]:
                    status_msg = ",".join(file_)
                else:
                    status_msg = file_[0]
                self.ui.status(status_msg)

    def _build(self, args):
        """
        Build a package
        """
        if len(args) < 2:
            raise SPMInvocationError("A path to a formula must be specified")

        self.abspath = args[1].rstrip("/")
        comps = self.abspath.split("/")
        self.relpath = comps[-1]

        formula_path = "{}/FORMULA".format(self.abspath)
        if not os.path.exists(formula_path):
            raise SPMPackageError("Formula file {} not found".format(formula_path))
        with salt.utils.files.fopen(formula_path) as fp_:
            formula_conf = salt.utils.yaml.safe_load(fp_)

        for field in ("name", "version", "release", "summary", "description"):
            if field not in formula_conf:
                raise SPMPackageError(
                    "Invalid package: a {} must be defined".format(field)
                )

        out_path = "{}/{}-{}-{}.spm".format(
            self.opts["spm_build_dir"],
            formula_conf["name"],
            formula_conf["version"],
            formula_conf["release"],
        )

        if not os.path.exists(self.opts["spm_build_dir"]):
            os.mkdir(self.opts["spm_build_dir"])

        self.formula_conf = formula_conf

        formula_tar = tarfile.open(out_path, "w:bz2")

        if "files" in formula_conf:
            # This allows files to be added to the SPM file in a specific order.
            # It also allows for files to be tagged as a certain type, as with
            # RPM files. This tag is ignored here, but is used when installing
            # the SPM file.
            if isinstance(formula_conf["files"], list):
                formula_dir = tarfile.TarInfo(formula_conf["name"])
                formula_dir.type = tarfile.DIRTYPE
                formula_tar.addfile(formula_dir)
                for file_ in formula_conf["files"]:
                    for ftype in FILE_TYPES:
                        if file_.startswith("{}|".format(ftype)):
                            file_ = file_.lstrip("{}|".format(ftype))
                    formula_tar.add(
                        os.path.join(os.getcwd(), file_),
                        os.path.join(formula_conf["name"], file_),
                    )
        else:
            # If no files are specified, then the whole directory will be added.
            try:
                formula_tar.add(
                    formula_path, formula_conf["name"], filter=self._exclude
                )
                formula_tar.add(
                    self.abspath, formula_conf["name"], filter=self._exclude
                )
            except TypeError:
                formula_tar.add(
                    formula_path, formula_conf["name"], exclude=self._exclude
                )
                formula_tar.add(
                    self.abspath, formula_conf["name"], exclude=self._exclude
                )
        formula_tar.close()

        self.ui.status("Built package {}".format(out_path))

    def _exclude(self, member):
        """
        Exclude based on opts
        """
        if isinstance(member, str):
            return None

        for item in self.opts["spm_build_exclude"]:
            if member.name.startswith("{}/{}".format(self.formula_conf["name"], item)):
                return None
            elif member.name.startswith("{}/{}".format(self.abspath, item)):
                return None
        return member

    def _render(self, data, formula_def):
        """
        Render a [pre|post]_local_state or [pre|post]_tgt_state script
        """
        # FORMULA can contain a renderer option
        renderer = formula_def.get("renderer", self.opts.get("renderer", "jinja|yaml"))
        rend = salt.loader.render(self.opts, {})
        blacklist = self.opts.get("renderer_blacklist")
        whitelist = self.opts.get("renderer_whitelist")
        template_vars = formula_def.copy()
        template_vars["opts"] = self.opts.copy()
        return compile_template(
            ":string:",
            rend,
            renderer,
            blacklist,
            whitelist,
            input_data=data,
            **template_vars
        )


class SPMUserInterface:
    """
    Handle user interaction with an SPMClient object
    """

    def status(self, msg):
        """
        Report an SPMClient status message
        """
        raise NotImplementedError()

    def error(self, msg):
        """
        Report an SPM error message
        """
        raise NotImplementedError()

    def confirm(self, action):
        """
        Get confirmation from the user before performing an SPMClient action.
        Return if the action is confirmed, or raise SPMOperationCanceled(<msg>)
        if canceled.
        """
        raise NotImplementedError()


class SPMCmdlineInterface(SPMUserInterface):
    """
    Command-line interface to SPMClient
    """

    def status(self, msg):
        print(msg)

    def error(self, msg):
        print(msg, file=sys.stderr)

    def confirm(self, action):
        print(action)
        res = input("Proceed? [N/y] ")
        if not res.lower().startswith("y"):
            raise SPMOperationCanceled("canceled")

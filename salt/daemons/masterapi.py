"""
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
"""

import fnmatch
import logging
import os
import re
import stat
import time

import salt.acl
import salt.auth
import salt.cache
import salt.client
import salt.crypt
import salt.exceptions
import salt.fileserver
import salt.key
import salt.minion
import salt.payload
import salt.pillar
import salt.runner
import salt.state
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.dictupdate
import salt.utils.event
import salt.utils.files
import salt.utils.gitfs
import salt.utils.gzip_util
import salt.utils.jid
import salt.utils.mine
import salt.utils.minions
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.user
import salt.utils.verify
import salt.wheel
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.pillar import git_pillar

try:
    import pwd

    HAS_PWD = True
except ImportError:
    # pwd is not available on windows
    HAS_PWD = False

log = logging.getLogger(__name__)

# Things to do in lower layers:
# only accept valid minion ids


def init_git_pillar(opts):
    """
    Clear out the ext pillar caches, used when the master starts
    """
    ret = []
    for opts_dict in [x for x in opts.get("ext_pillar", [])]:
        if "git" in opts_dict:
            try:
                pillar = salt.utils.gitfs.GitPillar(
                    opts,
                    opts_dict["git"],
                    per_remote_overrides=git_pillar.PER_REMOTE_OVERRIDES,
                    per_remote_only=git_pillar.PER_REMOTE_ONLY,
                    global_only=git_pillar.GLOBAL_ONLY,
                )
                ret.append(pillar)
            except salt.exceptions.FileserverConfigError:
                if opts.get("git_pillar_verify_config", True):
                    raise
                else:
                    log.critical("Could not initialize git_pillar")
    return ret


def clean_fsbackend(opts):
    """
    Clean out the old fileserver backends
    """
    # Clear remote fileserver backend caches so they get recreated
    for backend in ("git", "hg", "svn"):
        if backend in opts["fileserver_backend"]:
            env_cache = os.path.join(opts["cachedir"], "{}fs".format(backend), "envs.p")
            if os.path.isfile(env_cache):
                log.debug("Clearing %sfs env cache", backend)
                try:
                    os.remove(env_cache)
                except OSError as exc:
                    log.critical(
                        "Unable to clear env cache file %s: %s", env_cache, exc
                    )

            file_lists_dir = os.path.join(
                opts["cachedir"], "file_lists", "{}fs".format(backend)
            )
            try:
                file_lists_caches = os.listdir(file_lists_dir)
            except OSError:
                continue
            for file_lists_cache in fnmatch.filter(file_lists_caches, "*.p"):
                cache_file = os.path.join(file_lists_dir, file_lists_cache)
                try:
                    os.remove(cache_file)
                except OSError as exc:
                    log.critical(
                        "Unable to file_lists cache file %s: %s", cache_file, exc
                    )


def clean_expired_tokens(opts):
    """
    Clean expired tokens from the master
    """
    loadauth = salt.auth.LoadAuth(opts)
    for tok in loadauth.list_tokens():
        token_data = loadauth.get_tok(tok)
        if "expire" not in token_data or token_data.get("expire", 0) < time.time():
            loadauth.rm_token(tok)


def clean_pub_auth(opts):
    try:
        auth_cache = os.path.join(opts["cachedir"], "publish_auth")
        if not os.path.exists(auth_cache):
            return
        else:
            for (dirpath, dirnames, filenames) in salt.utils.path.os_walk(auth_cache):
                for auth_file in filenames:
                    auth_file_path = os.path.join(dirpath, auth_file)
                    if not os.path.isfile(auth_file_path):
                        continue
                    if time.time() - os.path.getmtime(auth_file_path) > (
                        opts["keep_jobs"] * 3600
                    ):
                        os.remove(auth_file_path)
    except OSError:
        log.error("Unable to delete pub auth file")


def clean_old_jobs(opts):
    """
    Clean out the old jobs from the job cache
    """
    # TODO: better way to not require creating the masterminion every time?
    mminion = salt.minion.MasterMinion(
        opts,
        states=False,
        rend=False,
    )
    # If the master job cache has a clean_old_jobs, call it
    fstr = "{}.clean_old_jobs".format(opts["master_job_cache"])
    if fstr in mminion.returners:
        mminion.returners[fstr]()


def mk_key(opts, user):
    if HAS_PWD:
        uid = None
        try:
            uid = pwd.getpwnam(user).pw_uid
        except KeyError:
            # User doesn't exist in the system
            if opts["client_acl_verify"]:
                return None
    if salt.utils.platform.is_windows():
        # The username may contain '\' if it is in Windows
        # 'DOMAIN\username' format. Fix this for the keyfile path.
        keyfile = os.path.join(
            opts["cachedir"], ".{}_key".format(user.replace("\\", "_"))
        )
    else:
        keyfile = os.path.join(opts["cachedir"], ".{}_key".format(user))

    if os.path.exists(keyfile):
        log.debug("Removing stale keyfile: %s", keyfile)
        if salt.utils.platform.is_windows() and not os.access(keyfile, os.W_OK):
            # Cannot delete read-only files on Windows.
            os.chmod(keyfile, stat.S_IRUSR | stat.S_IWUSR)
        os.unlink(keyfile)

    key = salt.crypt.Crypticle.generate_key_string()
    with salt.utils.files.set_umask(0o277):
        with salt.utils.files.fopen(keyfile, "w+") as fp_:
            fp_.write(salt.utils.stringutils.to_str(key))
    # 600 octal: Read and write access to the owner only.
    # Write access is necessary since on subsequent runs, if the file
    # exists, it needs to be written to again. Windows enforces this.
    os.chmod(keyfile, 0o600)
    if HAS_PWD and uid is not None:
        try:
            os.chown(keyfile, uid, -1)
        except OSError:
            # The master is not being run as root and can therefore not
            # chown the key file
            pass
    return key


def access_keys(opts):
    """
    A key needs to be placed in the filesystem with permissions 0400 so
    clients are required to run as root.
    """
    # TODO: Need a way to get all available users for systems not supported by pwd module.
    #       For now users pattern matching will not work for publisher_acl.
    keys = {}
    publisher_acl = opts["publisher_acl"]
    acl_users = set(publisher_acl.keys())
    if opts.get("user"):
        acl_users.add(opts["user"])
    acl_users.add(salt.utils.user.get_user())
    for user in acl_users:
        log.info("Preparing the %s key for local communication", user)
        key = mk_key(opts, user)
        if key is not None:
            keys[user] = key

    # Check other users matching ACL patterns
    if opts["client_acl_verify"] and HAS_PWD:
        log.profile("Beginning pwd.getpwall() call in masterapi access_keys function")
        for user in pwd.getpwall():
            user = user.pw_name
            if user not in keys and salt.utils.stringutils.check_whitelist_blacklist(
                user, whitelist=acl_users
            ):
                keys[user] = mk_key(opts, user)
        log.profile("End pwd.getpwall() call in masterapi access_keys function")

    return keys


def fileserver_update(fileserver):
    """
    Update the fileserver backends, requires that a salt.fileserver.Fileserver
    object be passed in
    """
    try:
        if not fileserver.servers:
            log.error(
                "No fileservers loaded, the master will not be able to "
                "serve files to minions"
            )
            raise salt.exceptions.SaltMasterError("No fileserver backends available")
        fileserver.update()
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Exception %s occurred in file server update",
            exc,
            exc_info_on_loglevel=logging.DEBUG,
        )


class AutoKey:
    """
    Implement the methods to run auto key acceptance and rejection
    """

    def __init__(self, opts):
        self.signing_files = {}
        self.opts = opts

    def check_permissions(self, filename):
        """
        Check if the specified filename has correct permissions
        """
        if salt.utils.platform.is_windows():
            return True

        # After we've ascertained we're not on windows
        groups = salt.utils.user.get_gid_list(self.opts["user"], include_default=False)
        fmode = os.stat(filename)

        if stat.S_IWOTH & fmode.st_mode:
            # don't allow others to write to the file
            return False

        if stat.S_IWGRP & fmode.st_mode:
            # if the group has write access only allow with permissive_pki_access
            if not self.opts.get("permissive_pki_access", False):
                return False
            elif os.getuid() == 0 and fmode.st_gid not in groups:
                # if salt is root it has to be in the group that has write access
                # this gives the group 'permission' to have write access
                return False

        return True

    def check_signing_file(self, keyid, signing_file):
        """
        Check a keyid for membership in a signing file
        """
        if not signing_file or not os.path.exists(signing_file):
            return False

        if not self.check_permissions(signing_file):
            log.warning("Wrong permissions for %s, ignoring content", signing_file)
            return False

        mtime = os.path.getmtime(signing_file)
        if self.signing_files.get(signing_file, {}).get("mtime") != mtime:
            self.signing_files.setdefault(signing_file, {})["mtime"] = mtime
            with salt.utils.files.fopen(signing_file, "r") as fp_:
                self.signing_files[signing_file]["data"] = [
                    entry
                    for entry in [line.strip() for line in fp_]
                    if not entry.strip().startswith("#")
                ]
        return any(
            salt.utils.stringutils.expr_match(keyid, line)
            for line in self.signing_files[signing_file].get("data", [])
        )

    def check_autosign_dir(self, keyid):
        """
        Check a keyid for membership in a autosign directory.
        """
        autosign_dir = os.path.join(self.opts["pki_dir"], "minions_autosign")

        # cleanup expired files
        expire_minutes = self.opts.get("autosign_timeout", 120)
        if expire_minutes > 0:
            min_time = time.time() - (60 * int(expire_minutes))
            for root, dirs, filenames in salt.utils.path.os_walk(autosign_dir):
                for f in filenames:
                    stub_file = os.path.join(autosign_dir, f)
                    mtime = os.path.getmtime(stub_file)
                    if mtime < min_time:
                        log.warning("Autosign keyid expired %s", stub_file)
                        os.remove(stub_file)

        stub_file = os.path.join(autosign_dir, keyid)
        if not os.path.exists(stub_file):
            return False
        os.remove(stub_file)
        return True

    def check_autosign_grains(self, autosign_grains):
        """
        Check for matching grains in the autosign_grains_dir.
        """
        if not autosign_grains or "autosign_grains_dir" not in self.opts:
            return False

        autosign_grains_dir = self.opts["autosign_grains_dir"]
        for root, dirs, filenames in os.walk(autosign_grains_dir):
            for grain in filenames:
                if grain in autosign_grains:
                    grain_file = os.path.join(autosign_grains_dir, grain)

                    if not self.check_permissions(grain_file):
                        log.warning(
                            "Wrong permissions for %s, ignoring content", grain_file
                        )
                        continue

                    with salt.utils.files.fopen(grain_file, "r") as f:
                        for line in f:
                            line = salt.utils.stringutils.to_unicode(line).strip()
                            if line.startswith("#"):
                                continue
                            if autosign_grains[grain] == line:
                                return True
        return False

    def check_autoreject(self, keyid):
        """
        Checks if the specified keyid should automatically be rejected.
        """
        return self.check_signing_file(keyid, self.opts.get("autoreject_file", None))

    def check_autosign(self, keyid, autosign_grains=None):
        """
        Checks if the specified keyid should automatically be signed.
        """
        if self.opts["auto_accept"]:
            return True
        if self.check_signing_file(keyid, self.opts.get("autosign_file", None)):
            return True
        if self.check_autosign_dir(keyid):
            return True
        if self.check_autosign_grains(autosign_grains):
            return True
        return False


class RemoteFuncs:
    """
    Funcitons made available to minions, this class includes the raw routines
    post validation that make up the minion access to the master
    """

    def __init__(self, opts):
        self.opts = opts
        self.event = salt.utils.event.get_event(
            "master",
            self.opts["sock_dir"],
            self.opts["transport"],
            opts=self.opts,
            listen=False,
        )
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Create the tops dict for loading external top data
        self.tops = salt.loader.tops(self.opts)
        # Make a client
        self.local = salt.client.get_local_client(mopts=self.opts)
        # Create the master minion to access the external job cache
        self.mminion = salt.minion.MasterMinion(self.opts, states=False, rend=False)
        self.__setup_fileserver()
        self.cache = salt.cache.factory(opts)

    def __setup_fileserver(self):
        """
        Set the local file objects from the file server interface
        """
        fs_ = salt.fileserver.Fileserver(self.opts)
        self._serve_file = fs_.serve_file
        self._file_find = fs_._find_file
        self._file_hash = fs_.file_hash
        self._file_list = fs_.file_list
        self._file_list_emptydirs = fs_.file_list_emptydirs
        self._dir_list = fs_.dir_list
        self._symlink_list = fs_.symlink_list
        self._file_envs = fs_.envs

    def __verify_minion_publish(self, load):
        """
        Verify that the passed information authorized a minion to execute
        """
        # Verify that the load is valid
        if "peer" not in self.opts:
            return False
        if not isinstance(self.opts["peer"], dict):
            return False
        if any(key not in load for key in ("fun", "arg", "tgt", "ret", "id")):
            return False
        # If the command will make a recursive publish don't run
        if re.match("publish.*", load["fun"]):
            return False
        # Check the permissions for this minion
        perms = []
        for match in self.opts["peer"]:
            if re.match(match, load["id"]):
                # This is the list of funcs/modules!
                if isinstance(self.opts["peer"][match], list):
                    perms.extend(self.opts["peer"][match])
        if "," in load["fun"]:
            # 'arg': [['cat', '/proc/cpuinfo'], [], ['foo']]
            load["fun"] = load["fun"].split(",")
            arg_ = []
            for arg in load["arg"]:
                arg_.append(arg.split())
            load["arg"] = arg_
        return self.ckminions.auth_check(
            perms,
            load["fun"],
            load["arg"],
            load["tgt"],
            load.get("tgt_type", "glob"),
            publish_validate=True,
        )

    def _master_opts(self, load):
        """
        Return the master options to the minion
        """
        mopts = {}
        file_roots = {}
        envs = self._file_envs()
        for saltenv in envs:
            if saltenv not in file_roots:
                file_roots[saltenv] = []
        mopts["file_roots"] = file_roots
        mopts["top_file_merging_strategy"] = self.opts["top_file_merging_strategy"]
        mopts["env_order"] = self.opts["env_order"]
        mopts["default_top"] = self.opts["default_top"]
        if load.get("env_only"):
            return mopts
        mopts["renderer"] = self.opts["renderer"]
        mopts["failhard"] = self.opts["failhard"]
        mopts["state_top"] = self.opts["state_top"]
        mopts["state_top_saltenv"] = self.opts["state_top_saltenv"]
        mopts["nodegroups"] = self.opts["nodegroups"]
        mopts["state_auto_order"] = self.opts["state_auto_order"]
        mopts["state_events"] = self.opts["state_events"]
        mopts["state_aggregate"] = self.opts["state_aggregate"]
        mopts["jinja_env"] = self.opts["jinja_env"]
        mopts["jinja_sls_env"] = self.opts["jinja_sls_env"]
        mopts["jinja_lstrip_blocks"] = self.opts["jinja_lstrip_blocks"]
        mopts["jinja_trim_blocks"] = self.opts["jinja_trim_blocks"]
        return mopts

    def _master_tops(self, load, skip_verify=False):
        """
        Return the results from master_tops if configured
        """
        if not skip_verify:
            if "id" not in load:
                log.error("Received call for external nodes without an id")
                return {}
            if not salt.utils.verify.valid_id(self.opts, load["id"]):
                return {}
        # Evaluate all configured master_tops interfaces

        opts = {}
        grains = {}
        ret = {}

        if "opts" in load:
            opts = load["opts"]
            if "grains" in load["opts"]:
                grains = load["opts"]["grains"]
        for fun in self.tops:
            if fun not in self.opts.get("master_tops", {}):
                continue
            try:
                ret = salt.utils.dictupdate.merge(
                    ret, self.tops[fun](opts=opts, grains=grains), merge_lists=True
                )
            except Exception as exc:  # pylint: disable=broad-except
                # If anything happens in the top generation, log it and move on
                log.error(
                    "Top function %s failed with error %s for minion %s",
                    fun,
                    exc,
                    load["id"],
                )
        return ret

    def _mine_get(self, load, skip_verify=False):
        """
        Gathers the data from the specified minions' mine
        """
        if not skip_verify:
            if any(key not in load for key in ("id", "tgt", "fun")):
                return {}

        if isinstance(load["fun"], str):
            functions = list(set(load["fun"].split(",")))
            _ret_dict = len(functions) > 1
        elif isinstance(load["fun"], list):
            functions = load["fun"]
            _ret_dict = True
        else:
            return {}

        functions_allowed = []

        if "mine_get" in self.opts:
            # If master side acl defined.
            if not isinstance(self.opts["mine_get"], dict):
                return {}
            perms = set()
            for match in self.opts["mine_get"]:
                if re.match(match, load["id"]):
                    if isinstance(self.opts["mine_get"][match], list):
                        perms.update(self.opts["mine_get"][match])
            for fun in functions:
                if any(re.match(perm, fun) for perm in perms):
                    functions_allowed.append(fun)
            if not functions_allowed:
                return {}
        else:
            functions_allowed = functions

        ret = {}
        if not salt.utils.verify.valid_id(self.opts, load["id"]):
            return ret

        expr_form = load.get("expr_form")
        # keep both expr_form and tgt_type to ensure
        # comptability between old versions of salt
        if expr_form is not None and "tgt_type" not in load:
            match_type = expr_form
        else:
            match_type = load.get("tgt_type", "glob")
        if match_type.lower() == "pillar":
            match_type = "pillar_exact"
        if match_type.lower() == "compound":
            match_type = "compound_pillar_exact"
        checker = salt.utils.minions.CkMinions(self.opts)
        _res = checker.check_minions(load["tgt"], match_type, greedy=False)
        minions = _res["minions"]
        minion_side_acl = {}  # Cache minion-side ACL
        for minion in minions:
            mine_data = self.cache.fetch("minions/{}".format(minion), "mine")
            if not isinstance(mine_data, dict):
                continue
            for function in functions_allowed:
                if function not in mine_data:
                    continue
                mine_entry = mine_data[function]
                mine_result = mine_data[function]
                if (
                    isinstance(mine_entry, dict)
                    and salt.utils.mine.MINE_ITEM_ACL_ID in mine_entry
                ):
                    mine_result = mine_entry[salt.utils.mine.MINE_ITEM_ACL_DATA]
                    # Check and fill minion-side ACL cache
                    if function not in minion_side_acl.get(minion, {}):
                        if "allow_tgt" in mine_entry:
                            # Only determine allowed targets if any have been specified.
                            # This prevents having to add a list of all minions as allowed targets.
                            get_minion = checker.check_minions(
                                mine_entry["allow_tgt"],
                                mine_entry.get("allow_tgt_type", "glob"),
                            )["minions"]
                            # the minion in allow_tgt does not exist
                            if not get_minion:
                                continue
                            salt.utils.dictupdate.set_dict_key_value(
                                minion_side_acl,
                                "{}:{}".format(minion, function),
                                get_minion,
                            )
                if salt.utils.mine.minion_side_acl_denied(
                    minion_side_acl, minion, function, load["id"]
                ):
                    continue
                if _ret_dict:
                    ret.setdefault(function, {})[minion] = mine_result
                else:
                    # There is only one function in functions_allowed.
                    ret[minion] = mine_result
        return ret

    def _mine(self, load, skip_verify=False):
        """
        Store/update the mine data in cache.
        """
        if not skip_verify:
            if "id" not in load or "data" not in load:
                return False
        if self.opts.get("minion_data_cache", False) or self.opts.get(
            "enforce_mine_cache", False
        ):
            cbank = "minions/{}".format(load["id"])
            ckey = "mine"
            new_data = load["data"]
            if not load.get("clear", False):
                data = self.cache.fetch(cbank, ckey)
                if isinstance(data, dict):
                    data.update(new_data)
            self.cache.store(cbank, ckey, data)
        return True

    def _mine_delete(self, load):
        """
        Allow the minion to delete a specific function from its own mine
        """
        if "id" not in load or "fun" not in load:
            return False
        if self.opts.get("minion_data_cache", False) or self.opts.get(
            "enforce_mine_cache", False
        ):
            cbank = "minions/{}".format(load["id"])
            ckey = "mine"
            try:
                data = self.cache.fetch(cbank, ckey)
                if not isinstance(data, dict):
                    return False
                if load["fun"] in data:
                    del data[load["fun"]]
                    self.cache.store(cbank, ckey, data)
            except OSError:
                return False
        return True

    def _mine_flush(self, load, skip_verify=False):
        """
        Allow the minion to delete all of its own mine contents
        """
        if not skip_verify and "id" not in load:
            return False
        if self.opts.get("minion_data_cache", False) or self.opts.get(
            "enforce_mine_cache", False
        ):
            return self.cache.flush("minions/{}".format(load["id"]), "mine")
        return True

    def _file_recv(self, load):
        """
        Allows minions to send files to the master, files are sent to the
        master file cache
        """
        if any(key not in load for key in ("id", "path", "loc")):
            return False
        if not self.opts["file_recv"] or os.path.isabs(load["path"]):
            return False
        if os.path.isabs(load["path"]) or "../" in load["path"]:
            # Can overwrite master files!!
            return False
        if not salt.utils.verify.valid_id(self.opts, load["id"]):
            return False
        file_recv_max_size = 1024 * 1024 * self.opts["file_recv_max_size"]

        if "loc" in load and load["loc"] < 0:
            log.error("Invalid file pointer: load[loc] < 0")
            return False

        if load.get("size", 0) > file_recv_max_size:
            log.error("Exceeding file_recv_max_size limit: %s", file_recv_max_size)
            return False

        if len(load["data"]) + load.get("loc", 0) > file_recv_max_size:
            log.error("Exceeding file_recv_max_size limit: %s", file_recv_max_size)
            return False
        # Normalize Windows paths
        normpath = load["path"]
        if ":" in normpath:
            # make sure double backslashes are normalized
            normpath = normpath.replace("\\", "/")
            normpath = os.path.normpath(normpath)
        cpath = os.path.join(
            self.opts["cachedir"], "minions", load["id"], "files", normpath
        )
        cdir = os.path.dirname(cpath)
        if not os.path.isdir(cdir):
            try:
                os.makedirs(cdir)
            except os.error:
                pass
        if os.path.isfile(cpath) and load["loc"] != 0:
            mode = "ab"
        else:
            mode = "wb"
        with salt.utils.files.fopen(cpath, mode) as fp_:
            if load["loc"]:
                fp_.seek(load["loc"])
            fp_.write(salt.utils.stringutils.to_str(load["data"]))
        return True

    def _pillar(self, load):
        """
        Return the pillar data for the minion
        """
        if any(key not in load for key in ("id", "grains")):
            return False
        log.debug("Master _pillar using ext: %s", load.get("ext"))
        pillar = salt.pillar.get_pillar(
            self.opts,
            load["grains"],
            load["id"],
            load.get("saltenv", load.get("env")),
            load.get("ext"),
            self.mminion.functions,
            pillar_override=load.get("pillar_override", {}),
        )
        data = pillar.compile_pillar()
        if self.opts.get("minion_data_cache", False):
            self.cache.store(
                "minions/{}".format(load["id"]),
                "data",
                {"grains": load["grains"], "pillar": data},
            )
            if self.opts.get("minion_data_cache_events") is True:
                self.event.fire_event(
                    {"comment": "Minion data cache refresh"},
                    salt.utils.event.tagify(load["id"], "refresh", "minion"),
                )
        return data

    def _minion_event(self, load):
        """
        Receive an event from the minion and fire it on the master event
        interface
        """
        if "id" not in load:
            return False
        if "events" not in load and ("tag" not in load or "data" not in load):
            return False
        if "events" in load:
            for event in load["events"]:
                if "data" in event:
                    event_data = event["data"]
                else:
                    event_data = event
                self.event.fire_event(event_data, event["tag"])  # old dup event
                if load.get("pretag") is not None:
                    self.event.fire_event(
                        event_data,
                        salt.utils.event.tagify(event["tag"], base=load["pretag"]),
                    )
        else:
            tag = load["tag"]
            self.event.fire_event(load, tag)
        return True

    def _return(self, load):
        """
        Handle the return data sent from the minions
        """
        # Generate EndTime
        endtime = salt.utils.jid.jid_to_time(salt.utils.jid.gen_jid(self.opts))
        # If the return data is invalid, just ignore it
        if any(key not in load for key in ("return", "jid", "id")):
            return False

        if load["jid"] == "req":
            # The minion is returning a standalone job, request a jobid
            prep_fstr = "{}.prep_jid".format(self.opts["master_job_cache"])
            load["jid"] = self.mminion.returners[prep_fstr](
                nocache=load.get("nocache", False)
            )

            # save the load, since we don't have it
            saveload_fstr = "{}.save_load".format(self.opts["master_job_cache"])
            self.mminion.returners[saveload_fstr](load["jid"], load)
        log.info("Got return from %s for job %s", load["id"], load["jid"])
        self.event.fire_event(load, load["jid"])  # old dup event
        self.event.fire_event(
            load, salt.utils.event.tagify([load["jid"], "ret", load["id"]], "job")
        )
        self.event.fire_ret_load(load)
        if not self.opts["job_cache"] or self.opts.get("ext_job_cache"):
            return

        fstr = "{}.update_endtime".format(self.opts["master_job_cache"])
        if self.opts.get("job_cache_store_endtime") and fstr in self.mminion.returners:
            self.mminion.returners[fstr](load["jid"], endtime)

        fstr = "{}.returner".format(self.opts["master_job_cache"])
        self.mminion.returners[fstr](load)

    def _syndic_return(self, load):
        """
        Receive a syndic minion return and format it to look like returns from
        individual minions.
        """
        # Verify the load
        if any(key not in load for key in ("return", "jid", "id")):
            return None
        # if we have a load, save it
        if "load" in load:
            fstr = "{}.save_load".format(self.opts["master_job_cache"])
            self.mminion.returners[fstr](load["jid"], load["load"])

        # Format individual return loads
        for key, item in load["return"].items():
            ret = {"jid": load["jid"], "id": key, "return": item}
            if "out" in load:
                ret["out"] = load["out"]
            self._return(ret)

    def minion_runner(self, load):
        """
        Execute a runner from a minion, return the runner's function data
        """
        if "peer_run" not in self.opts:
            return {}
        if not isinstance(self.opts["peer_run"], dict):
            return {}
        if any(key not in load for key in ("fun", "arg", "id")):
            return {}
        perms = set()
        for match in self.opts["peer_run"]:
            if re.match(match, load["id"]):
                # This is the list of funcs/modules!
                if isinstance(self.opts["peer_run"][match], list):
                    perms.update(self.opts["peer_run"][match])
        good = False
        for perm in perms:
            if re.match(perm, load["fun"]):
                good = True
        if not good:
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning("Minion id %s is not who it says it is!", load["id"])
            return {}
        # Prepare the runner object
        opts = {}
        opts.update(self.opts)
        opts.update(
            {
                "fun": load["fun"],
                "arg": salt.utils.args.parse_input(
                    load["arg"], no_parse=load.get("no_parse", [])
                ),
                "id": load["id"],
                "doc": False,
                "conf_file": self.opts["conf_file"],
            }
        )
        runner = salt.runner.Runner(opts)
        return runner.run()

    def pub_ret(self, load, skip_verify=False):
        """
        Request the return data from a specific jid, only allowed
        if the requesting minion also initialted the execution.
        """
        if not skip_verify and any(key not in load for key in ("jid", "id")):
            return {}
        else:
            auth_cache = os.path.join(self.opts["cachedir"], "publish_auth")
            if not os.path.isdir(auth_cache):
                os.makedirs(auth_cache)
            jid_fn = os.path.join(auth_cache, load["jid"])
            with salt.utils.files.fopen(jid_fn, "r") as fp_:
                if not load["id"] == salt.utils.stringutils.to_unicode(fp_.read()):
                    return {}

            return self.local.get_cache_returns(load["jid"])

    def minion_pub(self, load):
        """
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.
        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions
        The config will look like this:
        peer:
            .*:
                - .*
        This configuration will enable all minions to execute all commands.
        peer:
            foo.example.com:
                - test.*
        This configuration will only allow the minion foo.example.com to
        execute commands from the test module
        """
        if not self.__verify_minion_publish(load):
            return {}
        # Set up the publication payload
        pub_load = {
            "fun": load["fun"],
            "arg": salt.utils.args.parse_input(
                load["arg"], no_parse=load.get("no_parse", [])
            ),
            "tgt_type": load.get("tgt_type", "glob"),
            "tgt": load["tgt"],
            "ret": load["ret"],
            "id": load["id"],
        }
        if "tgt_type" in load:
            if load["tgt_type"].startswith("node"):
                if load["tgt"] in self.opts["nodegroups"]:
                    pub_load["tgt"] = self.opts["nodegroups"][load["tgt"]]
                    pub_load["tgt_type"] = "compound"
                else:
                    return {}
            else:
                pub_load["tgt_type"] = load["tgt_type"]
        ret = {}
        ret["jid"] = self.local.cmd_async(**pub_load)
        _res = self.ckminions.check_minions(load["tgt"], pub_load["tgt_type"])
        ret["minions"] = _res["minions"]
        auth_cache = os.path.join(self.opts["cachedir"], "publish_auth")
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, str(ret["jid"]))
        with salt.utils.files.fopen(jid_fn, "w+") as fp_:
            fp_.write(salt.utils.stringutils.to_str(load["id"]))
        return ret

    def minion_publish(self, load):
        """
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.
        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions
        The config will look like this:
        peer:
            .*:
                - .*
        This configuration will enable all minions to execute all commands.
        peer:
            foo.example.com:
                - test.*
        This configuration will only allow the minion foo.example.com to
        execute commands from the test module
        """
        if not self.__verify_minion_publish(load):
            return {}
        # Set up the publication payload
        pub_load = {
            "fun": load["fun"],
            "arg": salt.utils.args.parse_input(
                load["arg"], no_parse=load.get("no_parse", [])
            ),
            "tgt_type": load.get("tgt_type", "glob"),
            "tgt": load["tgt"],
            "ret": load["ret"],
            "id": load["id"],
        }
        if "tmo" in load:
            try:
                pub_load["timeout"] = int(load["tmo"])
            except ValueError:
                msg = "Failed to parse timeout value: {}".format(load["tmo"])
                log.warning(msg)
                return {}
        if "timeout" in load:
            try:
                pub_load["timeout"] = int(load["timeout"])
            except ValueError:
                msg = "Failed to parse timeout value: {}".format(load["timeout"])
                log.warning(msg)
                return {}
        if "tgt_type" in load:
            if load["tgt_type"].startswith("node"):
                if load["tgt"] in self.opts["nodegroups"]:
                    pub_load["tgt"] = self.opts["nodegroups"][load["tgt"]]
                    pub_load["tgt_type"] = "compound"
                else:
                    return {}
            else:
                pub_load["tgt_type"] = load["tgt_type"]
        pub_load["raw"] = True
        ret = {}
        for minion in self.local.cmd_iter(**pub_load):
            if load.get("form", "") == "full":
                data = minion
                if "jid" in minion:
                    ret["__jid__"] = minion["jid"]
                data["ret"] = data.pop("return")
                ret[minion["id"]] = data
            else:
                ret[minion["id"]] = minion["return"]
                if "jid" in minion:
                    ret["__jid__"] = minion["jid"]
        for key, val in self.local.get_cache_returns(ret["__jid__"]).items():
            if key not in ret:
                ret[key] = val
        if load.get("form", "") != "full":
            ret.pop("__jid__")
        return ret

    def revoke_auth(self, load):
        """
        Allow a minion to request revocation of its own key
        """
        if "id" not in load:
            return False
        with salt.key.Key(self.opts) as keyapi:
            keyapi.delete_key(
                load["id"], preserve_minions=load.get("preserve_minion_cache", False)
            )
        return True

    def destroy(self):
        if self.event is not None:
            self.event.destroy()
            self.event = None
        if self.local is not None:
            self.local.destroy()
            self.local = None


class LocalFuncs:
    """
    Set up methods for use only from the local system
    """

    # The ClearFuncs object encapsulates the functions that can be executed in
    # the clear:
    # publish (The publish from the LocalClient)
    # _auth
    def __init__(self, opts, key):
        self.opts = opts
        self.key = key
        # Create the event manager
        self.event = salt.utils.event.get_event(
            "master",
            self.opts["sock_dir"],
            self.opts["transport"],
            opts=self.opts,
            listen=False,
        )
        # Make a client
        self.local = salt.client.get_local_client(mopts=self.opts)
        # Make an minion checker object
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Make an Auth object
        self.loadauth = salt.auth.LoadAuth(opts)
        # Stand up the master Minion to access returner data
        self.mminion = salt.minion.MasterMinion(self.opts, states=False, rend=False)
        # Make a wheel object
        self.wheel_ = salt.wheel.Wheel(opts)

    def runner(self, load):
        """
        Send a master control function back to the runner system
        """
        # All runner opts pass through eauth
        auth_type, err_name, key = self._prep_auth_info(load)

        # Authenticate
        auth_check = self.loadauth.check_authentication(load, auth_type)
        error = auth_check.get("error")

        if error:
            # Authentication error occurred: do not continue.
            return {"error": error}

        # Authorize
        runner_check = self.ckminions.runner_check(
            auth_check.get("auth_list", []), load["fun"], load["kwarg"]
        )
        username = auth_check.get("username")
        if not runner_check:
            return {
                "error": {
                    "name": err_name,
                    "message": (
                        'Authentication failure of type "{}" occurred '
                        "for user {}.".format(auth_type, username)
                    ),
                }
            }
        elif isinstance(runner_check, dict) and "error" in runner_check:
            # A dictionary with an error name/message was handled by ckminions.runner_check
            return runner_check

        # Authorized. Do the job!
        try:
            fun = load.pop("fun")
            runner_client = salt.runner.RunnerClient(self.opts)
            return runner_client.asynchronous(fun, load.get("kwarg", {}), username)
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Exception occurred while introspecting %s")
            return {
                "error": {
                    "name": exc.__class__.__name__,
                    "args": exc.args,
                    "message": str(exc),
                }
            }

    def wheel(self, load):
        """
        Send a master control function back to the wheel system
        """
        # All wheel ops pass through eauth
        auth_type, err_name, key = self._prep_auth_info(load)

        # Authenticate
        auth_check = self.loadauth.check_authentication(
            load, auth_type, key=key, show_username=True
        )
        error = auth_check.get("error")

        if error:
            # Authentication error occurred: do not continue.
            return {"error": error}

        # Authorize
        username = auth_check.get("username")
        if auth_type != "user":
            wheel_check = self.ckminions.wheel_check(
                auth_check.get("auth_list", []), load["fun"], load["kwarg"]
            )
            if not wheel_check:
                return {
                    "error": {
                        "name": err_name,
                        "message": (
                            'Authentication failure of type "{}" occurred for '
                            "user {}.".format(auth_type, username)
                        ),
                    }
                }
            elif isinstance(wheel_check, dict) and "error" in wheel_check:
                # A dictionary with an error name/message was handled by ckminions.wheel_check
                return wheel_check

        # Authenticated. Do the job.
        jid = salt.utils.jid.gen_jid(self.opts)
        fun = load.pop("fun")
        tag = salt.utils.event.tagify(jid, prefix="wheel")
        data = {
            "fun": "wheel.{}".format(fun),
            "jid": jid,
            "tag": tag,
            "user": username,
        }
        try:
            self.event.fire_event(data, salt.utils.event.tagify([jid, "new"], "wheel"))
            ret = self.wheel_.call_func(fun, **load)
            data["return"] = ret
            data["success"] = True
            self.event.fire_event(data, salt.utils.event.tagify([jid, "ret"], "wheel"))
            return {"tag": tag, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Exception occurred while introspecting %s", fun)
            data["return"] = "Exception occurred in wheel {}: {}: {}".format(
                fun,
                exc.__class__.__name__,
                exc,
            )
            data["success"] = False
            self.event.fire_event(data, salt.utils.event.tagify([jid, "ret"], "wheel"))
            return {"tag": tag, "data": data}

    def mk_token(self, load):
        """
        Create and return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        """
        token = self.loadauth.mk_token(load)
        if not token:
            log.warning('Authentication failure of type "eauth" occurred.')
            return ""
        return token

    def get_token(self, load):
        """
        Return the name associated with a token or False if the token is invalid
        """
        if "token" not in load:
            return False
        return self.loadauth.get_tok(load["token"])

    def publish(self, load):
        """
        This method sends out publications to the minions, it can only be used
        by the LocalClient.
        """
        extra = load.get("kwargs", {})

        publisher_acl = salt.acl.PublisherACL(self.opts["publisher_acl_blacklist"])

        if publisher_acl.user_is_blacklisted(
            load["user"]
        ) or publisher_acl.cmd_is_blacklisted(load["fun"]):
            log.error(
                "%s does not have permissions to run %s. Please contact "
                "your local administrator if you believe this is in error.",
                load["user"],
                load["fun"],
            )
            return {
                "error": {
                    "name": "AuthorizationError",
                    "message": "Authorization error occurred.",
                }
            }

        # Retrieve the minions list
        delimiter = load.get("kwargs", {}).get("delimiter", DEFAULT_TARGET_DELIM)
        _res = self.ckminions.check_minions(
            load["tgt"], load.get("tgt_type", "glob"), delimiter
        )
        minions = _res["minions"]

        # Check for external auth calls and authenticate
        auth_type, err_name, key = self._prep_auth_info(extra)
        if auth_type == "user":
            auth_check = self.loadauth.check_authentication(load, auth_type, key=key)
        else:
            auth_check = self.loadauth.check_authentication(extra, auth_type)

        # Setup authorization list variable and error information
        auth_list = auth_check.get("auth_list", [])
        error = auth_check.get("error")
        err_msg = 'Authentication failure of type "{}" occurred.'.format(auth_type)

        if error:
            # Authentication error occurred: do not continue.
            log.warning(err_msg)
            return {
                "error": {
                    "name": "AuthenticationError",
                    "message": "Authentication error occurred.",
                }
            }

        # All Token, Eauth, and non-root users must pass the authorization check
        if auth_type != "user" or (auth_type == "user" and auth_list):
            # Authorize the request
            authorized = self.ckminions.auth_check(
                auth_list,
                load["fun"],
                load["arg"],
                load["tgt"],
                load.get("tgt_type", "glob"),
                minions=minions,
                # always accept find_job
                whitelist=["saltutil.find_job"],
            )

            if not authorized:
                # Authorization error occurred. Log warning and do not continue.
                log.warning(err_msg)
                return {
                    "error": {
                        "name": "AuthorizationError",
                        "message": "Authorization error occurred.",
                    }
                }

            # Perform some specific auth_type tasks after the authorization check
            if auth_type == "token":
                username = auth_check.get("username")
                load["user"] = username
                log.debug('Minion tokenized user = "%s"', username)
            elif auth_type == "eauth":
                # The username we are attempting to auth with
                load["user"] = self.loadauth.load_name(extra)

        # If we order masters (via a syndic), don't short circuit if no minions
        # are found
        if not self.opts.get("order_masters"):
            # Check for no minions
            if not minions:
                return {"enc": "clear", "load": {"jid": None, "minions": minions}}
        # Retrieve the jid
        if not load["jid"]:
            fstr = "{}.prep_jid".format(self.opts["master_job_cache"])
            load["jid"] = self.mminion.returners[fstr](
                nocache=extra.get("nocache", False)
            )
        self.event.fire_event({"minions": minions}, load["jid"])

        new_job_load = {
            "jid": load["jid"],
            "tgt_type": load["tgt_type"],
            "tgt": load["tgt"],
            "user": load["user"],
            "fun": load["fun"],
            "arg": salt.utils.args.parse_input(
                load["arg"], no_parse=load.get("no_parse", [])
            ),
            "minions": minions,
        }

        # Announce the job on the event bus
        self.event.fire_event(new_job_load, "new_job")  # old dup event
        self.event.fire_event(
            new_job_load, salt.utils.event.tagify([load["jid"], "new"], "job")
        )

        # Save the invocation information
        if self.opts["ext_job_cache"]:
            try:
                fstr = "{}.save_load".format(self.opts["ext_job_cache"])
                self.mminion.returners[fstr](load["jid"], load)
            except KeyError:
                log.critical(
                    "The specified returner used for the external job cache "
                    '"%s" does not have a save_load function!',
                    self.opts["ext_job_cache"],
                )
            except Exception:  # pylint: disable=broad-except
                log.critical(
                    "The specified returner threw a stack trace:", exc_info=True
                )

        # always write out to the master job cache
        try:
            fstr = "{}.save_load".format(self.opts["master_job_cache"])
            self.mminion.returners[fstr](load["jid"], load)
        except KeyError:
            log.critical(
                "The specified returner used for the master job cache "
                '"%s" does not have a save_load function!',
                self.opts["master_job_cache"],
            )
        except Exception:  # pylint: disable=broad-except
            log.critical("The specified returner threw a stack trace:", exc_info=True)
        # Altering the contents of the publish load is serious!! Changes here
        # break compatibility with minion/master versions and even tiny
        # additions can have serious implications on the performance of the
        # publish commands.
        #
        # In short, check with Thomas Hatch before you even think about
        # touching this stuff, we can probably do what you want to do another
        # way that won't have a negative impact.
        pub_load = {
            "fun": load["fun"],
            "arg": salt.utils.args.parse_input(
                load["arg"], no_parse=load.get("no_parse", [])
            ),
            "tgt": load["tgt"],
            "jid": load["jid"],
            "ret": load["ret"],
        }

        if "id" in extra:
            pub_load["id"] = extra["id"]
        if "tgt_type" in load:
            pub_load["tgt_type"] = load["tgt_type"]
        if "to" in load:
            pub_load["to"] = load["to"]

        if "kwargs" in load:
            if "ret_config" in load["kwargs"]:
                pub_load["ret_config"] = load["kwargs"].get("ret_config")

            if "metadata" in load["kwargs"]:
                pub_load["metadata"] = load["kwargs"].get("metadata")

            if "ret_kwargs" in load["kwargs"]:
                pub_load["ret_kwargs"] = load["kwargs"].get("ret_kwargs")

        if "user" in load:
            log.info(
                "User %s Published command %s with jid %s",
                load["user"],
                load["fun"],
                load["jid"],
            )
            pub_load["user"] = load["user"]
        else:
            log.info("Published command %s with jid %s", load["fun"], load["jid"])
        log.debug("Published command details %s", pub_load)

        return {"ret": {"jid": load["jid"], "minions": minions}, "pub": pub_load}

    def _prep_auth_info(self, load):
        key = None
        if "token" in load:
            auth_type = "token"
            err_name = "TokenAuthenticationError"
        elif "eauth" in load:
            auth_type = "eauth"
            err_name = "EauthAuthenticationError"
        else:
            auth_type = "user"
            err_name = "UserAuthenticationError"
            key = self.key

        return auth_type, err_name, key

    def destroy(self):
        if self.event is not None:
            self.event.destroy()
            self.event = None
        if self.local is not None:
            self.local.destroy()
            self.local = None

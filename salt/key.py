"""
The Salt Key backend API and interface used by the CLI. The Key class can be
used to manage salt keys directly without interfacing with the CLI.
"""

import fnmatch
import itertools
import logging
import os
import sys

import salt.cache
import salt.client
import salt.crypt
import salt.exceptions
import salt.payload
import salt.transport
import salt.utils.args
import salt.utils.crypt
import salt.utils.data
import salt.utils.event
import salt.utils.files
import salt.utils.json
import salt.utils.kinds
import salt.utils.minions
import salt.utils.sdb
import salt.utils.stringutils
import salt.utils.user
from salt.utils.decorators import cached_property

log = logging.getLogger(__name__)


def get_key(opts):
    return Key(opts)


class KeyCLI:
    """
    Manage key CLI operations
    """

    CLI_KEY_MAP = {
        "list": "list_status",
        "delete": "delete_key",
        "gen_signature": "gen_keys_signature",
        "print": "key_str",
    }

    def __init__(self, opts):
        self.opts = opts
        import salt.wheel

        self.client = salt.wheel.WheelClient(opts)
        # instantiate the key object for masterless mode
        if not opts.get("eauth"):
            self.key = get_key(opts)
        else:
            self.key = Key

        self.auth = {}

    def _update_opts(self):
        # get the key command
        for cmd in (
            "gen_keys",
            "gen_signature",
            "list",
            "list_all",
            "print",
            "print_all",
            "accept",
            "accept_all",
            "reject",
            "reject_all",
            "delete",
            "delete_all",
            "finger",
            "finger_all",
            "list_all",
        ):  # last is default
            if self.opts[cmd]:
                break
        # set match if needed
        if not cmd.startswith("gen_"):
            if cmd == "list_all":
                self.opts["match"] = "all"
            elif cmd.endswith("_all"):
                self.opts["match"] = "*"
            else:
                self.opts["match"] = self.opts[cmd]
            if cmd.startswith("accept"):
                self.opts["include_rejected"] = (
                    self.opts["include_all"] or self.opts["include_rejected"]
                )
                self.opts["include_accepted"] = False
            elif cmd.startswith("reject"):
                self.opts["include_accepted"] = (
                    self.opts["include_all"] or self.opts["include_accepted"]
                )
                self.opts["include_rejected"] = False
        elif cmd == "gen_keys":
            self.opts["keydir"] = self.opts["gen_keys_dir"]
            self.opts["keyname"] = self.opts["gen_keys"]
        # match is set to opts, now we can forget about *_all commands
        self.opts["fun"] = cmd.replace("_all", "")

    def _init_auth(self):
        if self.auth:
            return

        low = {}
        skip_perm_errors = self.opts["eauth"] != ""

        if self.opts["eauth"]:
            if "token" in self.opts:
                try:
                    with salt.utils.files.fopen(
                        os.path.join(self.opts["cachedir"], ".root_key"), "r"
                    ) as fp_:
                        low["key"] = salt.utils.stringutils.to_unicode(fp_.readline())
                except OSError:
                    low["token"] = self.opts["token"]

            # If using eauth and a token hasn't already been loaded into
            # low, prompt the user to enter auth credentials
            if "token" not in low and "key" not in low and self.opts["eauth"]:
                # This is expensive. Don't do it unless we need to.
                import salt.auth

                resolver = salt.auth.Resolver(self.opts)
                res = resolver.cli(self.opts["eauth"])
                if self.opts["mktoken"] and res:
                    tok = resolver.token_cli(self.opts["eauth"], res)
                    if tok:
                        low["token"] = tok.get("token", "")
                if not res:
                    log.error("Authentication failed")
                    return {}
                low.update(res)
                low["eauth"] = self.opts["eauth"]
        else:
            # late import to avoid circular import
            import salt.utils.master

            low["user"] = salt.utils.user.get_specific_user()
            low["key"] = salt.utils.master.get_master_key(
                low["user"], self.opts, skip_perm_errors
            )

        self.auth = low

    def _get_args_kwargs(self, fun, args=None):
        argspec = salt.utils.args.get_function_argspec(fun)
        if args is None:
            args = []
            if argspec.args:
                # Iterate in reverse order to ensure we get the correct default
                # value for the positional argument.
                for arg, default in itertools.zip_longest(
                    reversed(argspec.args), reversed(argspec.defaults or ())
                ):
                    args.append(self.opts.get(arg, default))
            # Reverse the args so that they are in the correct order
            args = args[::-1]

        if argspec.keywords is None:
            kwargs = {}
        else:
            args, kwargs = salt.minion.load_args_and_kwargs(fun, args)
        return args, kwargs

    def _run_cmd(self, cmd, args=None):
        if not self.opts.get("eauth"):
            cmd = self.CLI_KEY_MAP.get(cmd, cmd)
            fun = getattr(self.key, cmd)
            args, kwargs = self._get_args_kwargs(fun, args)
            ret = fun(*args, **kwargs)
            if (
                isinstance(ret, dict)
                and "local" in ret
                and cmd not in ("finger", "finger_all")
            ):
                ret.pop("local", None)
            return ret

        if cmd in ("accept", "reject", "delete") and args is None:
            args = self.opts.get("match_dict", {}).get("minions")
        fstr = f"key.{cmd}"
        fun = self.client.functions[fstr]
        args, kwargs = self._get_args_kwargs(fun, args)

        low = {
            "fun": fstr,
            "arg": args,
            "kwarg": kwargs,
        }

        self._init_auth()
        low.update(self.auth)

        # Execute the key request!
        ret = self.client.cmd_sync(low)

        ret = ret["data"]["return"]
        if (
            isinstance(ret, dict)
            and "local" in ret
            and cmd not in ("finger", "finger_all")
        ):
            ret.pop("local", None)

        return ret

    def _filter_ret(self, cmd, ret):
        if cmd.startswith("delete"):
            return ret

        keys = {}
        if self.key.PEND in ret:
            keys[self.key.PEND] = ret[self.key.PEND]
        if self.opts["include_accepted"] and bool(ret.get(self.key.ACC)):
            keys[self.key.ACC] = ret[self.key.ACC]
        if self.opts["include_rejected"] and bool(ret.get(self.key.REJ)):
            keys[self.key.REJ] = ret[self.key.REJ]
        if self.opts["include_denied"] and bool(ret.get(self.key.DEN)):
            keys[self.key.DEN] = ret[self.key.DEN]
        return keys

    def _print_no_match(self, cmd, match):
        statuses = ["unaccepted"]
        if self.opts["include_accepted"]:
            statuses.append("accepted")
        if self.opts["include_rejected"]:
            statuses.append("rejected")
        if self.opts["include_denied"]:
            statuses.append("denied")
        if len(statuses) == 1:
            stat_str = statuses[0]
        else:
            stat_str = "{} or {}".format(", ".join(statuses[:-1]), statuses[-1])
        msg = f"The key glob '{match}' does not match any {stat_str} keys."
        print(msg)

    def run(self):
        """
        Run the logic for saltkey
        """
        self._update_opts()
        cmd = self.opts["fun"]

        veri = None
        ret = None
        try:
            if cmd in ("accept", "reject", "delete"):
                ret = self._run_cmd("glob_match")
                if not isinstance(ret, dict):
                    salt.output.display_output(ret, "key", opts=self.opts)
                    return ret
                ret = self._filter_ret(cmd, ret)
                if not ret:
                    self._print_no_match(cmd, self.opts["match"])
                    return
                print(
                    "The following keys are going to be {}ed:".format(cmd.rstrip("e"))
                )
                salt.output.display_output(ret, "key", opts=self.opts)

                if not self.opts.get("yes", False):
                    try:
                        if cmd.startswith("delete"):
                            veri = input("Proceed? [N/y] ")
                            if not veri:
                                veri = "n"
                        else:
                            veri = input("Proceed? [n/Y] ")
                            if not veri:
                                veri = "y"
                    except KeyboardInterrupt:
                        raise SystemExit("\nExiting on CTRL-c")
                # accept/reject/delete the same keys we're printed to the user
                self.opts["match_dict"] = ret
                self.opts.pop("match", None)
                list_ret = ret

            if veri is None or veri.lower().startswith("y"):
                ret = self._run_cmd(cmd)
                if cmd in ("accept", "reject", "delete"):
                    if cmd == "delete":
                        ret = list_ret
                    for minions in ret.values():
                        for minion in minions:
                            print(
                                "Key for minion {} {}ed.".format(
                                    minion, cmd.rstrip("e")
                                )
                            )
                elif isinstance(ret, dict):
                    salt.output.display_output(ret, "key", opts=self.opts)
                else:
                    salt.output.display_output({"return": ret}, "key", opts=self.opts)
        except salt.exceptions.SaltException as exc:
            ret = f"{exc}"
            if not self.opts.get("quiet", False):
                salt.output.display_output(ret, "nested", self.opts)
        except Exception as exc:  # pylint: disable=broad-except
            # dont swallow unexpected exceptions in salt-key
            log.exception(exc)

        return ret


class Key:
    """
    The object that encapsulates saltkey actions
    """

    ACC = "minions"
    PEND = "minions_pre"
    REJ = "minions_rejected"
    DEN = "minions_denied"

    # handle transitions from legacy naming to simpler new format
    STATE_MAP = {"accepted": ACC, "rejected": REJ, "pending": PEND, "denied": DEN}
    DIR_MAP = {v: k for k, v in STATE_MAP.items()}

    ACT_MAP = {
        ACC: "accept",
        REJ: "reject",
        PEND: "pend",
        DEN: "denied",
    }

    def __init__(self, opts, io_loop=None):
        self.opts = opts
        self.cache = salt.cache.Cache(opts, driver=self.opts["keys.cache_driver"])
        if self.opts.get("cluster_id", None) is not None:
            self.pki_dir = self.opts.get("cluster_pki_dir", "")
        else:
            self.pki_dir = self.opts.get("pki_dir", "")
        self._kind = self.opts.get("__role", "")  # application kind
        if self._kind not in salt.utils.kinds.APPL_KINDS:
            emsg = f"Invalid application kind = '{self._kind}'."
            log.error(emsg)
            raise ValueError(emsg)
        self.passphrase = salt.utils.sdb.sdb_get(
            self.opts.get("signing_key_pass"), self.opts
        )
        self.io_loop = io_loop

    @cached_property
    def master_keys(self):
        return salt.crypt.MasterKeys(self.opts)

    @cached_property
    def event(self):
        return salt.utils.event.get_event(
            self._kind,
            self.opts["sock_dir"],
            opts=self.opts,
            listen=False,
            io_loop=self.io_loop,
        )

    def _check_minions_directories(self):
        """
        Return the minion keys directory paths
        """
        minions_accepted = os.path.join(self.pki_dir, self.ACC)
        minions_pre = os.path.join(self.pki_dir, self.PEND)
        minions_rejected = os.path.join(self.pki_dir, self.REJ)

        minions_denied = os.path.join(self.pki_dir, self.DEN)
        return minions_accepted, minions_pre, minions_rejected, minions_denied

    def _get_key_attrs(self, keydir, keyname, keysize, user):
        cache = None
        if not keydir:
            if "gen_keys_dir" in self.opts:
                keydir = self.opts["gen_keys_dir"]
            else:
                keydir = self.pki_dir
        cache = salt.cache.Cache(
            self.opts, driver=self.opts["keys.cache_driver"], cachedir=keydir, user=user
        )
        if not keyname:
            if "gen_keys" in self.opts:
                keyname = self.pki_dir
            else:
                keyname = "minion"
        if not keysize:
            keysize = self.opts["keysize"]
        return keydir, keyname, keysize, user, cache

    def gen_keys(self, keydir=None, keyname=None, keysize=None, user=None):
        """
        Generate minion RSA public keypair
        """
        keydir, keyname, keysize, user, cache = self._get_key_attrs(
            keydir, keyname, keysize, user
        )
        priv = self.master_keys.find_or_create_keys(
            keyname, keysize=keysize, cache=cache
        )
        return salt.utils.crypt.pem_finger(key=priv.public_key())

    def gen_keys_signature(
        self, priv, pub, signature_path, auto_create=False, keysize=None
    ):
        """
        Generate master public-key-signature
        """
        # check given pub-key
        if pub:
            if not os.path.isfile(pub):
                return f"Public-key {pub} does not exist"
        # default to master.pub
        else:
            mpub = self.pki_dir + "/" + "master.pub"
            if os.path.isfile(mpub):
                pub = mpub

        # check given priv-key
        if priv:
            if not os.path.isfile(priv):
                return f"Private-key {priv} does not exist"
        # default to master_sign.pem
        else:
            mpriv = self.pki_dir + "/" + "master_sign.pem"
            if os.path.isfile(mpriv):
                priv = mpriv

        if priv:
            priv = salt.crypt.PrivateKey.from_file(priv)
        else:
            if auto_create:
                log.debug(
                    "Generating new signing key-pair .%s.* in %s",
                    self.opts["master_sign_key_name"],
                    self.pki_dir,
                )
                # we force re-create as master_keys init also does the same
                # creation without these kwarg overrides
                priv = self.master_keys.sign_key = self.master_keys.find_or_create_keys(
                    name=self.opts["master_sign_key_name"],
                    keysize=keysize or self.opts["keysize"],
                    passphrase=self.passphrase,
                    force=True,
                )
            else:
                return "No usable private-key found"

        if pub:
            pub = salt.crypt.PublicKey.from_file(pub).key
        else:
            return "No usable public-key found"

        log.debug("Using public-key %s", pub)
        log.debug("Using private-key %s", priv)

        if signature_path:
            if not os.path.isdir(signature_path):
                log.debug("target directory %s does not exist", signature_path)
            sign_path = signature_path + "/" + self.master_keys.master_pubkey_signature
        else:
            sign_path = None

        return self.master_keys.gen_signature(priv, pub, sign_path)

    def check_minion_cache(self, preserve_minions=None):
        """
        Check the minion cache to make sure that old minion data is cleared

        Optionally, pass in a list of minions which should have their caches
        preserved. To preserve all caches, set __opts__['preserve_minion_cache']
        """
        if preserve_minions is None:
            preserve_minions = []
        keys = self.list_keys()
        minions = []
        for key, val in keys.items():
            minions.extend(val)
        if not self.opts.get("preserve_minion_cache", False):
            # we use a new cache instance here as we dont want the key cache
            cache = salt.cache.factory(self.opts)
            clist = cache.list(self.ACC)
            if clist:
                for minion in clist:
                    if minion not in minions and minion not in preserve_minions:
                        cache.flush(f"{self.ACC}/{minion}")

    def check_master(self):
        """
        Log if the master is not running

        :rtype: bool
        :return: Whether or not the master is running
        """
        if not os.path.exists(os.path.join(self.opts["sock_dir"], "publish_pull.ipc")):
            return False
        return True

    def glob_match(self, match, full=False):
        """
        Accept a glob which to match the of a key and return the key's location
        """
        if full:
            matches = self.all_keys()
        else:
            matches = self.list_keys()
        ret = {}
        if "," in match and isinstance(match, str):
            match = match.split(",")
        for status, keys in matches.items():
            for key in salt.utils.data.sorted_ignorecase(keys):
                if isinstance(match, list):
                    for match_item in match:
                        if fnmatch.fnmatch(key, match_item):
                            if status not in ret:
                                ret[status] = []
                            ret[status].append(key)
                else:
                    if fnmatch.fnmatch(key, match):
                        if status not in ret:
                            ret[status] = []
                        ret[status].append(key)
        return ret

    def list_match(self, match):
        """
        Accept a glob which to match the of a key and return the key's location
        """
        ret = {}
        if isinstance(match, str):
            match = match.split(",")

        for name in match:
            key = self.cache.fetch("keys", name)
            if key:
                try:
                    ret.setdefault(self.STATE_MAP[key["state"]], [])
                    ret[self.STATE_MAP[key["state"]]].append(name)
                except KeyError:
                    log.error("unexpected key state returned for %s: %s", name, key)

            denied_keys = self.cache.fetch("denied_keys", name)
            if denied_keys:
                ret.setdefault(self.DEN, [])
                ret[self.DEN].append(name)
        return ret

    def dict_match(self, match_dict):
        """
        Accept a dictionary of keys and return the current state of the
        specified keys
        """
        ret = {}
        cur_keys = self.list_keys()
        for status, keys in match_dict.items():
            for key in salt.utils.data.sorted_ignorecase(keys):
                for keydir in (self.ACC, self.PEND, self.REJ, self.DEN):
                    if keydir and fnmatch.filter(cur_keys.get(keydir, []), key):
                        ret.setdefault(keydir, []).append(key)
        return ret

    def list_keys(self):
        """
        Return a dict of managed keys and what the key status are
        """
        if self.opts.get("key_cache") == "sched":
            acc = "accepted"

            cache_file = os.path.join(self.opts["pki_dir"], acc, ".key_cache")
            if self.opts["key_cache"] and os.path.exists(cache_file):
                log.debug("Returning cached minion list")
                with salt.utils.files.fopen(cache_file, mode="rb") as fn_:
                    return salt.payload.load(fn_)

        ret = {
            "minions_pre": [],
            "minions_rejected": [],
            "minions": [],
            "minions_denied": [],
        }
        for id_ in salt.utils.data.sorted_ignorecase(self.cache.list("keys")):
            key = self.cache.fetch("keys", id_)

            if key["state"] == "accepted":
                ret["minions"].append(id_)
            elif key["state"] == "pending":
                ret["minions_pre"].append(id_)
            elif key["state"] == "rejected":
                ret["minions_rejected"].append(id_)

        for id_ in salt.utils.data.sorted_ignorecase(self.cache.list("denied_keys")):
            ret["minions_denied"].append(id_)
        return ret

    def local_keys(self):
        """
        Return a dict of local keys
        """
        ret = {"local": []}
        for key in salt.utils.data.sorted_ignorecase(self.cache.list("master_keys")):
            if key.endswith(".pub") or key.endswith(".pem"):
                ret["local"].append(key)
        return ret

    def all_keys(self):
        """
        Merge managed keys with local keys
        """
        keys = self.list_keys()
        keys.update(self.local_keys())
        return keys

    def list_status(self, match):
        """
        Return a dict of managed keys under a named status
        """
        ret = self.all_keys()
        if match.startswith("acc"):
            return {
                "minions": salt.utils.data.sorted_ignorecase(ret.get("minions", []))
            }
        elif match.startswith("pre") or match.startswith("un"):
            return {
                "minions_pre": salt.utils.data.sorted_ignorecase(
                    ret.get("minions_pre", [])
                )
            }
        elif match.startswith("rej"):
            return {
                "minions_rejected": salt.utils.data.sorted_ignorecase(
                    ret.get("minions_rejected", [])
                )
            }
        elif match.startswith("den"):
            return {
                "minions_denied": salt.utils.data.sorted_ignorecase(
                    ret.get("minions_denied", [])
                )
            }
        elif match.startswith("all"):
            return ret
        # this should never be reached
        return {}

    def key_str(self, match):
        """
        Return the specified public key or keys based on a glob
        """
        ret = {}
        for status, keys in self.glob_match(match).items():
            ret[status] = {}
            for key in salt.utils.data.sorted_ignorecase(keys):
                if status == self.DEN:
                    denied = self.cache.fetch("denied_keys", key)
                    if len(denied) == 1:
                        ret[status][key] = denied[0]
                    else:
                        ret[status][key] = denied
                else:
                    ret[status][key] = self.cache.fetch("keys", key).get("pub")
        return ret

    def key_str_all(self):
        """
        Return all managed key strings
        """
        return self.key_str("*")

    def change_state(
        self,
        from_state,
        to_state,
        match=None,
        match_dict=None,
        include_rejected=False,
        include_denied=False,
        include_accepted=False,
    ):
        """
        change key state from one state to another
        """
        if match is not None:
            matches = self.glob_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}
        keydirs = [from_state]
        if include_rejected:
            keydirs.append(self.REJ)
        if include_denied:
            keydirs.append(self.DEN)
        if include_accepted:
            keydirs.append(self.ACC)

        invalid_keys = []
        for keydir in keydirs:
            for keyname in matches.get(keydir, []):
                if to_state == self.DEN:
                    key = self.cache.fetch("keys", keyname)
                    self.cache.flush("keys", keyname)
                    self.cache.store("denied_keys", keyname, [key["pub"]])
                else:
                    if keydir == self.DEN:
                        # denied keys can be many per id, but we assume first for legacy
                        pub = self.cache.fetch("denied_keys", keyname)[0]
                        self.cache.flush("denied_keys", keyname)
                        key = {"pub": pub}
                    else:
                        key = self.cache.fetch("keys", keyname)

                    try:
                        salt.crypt.PublicKey.from_str(key["pub"])
                    except salt.exceptions.InvalidKeyError:
                        log.error("Invalid RSA public key: %s", keyname)
                        invalid_keys.append(keyname)
                        continue

                    key["state"] = self.DIR_MAP[to_state]
                    self.cache.store("keys", keyname, key)

                eload = {"result": True, "act": self.DIR_MAP[to_state], "id": keyname}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix="key"))

        for key in invalid_keys:
            sys.stderr.write(f"Unable to accept invalid key for {key}.\n")

        return self.glob_match(match) if match is not None else self.dict_match(matches)

    def accept(
        self, match=None, match_dict=None, include_rejected=False, include_denied=False
    ):
        """
        Accept public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".
        """
        return self.change_state(
            self.PEND,
            self.ACC,
            match,
            match_dict,
            include_rejected=include_rejected,
            include_denied=include_denied,
        )

    def accept_all(self):
        """
        Accept all keys in pre
        """
        return self.accept(match="*")

    def delete_key(
        self, match=None, match_dict=None, preserve_minions=None, revoke_auth=False
    ):
        """
        Delete public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".

        To preserve the master caches of minions who are matched, set preserve_minions
        """
        if match is not None:
            matches = self.glob_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}
        with salt.client.get_local_client(mopts=self.opts) as client:
            for status, keys in matches.items():
                for key in keys:
                    try:
                        if revoke_auth:
                            if self.opts.get("rotate_aes_key") is False:
                                print(
                                    "Immediate auth revocation specified but AES key"
                                    " rotation not allowed. Minion will not be"
                                    " disconnected until the master AES key is rotated."
                                )
                            else:
                                try:
                                    client.cmd_async(key, "saltutil.revoke_auth")
                                except salt.exceptions.SaltClientError:
                                    print(
                                        "Cannot contact Salt master. "
                                        "Connection for {} will remain up until "
                                        "master AES key is rotated or auth is revoked "
                                        "with 'saltutil.revoke_auth'.".format(key)
                                    )
                        if status == "minions_denied":
                            self.cache.flush("denied_keys", key)
                        else:
                            self.cache.flush("keys", key)
                        eload = {"result": True, "act": "delete", "id": key}
                        self.event.fire_event(
                            eload, salt.utils.event.tagify(prefix="key")
                        )
                    except OSError:
                        pass
        if self.opts.get("preserve_minions") is True:
            self.check_minion_cache(preserve_minions=matches.get("minions", []))
        else:
            self.check_minion_cache()
        if self.opts.get("rotate_aes_key"):
            salt.crypt.dropfile(
                self.opts["cachedir"], self.opts["user"], self.opts["id"]
            )
        return self.glob_match(match) if match is not None else self.dict_match(matches)

    def delete_den(self):
        """
        Delete all denied keys
        """
        self.cache.flush("denied_keys")
        self.check_minion_cache()
        return self.list_keys()

    def delete_all(self):
        """
        Delete all keys
        """
        for status, keys in self.list_keys().items():
            for key in keys:
                try:
                    self.cache.flush("keys", key)
                    eload = {"result": True, "act": "delete", "id": key}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix="key"))
                except OSError:
                    pass
        self.check_minion_cache()
        if self.opts.get("rotate_aes_key"):
            salt.crypt.dropfile(
                self.opts["cachedir"], self.opts["user"], self.opts["id"]
            )
        return self.list_keys()

    def reject(
        self, match=None, match_dict=None, include_accepted=False, include_denied=False
    ):
        """
        Reject public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".
        """
        ret = self.change_state(
            self.PEND,
            self.REJ,
            match,
            match_dict,
            include_accepted=include_accepted,
            include_denied=include_denied,
        )
        self.check_minion_cache()
        if self.opts.get("rotate_aes_key"):
            salt.crypt.dropfile(
                self.opts["cachedir"], self.opts["user"], self.opts["id"]
            )
        return ret

    def reject_all(self):
        """
        Reject all keys in pre
        """
        self.reject(match="*")
        self.check_minion_cache()
        if self.opts.get("rotate_aes_key"):
            salt.crypt.dropfile(
                self.opts["cachedir"], self.opts["user"], self.opts["id"]
            )
        return self.list_keys()

    def finger(self, match, hash_type=None):
        """
        Return the fingerprint for a specified key
        """
        if hash_type is None:
            hash_type = self.opts["hash_type"]

        matches = self.glob_match(match, full=True)
        ret = {}
        for status, keys in matches.items():
            ret[status] = {}
            for key in keys:
                if status == "minions_denied":
                    denied = self.cache.fetch("denied_keys", key)
                    for den in denied:
                        finger = salt.utils.crypt.pem_finger(
                            key=den.encode("utf-8"), sum_type=hash_type
                        )
                        ret[status].setdefault(key, []).append(finger)
                    # brush over some dumb backcompat with how denied keys work
                    # with the legacy system
                    if len(denied) == 1:
                        ret[status][key] = ret[status][key][0]
                else:
                    if status == "local":
                        pub = self.cache.fetch("master_keys", key).encode("utf-8")
                    else:
                        pub = self.cache.fetch("keys", key)["pub"].encode("utf-8")
                    ret[status][key] = salt.utils.crypt.pem_finger(
                        key=pub, sum_type=hash_type
                    )
        return ret

    def finger_all(self, hash_type=None):
        """
        Return fingerprints for all keys
        """
        if hash_type is None:
            hash_type = self.opts["hash_type"]

        return self.finger("*", hash_type=hash_type)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.event.destroy()

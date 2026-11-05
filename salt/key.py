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

    # ``--master`` scope on salt-key routes through :class:`MasterKey`,
    # which is a :class:`Key` subclass with the standard public API
    # (``list_keys``, ``accept``, ``reject``, ``delete_key``,
    # ``finger``) backed by the ``pki_dir/masters*/`` buckets.  No
    # separate dispatch table needed; :meth:`_run_cmd` just swaps
    # ``self.key`` for ``self.master_key`` when ``master_scope`` is
    # set.  Commands that ``MasterKey`` does not implement
    # (``gen_keys``, ``print``) fall back to the base-class method
    # inherited from :class:`Key`.

    def __init__(self, opts):
        # If client auth is enabled, load client config and set role
        if opts.get("client_auth"):
            import salt.config
            import salt.syspaths as syspaths

            # Load client config if not already loaded
            if "__role" not in opts:
                client_opts = salt.config.client_config(
                    opts.get("conf_file", os.path.join(syspaths.CONFIG_DIR, "master"))
                )
                # Merge client config with provided opts
                client_opts.update(opts)
                opts = client_opts
            # Set client role for PKI authentication
            opts["__role"] = "client"

        self.opts = opts
        import salt.wheel

        # Config decides which wheel client to use: ``RemoteWheelClient`` for
        # workstation operators (``__role=client``), the master-local
        # ``WheelClient`` otherwise.  No branch inside WheelClient itself.
        if opts.get("__role") == "client":
            self.client = salt.wheel.RemoteWheelClient(opts)
        else:
            self.client = salt.wheel.WheelClient(opts)
        # instantiate the key object for masterless mode
        if not opts.get("eauth") and not opts.get("client_auth"):
            self.key = get_key(opts)
            self.master_key = MasterKey(opts)
            self.client_key = ClientKey(opts)
        else:
            self.key = Key
            self.master_key = MasterKey
            self.client_key = ClientKey

        self.auth = {}

    def destroy(self):
        """
        Release resources this ``KeyCLI`` is holding.

        Without this, exiting ``salt-key`` drops the last reference to
        ``self.client`` (a :class:`salt.wheel.WheelClient`) and its
        ``__del__`` finalizer emits an ``unclosed WheelClient`` warning
        via :func:`salt.utils.resource_warnings.warn_until_close` -- once
        as a Python ``ResourceWarning`` (filtered by default) and once
        as a ``log.warning`` record that reaches stdout/stderr, breaking
        consumers that parse ``salt-key --out json``. The local ``Key``
        event bus is also closed here so Python 3.11 does not print
        ``Exception ignored in: BaseEventLoop.__del__`` during
        interpreter shutdown. Called automatically by the
        context-manager protocol.
        """
        if not self.opts.get("eauth"):
            # Drop the event bus on every instantiated Key subclass so
            # the EventPublisher socket is not left behind.  ``type``
            # guard skips the no-eauth path where attrs hold the class
            # (lazy construction in the eauth branch of ``__init__``).
            for attr in ("key", "master_key", "client_key"):
                obj = getattr(self, attr, None)
                if obj is not None and not isinstance(obj, type):
                    obj.destroy()
        client = getattr(self, "client", None)
        if client is not None:
            try:
                client.destroy()
            finally:
                self.client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()

    def _update_opts(self):
        # ``--kind`` is a unifying alias for the legacy per-scope
        # flags.  ``--kind master`` sets the same ``master_scope``
        # bit the legacy ``--master`` flag sets; ``--kind client``
        # rewrites the standard ``-L/-a/-d/-F`` opts into their
        # ``_client`` siblings so the dispatch below picks the
        # ClientKey route.  ``--kind minion`` (or no ``--kind``)
        # leaves opts untouched -- that is already the default.
        kind = self.opts.get("kind")
        if kind == "master":
            self.opts["master_scope"] = True
        elif kind == "client":
            for base_cmd in ("list", "accept", "reject", "print", "delete", "finger"):
                client_cmd = f"{base_cmd}_client"
                # Only rewrite when the client-suffixed opt is still
                # at its default (empty string / falsy) --- an
                # operator who passed both ``--kind client`` and
                # e.g. ``--list-clients=pre`` meant the latter.
                if self.opts.get(base_cmd) and not self.opts.get(client_cmd):
                    self.opts[client_cmd] = self.opts[base_cmd]
                    self.opts[base_cmd] = ""
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
            "list_clients",
            "accept_client",
            "reject_client",
            "print_client",
            "delete_client",
            "finger_client",
            "list_all",
        ):  # last is default
            if self.opts[cmd]:
                break
        # set match if needed
        if not cmd.startswith("gen_"):
            if cmd == "list_all":
                self.opts["match"] = "all"
            elif cmd == "list_clients":
                self.opts["match"] = self.opts[cmd] if self.opts[cmd] else "all"
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

        # client_auth alone (no eauth) uses PKI identity as the sole
        # authorization source.  When both are configured, we still need
        # to collect eauth creds so the master's stacked PKI+eauth
        # check receives them.
        if self.opts.get("client_auth") and not self.opts.get("eauth"):
            # Pure PKI identity -- no credentials needed in low dict.
            pass
        elif self.opts["eauth"]:
            if "token" in self.opts:
                try:
                    with salt.utils.files.fopen(
                        os.path.join(self.opts["cachedir"], ".root_key"), "r"
                    ) as fp_:
                        low["key"] = salt.utils.stringutils.to_unicode(fp_.readline())
                except OSError:
                    low["token"] = self.opts["token"]

            # If using eauth and a token hasn't already been loaded into
            # low, prompt the user to enter auth credentials.  Aliased
            # imports -- bare ``import salt.auth`` here would shadow the
            # module-level ``salt`` binding used earlier in this function
            # for ``salt.utils.files`` / ``salt.utils.stringutils``.
            if "token" not in low and "key" not in low and self.opts["eauth"]:
                from salt import auth as _auth

                resolver = _auth.Resolver(self.opts)
                res = resolver.cli(self.opts["eauth"])
                if not res:
                    log.error("Authentication failed")
                    return {}
                # Mint a token when the operator asked for one
                # (``--mktoken``) or when this is a remote CLI client
                # whose event-subscriber path needs it.  For plain
                # master-local salt-key, do not pre-mint: the historical
                # bad-eauth-creds behavior expects ``check_authentication``
                # on the wheel endpoint to see ``auth_type="eauth"`` and
                # reject bad PAM passwords through the eauth driver
                # rather than through a successful ``mk_token`` round-trip.
                want_token = (
                    self.opts.get("mktoken") or self.opts.get("__role") == "client"
                )
                if want_token:
                    tok = resolver.token_cli(self.opts["eauth"], res)
                    if tok and tok.get("token"):
                        low["token"] = tok["token"]
                low.update(res)
                low["eauth"] = self.opts["eauth"]
        else:
            # Late import to avoid circular import; aliased for the same
            # shadowing reason noted above.
            from salt.utils import master as _master_utils

            low["user"] = salt.utils.user.get_specific_user()
            low["key"] = _master_utils.get_master_key(
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
        if not self.opts.get("eauth") and not self.opts.get("client_auth"):
            # Route to the right Key subclass:
            #   - ``_client`` suffix     -> ClientKey  (upstream remote-CLI scope)
            #   - ``master_scope`` flag  -> MasterKey  (master-topology peer scope)
            #   - default                -> Key / MinionKey
            # All three subclasses share the base ``Key`` method
            # names (``list_keys``, ``accept``, ``reject``,
            # ``delete_key``, ``finger``, ...) so a single mapping
            # table suffices.
            if cmd.endswith("_client"):
                base_cmd = cmd[:-7]  # Remove "_client"
                mapped_cmd = self.CLI_KEY_MAP.get(base_cmd, base_cmd)
                fun = getattr(self.client_key, mapped_cmd)
            elif self.opts.get("master_scope"):
                mapped_cmd = self.CLI_KEY_MAP.get(cmd, cmd)
                fun = getattr(self.master_key, mapped_cmd)
            else:
                mapped_cmd = self.CLI_KEY_MAP.get(cmd, cmd)
                fun = getattr(self.key, mapped_cmd)

            args, kwargs = self._get_args_kwargs(fun, args)
            ret = fun(*args, **kwargs)
            if (
                isinstance(ret, dict)
                and "local" in ret
                and mapped_cmd not in ("finger", "finger_all")
            ):
                ret.pop("local", None)
            return ret

        # Remote execution with eauth or client_auth
        if cmd.endswith("_client"):
            # Client command for remote execution
            if cmd[:-7] in ("accept", "reject", "delete") and args is None:
                args = self.opts.get("match_dict", {}).get("clients")
            fstr = f"key.{cmd}"
        else:
            # Regular minion command for remote execution
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
            and fstr not in ("key.finger", "key.finger_all", "key.finger_client")
        ):
            ret.pop("local", None)

        return ret

    def _filter_ret(self, cmd, ret):
        if cmd.startswith("delete"):
            return ret

        # Use appropriate key constants based on command type
        key_obj = self.client_key if cmd.endswith("_client") else self.key

        keys = {}
        if key_obj.PEND in ret:
            keys[key_obj.PEND] = ret[key_obj.PEND]
        if self.opts["include_accepted"] and bool(ret.get(key_obj.ACC)):
            keys[key_obj.ACC] = ret[key_obj.ACC]
        if self.opts["include_rejected"] and bool(ret.get(key_obj.REJ)):
            keys[key_obj.REJ] = ret[key_obj.REJ]
        if self.opts["include_denied"] and bool(ret.get(key_obj.DEN)):
            keys[key_obj.DEN] = ret[key_obj.DEN]
        return keys

    def _print_no_match(self, cmd, match):
        key_type = "client" if cmd.endswith("_client") else "minion"
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
        msg = f"The key glob '{match}' does not match any {stat_str} {key_type} keys."
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
            # Handle both minion and client commands
            is_client_cmd = cmd.endswith("_client")
            base_cmd = cmd[:-7] if is_client_cmd else cmd

            if base_cmd in ("accept", "reject", "delete"):
                ret = self._run_cmd("glob_match" + ("_client" if is_client_cmd else ""))
                if not isinstance(ret, dict):
                    salt.output.display_output(ret, "key", opts=self.opts)
                    return ret
                ret = self._filter_ret(cmd, ret)
                if not ret:
                    self._print_no_match(cmd, self.opts["match"])
                    return
                print(
                    "The following keys are going to be {}ed:".format(
                        base_cmd.rstrip("e")
                    )
                )
                salt.output.display_output(ret, "key", opts=self.opts)

                if not self.opts.get("yes", False):
                    try:
                        if base_cmd.startswith("delete"):
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
                if base_cmd in ("accept", "reject", "delete"):
                    if base_cmd == "delete":
                        ret = list_ret
                    key_type = "client" if is_client_cmd else "minion"
                    for keys_group in ret.values():
                        for key_id in keys_group:
                            print(
                                "Key for {} {} {}ed.".format(
                                    key_type, key_id, base_cmd.rstrip("e")
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

    KIND = "minion"

    ACC = "minions"
    PEND = "minions_pre"
    REJ = "minions_rejected"
    DEN = "minions_denied"

    # handle transitions from legacy naming to simpler new format
    STATE_MAP = {"accepted": ACC, "rejected": REJ, "pending": PEND, "denied": DEN}
    DIR_MAP = {v: k for k, v in STATE_MAP.items()}

    # Short-form ``act`` strings fired on ``salt/key`` events.  Peer
    # masters in a cluster (``salt.master.EventMonitor._PEER_KEY_STATE``)
    # and the auto-accept auth path both key off the short form, so
    # ``change_state`` must emit short-form values here, not the
    # long-form ``DIR_MAP`` values that are stored as the local cache
    # ``state`` field.  See issue #70401.
    ACT_MAP = {
        ACC: "accept",
        REJ: "reject",
        PEND: "pend",
        DEN: "deny",
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

    def _bucket_path(self, bucket):
        """
        Return (and best-effort ensure) ``<pki_dir>/<bucket>/``.

        Shared primitive used by subclasses that store keys on the
        filesystem (base :class:`Key` minion scope,
        :class:`MasterKey` peer-master scope).  :class:`ClientKey`
        overrides storage to use a cache bank and does not call
        this.
        """
        path = os.path.join(self.pki_dir, bucket)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:  # pragma: no cover - best-effort
            pass
        return path

    def _list_bucket(self, bucket):
        """
        Return the sorted set of ``.pub`` filenames in a bucket with
        the ``.pub`` suffix stripped.

        Shared primitive matching :meth:`_bucket_path`.
        """
        path = self._bucket_path(bucket)
        if not os.path.isdir(path):
            return []
        names = []
        for entry in os.listdir(path):
            if entry.endswith(".pub"):
                names.append(entry[: -len(".pub")])
        return sorted(names)

    def _check_minions_directories(self):
        """
        Return the minion keys directory paths
        """
        minions_accepted = self._bucket_path(self.ACC)
        minions_pre = self._bucket_path(self.PEND)
        minions_rejected = self._bucket_path(self.REJ)
        minions_denied = self._bucket_path(self.DEN)
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
        self.master_keys.find_or_create_keys(keyname, keysize=keysize, cache=cache)
        pub = cache.fetch("master_keys", f"{keyname}.pub")
        return salt.utils.crypt.pem_finger(key=pub)

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
        if self.opts.get("preserve_minion_cache", False):
            return

        if preserve_minions is None:
            preserve_minions = []
        preserve_minions = set(preserve_minions)

        keys = self.list_keys()

        for val in keys.values():
            preserve_minions.update(val)

        # we use a new cache instance here as we dont want the key cache
        cache = salt.cache.factory(self.opts)

        for bank in ["grains", "pillar"]:
            clist = set(cache.list(bank))
            for minion in clist - preserve_minions:
                # pillar optionally encodes pillarenv in the key as minion:$pillarenv
                if ":" in minion and minion.split(":")[0] in preserve_minions:
                    continue
                cache.flush(bank, minion)

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
        if not isinstance(match, list):
            match = [match]
        for status, keys in matches.items():
            if match == ["*"] and keys:
                ret[status] = keys
                continue
            for key in salt.utils.data.sorted_ignorecase(keys):
                for match_item in match:
                    if fnmatch.fnmatch(key, match_item):
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
        Return a dict of managed keys and what the key status are.

        Uses ``cache.list_all("keys")`` when the configured cache driver
        supports it (``mmap_key`` and ``localfs_key`` both do), which
        walks the keys store in a single O(occupied) pass and avoids
        N per-key cache probes. Falls back to ``list`` + per-key
        ``fetch`` for any driver that does not implement ``list_all``.
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

        try:
            entries = self.cache.list_all("keys")
        except salt.exceptions.SaltCacheError:
            entries = None

        if entries is not None:
            for id_, entry in entries.items():
                state = (entry or {}).get("state")
                if state == "accepted":
                    ret["minions"].append(id_)
                elif state == "pending":
                    ret["minions_pre"].append(id_)
                elif state == "rejected":
                    ret["minions_rejected"].append(id_)
            for key in ret:
                ret[key] = salt.utils.data.sorted_ignorecase(ret[key])
        else:
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

                eload = {"result": True, "act": self.ACT_MAP[to_state], "id": keyname}
                # Cluster masters: include the public key body so peer
                # masters can populate their local ``pki_dir/<bucket>/<id>``
                # without a shared filesystem.  The bytes are only useful
                # to other cluster members; they're harmless on standalone
                # masters that ignore the field.
                pub_bytes = None
                if to_state == self.DEN:
                    pub_bytes = key
                elif "pub" in (key or {}):
                    pub_bytes = key["pub"]
                if pub_bytes:
                    eload["pub"] = pub_bytes
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

    def destroy(self):
        event = self.__dict__.get("event")
        if event is not None:
            event.destroy()
            self.__dict__.pop("event", None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()


class MasterKey(Key):
    """
    Manage peer-master keys on a master-topology cluster.

    Mirrors the minion-scoped base :class:`Key` but operates on the
    ``pki_dir/masters*/`` buckets used by the master-topology
    feature.  The accepted/pending/rejected/denied cluster peers
    live in ``pki_dir/{masters,masters_pre,masters_rejected,
    masters_denied}/<cluster_id>.pub``; each on-disk file is the
    peer master's ``master_identity.pub`` PEM bytes.

    Clustered callers (``opts["cluster_peers"]`` non-empty, which
    we proxy via the presence of an ``opts["raft_service"]`` hook)
    must propose the attach/detach to Raft FIRST and let the
    :class:`TopologyStateMachine` apply handler do the file-move
    atomically; if salt-key renamed the file first and then crashed
    before proposing, the file-system state would be ahead of the
    Raft log, violating the "every cluster peer sees the same state"
    invariant.  Solo masters (no raft_service) move the file
    directly.

    Public API aligned with the base :class:`Key` so :class:`KeyCLI`
    can dispatch uniformly: :meth:`list_keys`, :meth:`accept`,
    :meth:`reject`, :meth:`delete_key`, :meth:`finger`.  The
    cluster-id-based signature overrides the glob-match signature
    of the base class --- master keys are identified by exact
    ``cluster_id``, not glob.
    """

    KIND = "master"
    ACC = "masters"
    PEND = "masters_pre"
    REJ = "masters_rejected"
    DEN = "masters_denied"

    _MASTER_BUCKETS = (
        ("accepted", ACC),
        ("pending", PEND),
        ("rejected", REJ),
        ("denied", DEN),
    )

    def _validate_cluster_id(self, cluster_id):
        """
        Validate a ``cluster_id`` matches the topology ``CLUSTER_ID_RE``
        and is not one of the reserved MmapCache sentinel names.

        Rejects at the ``salt-key`` boundary so a bad id never reaches
        the Raft propose path.  :class:`TopologyStateMachine` performs
        the same check at apply time for hostile-peer defense.
        """
        import re  # local import; stdlib, cheap on repeat.

        from salt.config.topology import _RESERVED_CLUSTER_IDS, CLUSTER_ID_RE

        if not isinstance(cluster_id, str) or not cluster_id:
            raise ValueError("cluster_id must be a non-empty string")
        if cluster_id in _RESERVED_CLUSTER_IDS:
            raise ValueError(f"cluster_id {cluster_id!r} is a reserved sentinel name")
        if not re.match(CLUSTER_ID_RE, cluster_id):
            raise ValueError(
                f"cluster_id {cluster_id!r} does not match {CLUSTER_ID_RE}"
            )

    # ``_bucket_path`` and ``_list_bucket`` are inherited from
    # :class:`Key`; MasterKey only overrides the bucket CONSTANTS
    # (ACC/PEND/REJ/DEN point at ``masters*``) and the public
    # methods below that operate per-cluster_id instead of per-glob.

    def list_keys(self):
        """
        Return the four cluster-namespace buckets under ``pki_dir/``.

        Each bucket is the sorted set of ``<cluster_id>`` filenames
        (``.pub`` stripped) found under ``pki_dir/masters*/``.
        """
        return {
            name: self._list_bucket(bucket) for name, bucket in self._MASTER_BUCKETS
        }

    def list_status(self, match=None):
        """
        Alias so ``salt-key -L --master`` (which is routed via
        CLI_KEY_MAP["list"] == "list_status") returns the full bucket
        inventory.  ``match`` is ignored because master keys are
        exact-matched by cluster_id, not filtered by status glob.
        """
        return self.list_keys()

    def _raft_service(self):
        """
        Return the Raft service hook if we're on a clustered master,
        else ``None`` for solo-master code paths.

        A clustered master has a ``raft_service`` configured on opts
        (set up by :class:`TopologyLinkManager` on master start).
        Solo masters leave it unset, and the master-scope key methods
        rename files directly.
        """
        return self.opts.get("raft_service")

    def accept(
        self, match=None, match_dict=None, include_rejected=False, include_denied=False
    ):
        """
        Accept a pending peer-master key by ``cluster_id``.

        ``match`` is interpreted as an exact ``cluster_id``; glob is
        not supported for master keys (cluster identities are unique
        and operator-chosen).  ``match_dict``, ``include_rejected``,
        and ``include_denied`` are accepted for signature parity
        with :meth:`Key.accept` but are no-ops on this class.

        Propose-first ordering on clustered masters: when a Raft
        service hook is configured, we propose a
        ``MASTER_PEER_ATTACH`` entry carrying the peer's PEM bytes
        and rely on the :class:`TopologyStateMachine` apply handler
        to rename ``masters_pre/<id>.pub`` into ``masters/<id>.pub``
        atomically on every peer.  salt-key must NOT rename the
        file before proposing --- a crash between the rename and
        the propose would leave the file in ``masters/`` on this
        host with no Raft commit, breaking cluster-peer consistency.

        Solo masters (no raft_service) rename the file directly from
        ``masters_pre/`` to ``masters/``.  Operator restarts the
        publish daemon (or the daemon's PKI watcher picks up the
        ``salt/key`` event this method fires) to reconcile.
        """
        cluster_id = match
        self._validate_cluster_id(cluster_id)

        pending_dir = self._bucket_path(self.PEND)
        accepted_dir = self._bucket_path(self.ACC)
        pending_path = os.path.join(pending_dir, f"{cluster_id}.pub")
        accepted_path = os.path.join(accepted_dir, f"{cluster_id}.pub")

        if not os.path.exists(pending_path):
            return {"accepted": []}

        with salt.utils.files.fopen(pending_path, "rb") as fh:
            pub_bytes = fh.read()

        raft = self._raft_service()
        if raft is not None and hasattr(raft, "propose_peer_attach"):
            import time as _time

            try:
                raft.propose_peer_attach(
                    cluster_id=cluster_id,
                    public_key=pub_bytes,
                    endpoints=(),
                    attached_at=_time.time(),
                )
            except Exception as exc:  # pylint: disable=broad-except
                try:
                    from salt.cluster.consensus.service import (  # pylint: disable=import-outside-toplevel
                        MixedVersionClusterError,
                    )
                except ImportError:
                    MixedVersionClusterError = None
                if MixedVersionClusterError is not None and isinstance(
                    exc, MixedVersionClusterError
                ):
                    print(
                        f"salt-key: cannot accept peer master {cluster_id!r}: {exc}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                raise
        else:
            os.replace(pending_path, accepted_path)

        self.event.fire_event(
            {"result": True, "act": "accept", "id": cluster_id, "scope": "master"},
            salt.utils.event.tagify(prefix="key"),
        )
        return {"accepted": [cluster_id]}

    def reject(
        self, match=None, match_dict=None, include_accepted=False, include_denied=False
    ):
        """
        Reject a pending peer-master key by ``cluster_id``.

        Rejection is a local operator decision --- it is NOT
        replicated via Raft.  The file moves from ``masters_pre/``
        to ``masters_rejected/``.  ``match_dict`` /
        ``include_accepted`` / ``include_denied`` are accepted for
        signature parity with :meth:`Key.reject` but are no-ops.
        """
        cluster_id = match
        self._validate_cluster_id(cluster_id)

        pending_path = os.path.join(self._bucket_path(self.PEND), f"{cluster_id}.pub")
        rejected_path = os.path.join(self._bucket_path(self.REJ), f"{cluster_id}.pub")
        if not os.path.exists(pending_path):
            return {"rejected": []}
        os.replace(pending_path, rejected_path)
        self.event.fire_event(
            {"result": True, "act": "reject", "id": cluster_id, "scope": "master"},
            salt.utils.event.tagify(prefix="key"),
        )
        return {"rejected": [cluster_id]}

    def delete_key(
        self,
        match=None,
        match_dict=None,
        preserve_minions=None,
        revoke_auth=False,
    ):
        """
        Delete / revoke an accepted peer-master key by ``cluster_id``.

        Clustered masters propose ``MASTER_PEER_DETACH``; the apply
        handler removes (or moves to ``masters_denied/``) the file.
        As with :meth:`accept`, salt-key does NOT touch the file
        before proposing so a propose-then-crash cannot leave a
        half-applied state.

        Solo masters delete the file directly.

        ``match_dict`` / ``preserve_minions`` / ``revoke_auth`` are
        accepted for signature parity with :meth:`Key.delete_key`
        but are no-ops on peer-master keys.
        """
        cluster_id = match
        self._validate_cluster_id(cluster_id)

        accepted_path = os.path.join(self._bucket_path(self.ACC), f"{cluster_id}.pub")

        raft = self._raft_service()
        if raft is not None and hasattr(raft, "propose_peer_detach"):
            try:
                raft.propose_peer_detach(cluster_id=cluster_id, reason="revoked")
            except Exception as exc:  # pylint: disable=broad-except
                try:
                    from salt.cluster.consensus.service import (  # pylint: disable=import-outside-toplevel
                        MixedVersionClusterError,
                    )
                except ImportError:
                    MixedVersionClusterError = None
                if MixedVersionClusterError is not None and isinstance(
                    exc, MixedVersionClusterError
                ):
                    print(
                        f"salt-key: cannot revoke peer master {cluster_id!r}: {exc}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                raise
        else:
            if os.path.exists(accepted_path):
                os.remove(accepted_path)

        self.event.fire_event(
            {"result": True, "act": "delete", "id": cluster_id, "scope": "master"},
            salt.utils.event.tagify(prefix="key"),
        )
        return {"deleted": [cluster_id]}

    def finger(self, match, hash_type=None):
        """
        Return the fingerprint of a peer-master key by ``cluster_id``.

        Searches the four ``masters*/`` buckets in priority order
        (accepted, pending, rejected, denied).  Returns the empty
        string if the peer has no key in any bucket, mirroring
        :func:`salt.utils.crypt.pem_finger` on a missing path.
        """
        cluster_id = match
        if hash_type is None:
            hash_type = self.opts.get("hash_type", "sha256")
        for _, bucket in self._MASTER_BUCKETS:
            path = os.path.join(self._bucket_path(bucket), f"{cluster_id}.pub")
            if os.path.exists(path):
                with salt.utils.files.fopen(path, "rb") as fh:
                    pem = fh.read()
                return salt.utils.crypt.pem_finger(key=pem, sum_type=hash_type)
        return ""


class ClientKey(Key):
    """
    Manage client keys on the master.

    Client keys are separate from minion keys and use different cache banks:
    - client_keys: for accepted/pending/rejected client public keys
    - client_denied_keys: for denied client public keys

    This mirrors the minion key management but with separate storage.
    """

    KIND = "client"

    ACC = "clients"
    PEND = "clients_pre"
    REJ = "clients_rejected"
    DEN = "clients_denied"

    # Override state maps for client-specific directories
    STATE_MAP = {
        "accepted": "clients",
        "rejected": "clients_rejected",
        "pending": "clients_pre",
        "denied": "clients_denied",
    }
    DIR_MAP = {
        "clients": "accepted",
        "clients_rejected": "rejected",
        "clients_pre": "pending",
        "clients_denied": "denied",
    }

    ACT_MAP = {
        "clients": "accept",
        "clients_rejected": "reject",
        "clients_pre": "pend",
        "clients_denied": "denied",
    }

    # Cache keys for client authentication
    KEYS_CACHE = "client_keys"
    DENIED_CACHE = "client_denied_keys"

    def list_match(self, match):
        """
        Accept a glob which to match the of a key and return the key's location
        """
        ret = {}
        if isinstance(match, str):
            match = match.split(",")

        for name in match:
            key = self.cache.fetch(self.KEYS_CACHE, name)
            if key:
                try:
                    ret.setdefault(self.STATE_MAP[key["state"]], [])
                    ret[self.STATE_MAP[key["state"]]].append(name)
                except KeyError:
                    log.error("unexpected key state returned for %s: %s", name, key)

            denied_keys = self.cache.fetch(self.DENIED_CACHE, name)
            if denied_keys:
                ret.setdefault(self.DEN, [])
                ret[self.DEN].append(name)
        return ret

    def list_keys(self):
        """
        Return a dict of managed client keys and what the key status are
        """
        ret = {
            "clients_pre": [],
            "clients_rejected": [],
            "clients": [],
            "clients_denied": [],
        }
        for id_ in salt.utils.data.sorted_ignorecase(self.cache.list(self.KEYS_CACHE)):
            key = self.cache.fetch(self.KEYS_CACHE, id_)

            if key["state"] == "accepted":
                ret["clients"].append(id_)
            elif key["state"] == "pending":
                ret["clients_pre"].append(id_)
            elif key["state"] == "rejected":
                ret["clients_rejected"].append(id_)

        for id_ in salt.utils.data.sorted_ignorecase(
            self.cache.list(self.DENIED_CACHE)
        ):
            ret["clients_denied"].append(id_)
        return ret

    def key_str(self, match):
        """
        Return the specified public key or keys based on a glob
        """
        ret = {}
        for status, keys in self.glob_match(match).items():
            ret[status] = {}
            for key in salt.utils.data.sorted_ignorecase(keys):
                if status == self.DEN:
                    denied = self.cache.fetch(self.DENIED_CACHE, key)
                    if len(denied) == 1:
                        ret[status][key] = denied[0]
                    else:
                        ret[status][key] = denied
                else:
                    ret[status][key] = self.cache.fetch(self.KEYS_CACHE, key).get("pub")
        return ret

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
        Change client key state from one state to another
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
                    key = self.cache.fetch(self.KEYS_CACHE, keyname)
                    self.cache.flush(self.KEYS_CACHE, keyname)
                    self.cache.store(self.DENIED_CACHE, keyname, [key["pub"]])
                else:
                    if keydir == self.DEN:
                        # denied keys can be many per id, but we assume first for legacy
                        pub = self.cache.fetch(self.DENIED_CACHE, keyname)[0]
                        self.cache.flush(self.DENIED_CACHE, keyname)
                        key = {"pub": pub}
                    else:
                        key = self.cache.fetch(self.KEYS_CACHE, keyname)

                    try:
                        salt.crypt.PublicKey.from_str(key["pub"])
                    except salt.exceptions.InvalidKeyError:
                        log.error("Invalid RSA public key: %s", keyname)
                        invalid_keys.append(keyname)
                        continue

                    key["state"] = self.DIR_MAP[to_state]
                    self.cache.store(self.KEYS_CACHE, keyname, key)

                eload = {"result": True, "act": self.DIR_MAP[to_state], "id": keyname}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix="key"))

        for key in invalid_keys:
            sys.stderr.write(f"Unable to accept invalid key for {key}.\n")

        return self.glob_match(match) if match is not None else self.dict_match(matches)

    def delete_key(
        self, match=None, match_dict=None, preserve_minions=None, revoke_auth=False
    ):
        """
        Delete client public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".

        Note: preserve_minions and revoke_auth are ignored for client keys
        """
        if match is not None:
            matches = self.glob_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}

        for status, keys in matches.items():
            for key in keys:
                try:
                    if status == "clients_denied":
                        self.cache.flush(self.DENIED_CACHE, key)
                    else:
                        self.cache.flush(self.KEYS_CACHE, key)
                    eload = {"result": True, "act": "delete", "id": key}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix="key"))
                except OSError:
                    pass

        # Return the original matches (keys that were deleted), not current state
        return matches

    def delete_den(self):
        """
        Delete all denied client keys
        """
        self.cache.flush(self.DENIED_CACHE)
        return self.list_keys()

    def delete_all(self):
        """
        Delete all client keys
        """
        for status, keys in self.list_keys().items():
            for key in keys:
                try:
                    self.cache.flush(self.KEYS_CACHE, key)
                    eload = {"result": True, "act": "delete", "id": key}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix="key"))
                except OSError:
                    pass
        return self.list_keys()

    def local_keys(self):
        """
        Return a dict of local keys (empty for clients as they don't have local keys)
        """
        return {}

    def list_status(self, match):
        """
        Return a dict of managed client keys under a named status
        """
        ret = self.all_keys()
        if match.startswith("acc"):
            return {
                "clients": salt.utils.data.sorted_ignorecase(ret.get("clients", []))
            }
        elif match.startswith("pre") or match.startswith("un"):
            return {
                "clients_pre": salt.utils.data.sorted_ignorecase(
                    ret.get("clients_pre", [])
                )
            }
        elif match.startswith("rej"):
            return {
                "clients_rejected": salt.utils.data.sorted_ignorecase(
                    ret.get("clients_rejected", [])
                )
            }
        elif match.startswith("den"):
            return {
                "clients_denied": salt.utils.data.sorted_ignorecase(
                    ret.get("clients_denied", [])
                )
            }
        elif match.startswith("all"):
            return ret
        # this should never be reached
        return {}

    def finger(self, match, hash_type=None):
        """
        Return the fingerprint for a specified client key
        """
        if hash_type is None:
            hash_type = self.opts["hash_type"]

        matches = self.glob_match(match, full=True)
        ret = {}
        for status, keys in matches.items():
            ret[status] = {}
            for key in keys:
                if status == "clients_denied":
                    denied = self.cache.fetch(self.DENIED_CACHE, key)
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
                    pub = self.cache.fetch(self.KEYS_CACHE, key)["pub"].encode("utf-8")
                    ret[status][key] = salt.utils.crypt.pem_finger(
                        key=pub, sum_type=hash_type
                    )
        return ret

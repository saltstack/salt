"""
Salt's pluggable authentication system

This system allows for authentication to be managed in a module pluggable way
so that any external authentication system can be used inside of Salt
"""

# 1. Create auth loader instance
# 2. Accept arguments as a dict
# 3. Verify with function introspection
# 4. Execute auth function
# 5. Cache auth token with relative data opts['token_dir']
# 6. Interface to verify tokens

import getpass
import logging
import random
import time
from collections.abc import Iterable, Mapping

import salt.config
import salt.exceptions
import salt.loader
import salt.payload
import salt.transport.client
import salt.utils.args
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.minions
import salt.utils.user
import salt.utils.versions
import salt.utils.zeromq

log = logging.getLogger(__name__)

AUTH_INTERNAL_KEYWORDS = frozenset(
    [
        "client",
        "cmd",
        "eauth",
        "fun",
        "gather_job_timeout",
        "kwarg",
        "match",
        "metadata",
        "print_event",
        "raw",
        "yield_pub_data",
    ]
)


class LoadAuth:
    """
    Wrap the authentication system to handle peripheral components
    """

    def __init__(self, opts, ckminions=None):
        self.opts = opts
        self.max_fail = 1.0
        self.auth = salt.loader.auth(opts)
        self.tokens = salt.loader.eauth_tokens(opts)
        self.ckminions = ckminions or salt.utils.minions.CkMinions(opts)

    def load_name(self, load):
        """
        Return the primary name associate with the load, if an empty string
        is returned then the load does not match the function
        """
        if "eauth" not in load:
            return ""
        fstr = "{}.auth".format(load["eauth"])
        if fstr not in self.auth:
            return ""
        try:
            pname_arg = salt.utils.args.arg_lookup(self.auth[fstr])["args"][0]
            return load[pname_arg]
        except IndexError:
            return ""

    def __auth_call(self, load):
        """
        Return the token and set the cache data for use

        Do not call this directly! Use the time_auth method to overcome timing
        attacks
        """
        if "eauth" not in load:
            return False
        fstr = "{}.auth".format(load["eauth"])
        if fstr not in self.auth:
            return False
        # When making auth calls, only username, password, auth, and token
        # are valid, so we strip anything else out.
        _valid = ["username", "password", "eauth", "token"]
        _load = {key: value for (key, value) in load.items() if key in _valid}

        fcall = salt.utils.args.format_call(
            self.auth[fstr], _load, expected_extra_kws=AUTH_INTERNAL_KEYWORDS
        )
        try:
            if "kwargs" in fcall:
                return self.auth[fstr](*fcall["args"], **fcall["kwargs"])
            else:
                return self.auth[fstr](*fcall["args"])
        except Exception as e:  # pylint: disable=broad-except
            log.debug("Authentication module threw %s", e)
            return False

    def time_auth(self, load):
        """
        Make sure that all failures happen in the same amount of time
        """
        start = time.time()
        ret = self.__auth_call(load)
        if ret:
            return ret
        f_time = time.time() - start
        if f_time > self.max_fail:
            self.max_fail = f_time
        deviation = self.max_fail / 4
        r_time = random.SystemRandom().uniform(
            self.max_fail - deviation, self.max_fail + deviation
        )
        while start + r_time > time.time():
            time.sleep(0.001)
        return False

    def __get_acl(self, load):
        """
        Returns ACL for a specific user.
        Returns None if eauth doesn't provide any for the user. I. e. None means: use acl declared
        in master config.
        """
        if "eauth" not in load:
            return None
        mod = self.opts["eauth_acl_module"]
        if not mod:
            mod = load["eauth"]
        fstr = "{}.acl".format(mod)
        if fstr not in self.auth:
            return None
        fcall = salt.utils.args.format_call(
            self.auth[fstr], load, expected_extra_kws=AUTH_INTERNAL_KEYWORDS
        )
        try:
            return self.auth[fstr](*fcall["args"], **fcall["kwargs"])
        except Exception as e:  # pylint: disable=broad-except
            log.debug("Authentication module threw %s", e)
            return None

    def __process_acl(self, load, auth_list):
        """
        Allows eauth module to modify the access list right before it'll be applied to the request.
        For example ldap auth module expands entries
        """
        if "eauth" not in load:
            return auth_list
        fstr = "{}.process_acl".format(load["eauth"])
        if fstr not in self.auth:
            return auth_list
        try:
            return self.auth[fstr](auth_list, self.opts)
        except Exception as e:  # pylint: disable=broad-except
            log.debug("Authentication module threw %s", e)
            return auth_list

    def get_groups(self, load):
        """
        Read in a load and return the groups a user is a member of
        by asking the appropriate provider
        """
        if "eauth" not in load:
            return False
        fstr = "{}.groups".format(load["eauth"])
        if fstr not in self.auth:
            return False
        fcall = salt.utils.args.format_call(
            self.auth[fstr], load, expected_extra_kws=AUTH_INTERNAL_KEYWORDS
        )
        try:
            return self.auth[fstr](*fcall["args"], **fcall["kwargs"])
        except IndexError:
            return False
        except Exception:  # pylint: disable=broad-except
            return None

    def _allow_custom_expire(self, load):
        """
        Return bool if requesting user is allowed to set custom expire
        """
        expire_override = self.opts.get("token_expire_user_override", False)

        if expire_override is True:
            return True

        if isinstance(expire_override, Mapping):
            expire_whitelist = expire_override.get(load["eauth"], [])
            if isinstance(expire_whitelist, Iterable):
                if load.get("username") in expire_whitelist:
                    return True

        return False

    def mk_token(self, load):
        """
        Run time_auth and create a token. Return False or the token
        """
        if not self.authenticate_eauth(load):
            return {}

        if self._allow_custom_expire(load):
            token_expire = load.pop("token_expire", self.opts["token_expire"])
        else:
            _ = load.pop("token_expire", None)
            token_expire = self.opts["token_expire"]

        tdata = {
            "start": time.time(),
            "expire": time.time() + token_expire,
            "name": self.load_name(load),
            "eauth": load["eauth"],
        }

        if self.opts["keep_acl_in_token"]:
            acl_ret = self.__get_acl(load)
            tdata["auth_list"] = acl_ret

        groups = self.get_groups(load)
        if groups:
            tdata["groups"] = groups

        return self.tokens["{}.mk_token".format(self.opts["eauth_tokens"])](
            self.opts, tdata
        )

    def get_tok(self, tok):
        """
        Return the name associated with the token, or False if the token is
        not valid
        """
        tdata = {}
        try:
            tdata = self.tokens["{}.get_token".format(self.opts["eauth_tokens"])](
                self.opts, tok
            )
        except salt.exceptions.SaltDeserializationError:
            log.warning("Failed to load token %r - removing broken/empty file.", tok)
            rm_tok = True
        else:
            if not tdata:
                return {}
            rm_tok = False

        if tdata.get("expire", 0) < time.time():
            # If expire isn't present in the token it's invalid and needs
            # to be removed. Also, if it's present and has expired - in
            # other words, the expiration is before right now, it should
            # be removed.
            rm_tok = True

        if rm_tok:
            self.rm_token(tok)
            return {}

        return tdata

    def list_tokens(self):
        """
        List all tokens in eauth_tokn storage.
        """
        return self.tokens["{}.list_tokens".format(self.opts["eauth_tokens"])](
            self.opts
        )

    def rm_token(self, tok):
        """
        Remove the given token from token storage.
        """
        self.tokens["{}.rm_token".format(self.opts["eauth_tokens"])](self.opts, tok)

    def authenticate_token(self, load):
        """
        Authenticate a user by the token specified in load.
        Return the token object or False if auth failed.
        """
        token = self.get_tok(load["token"])

        # Bail if the token is empty or if the eauth type specified is not allowed
        if not token or token["eauth"] not in self.opts["external_auth"]:
            log.warning('Authentication failure of type "token" occurred.')
            return False

        return token

    def authenticate_eauth(self, load):
        """
        Authenticate a user by the external auth module specified in load.
        Return True on success or False on failure.
        """
        if "eauth" not in load:
            log.warning('Authentication failure of type "eauth" occurred.')
            return False

        if load["eauth"] not in self.opts["external_auth"]:
            log.warning('The eauth system "%s" is not enabled', load["eauth"])
            log.warning('Authentication failure of type "eauth" occurred.')
            return False

        # Perform the actual authentication. If we fail here, do not
        # continue.
        if not self.time_auth(load):
            log.warning('Authentication failure of type "eauth" occurred.')
            return False

        return True

    def authenticate_key(self, load, key):
        """
        Authenticate a user by the key passed in load.
        Return the effective user id (name) if it's different from the specified one (for sudo).
        If the effective user id is the same as the passed one, return True on success or False on
        failure.
        """
        error_msg = 'Authentication failure of type "user" occurred.'
        auth_key = load.pop("key", None)
        if auth_key is None:
            log.warning(error_msg)
            return False

        if "user" in load:
            auth_user = AuthUser(load["user"])
            if auth_user.is_sudo():
                # If someone sudos check to make sure there is no ACL's around their username
                if auth_key != key[self.opts.get("user", "root")]:
                    log.warning(error_msg)
                    return False
                return auth_user.sudo_name()
            elif (
                load["user"] == self.opts.get("user", "root") or load["user"] == "root"
            ):
                if auth_key != key[self.opts.get("user", "root")]:
                    log.warning(
                        "Master runs as %r, but user in payload is %r",
                        self.opts.get("user", "root"),
                        load["user"],
                    )
                    log.warning(error_msg)
                    return False
            elif auth_user.is_running_user():
                if auth_key != key.get(load["user"]):
                    log.warning(error_msg)
                    return False
            elif auth_key == key.get("root"):
                pass
            else:
                if load["user"] in key:
                    # User is authorised, check key and check perms
                    if auth_key != key[load["user"]]:
                        log.warning(error_msg)
                        return False
                    return load["user"]
                else:
                    log.warning(error_msg)
                    return False
        else:
            if auth_key != key[salt.utils.user.get_user()]:
                log.warning(error_msg)
                return False
        return True

    def get_auth_list(self, load, token=None):
        """
        Retrieve access list for the user specified in load.
        The list is built by eauth module or from master eauth configuration.
        Return None if current configuration doesn't provide any ACL for the user. Return an empty
        list if the user has no rights to execute anything on this master and returns non-empty list
        if user is allowed to execute particular functions.
        """
        # Get auth list from token
        if token and self.opts["keep_acl_in_token"] and "auth_list" in token:
            return token["auth_list"]
        # Get acl from eauth module.
        auth_list = self.__get_acl(load)
        if auth_list is not None:
            return auth_list

        eauth = token["eauth"] if token else load["eauth"]
        if eauth not in self.opts["external_auth"]:
            # No matching module is allowed in config
            log.debug('The eauth system "%s" is not enabled', eauth)
            log.warning("Authorization failure occurred.")
            return None

        if token:
            name = token["name"]
            groups = token.get("groups")
        else:
            name = self.load_name(load)  # The username we are attempting to auth with
            groups = self.get_groups(load)  # The groups this user belongs to
        eauth_config = self.opts["external_auth"][eauth]
        if not eauth_config:
            log.debug('eauth "%s" configuration is empty', eauth)

        if not groups:
            groups = []

        # We now have an authenticated session and it is time to determine
        # what the user has access to.
        auth_list = self.ckminions.fill_auth_list(eauth_config, name, groups)

        auth_list = self.__process_acl(load, auth_list)

        log.trace("Compiled auth_list: %s", auth_list)

        return auth_list

    def check_authentication(self, load, auth_type, key=None, show_username=False):
        """
        .. versionadded:: 2018.3.0

        Go through various checks to see if the token/eauth/user can be authenticated.

        Returns a dictionary containing the following keys:

        - auth_list
        - username
        - error

        If an error is encountered, return immediately with the relevant error dictionary
        as authentication has failed. Otherwise, return the username and valid auth_list.
        """
        auth_list = []
        username = load.get("username", "UNKNOWN")
        ret = {"auth_list": auth_list, "username": username, "error": {}}

        # Authenticate
        if auth_type == "token":
            token = self.authenticate_token(load)
            if not token:
                ret["error"] = {
                    "name": "TokenAuthenticationError",
                    "message": 'Authentication failure of type "token" occurred.',
                }
                return ret

            # Update username for token
            username = token["name"]
            ret["username"] = username
            auth_list = self.get_auth_list(load, token=token)
        elif auth_type == "eauth":
            if not self.authenticate_eauth(load):
                ret["error"] = {
                    "name": "EauthAuthenticationError",
                    "message": 'Authentication failure of type "eauth" occurred for user {}.'.format(
                        username
                    ),
                }
                return ret

            auth_list = self.get_auth_list(load)
        elif auth_type == "user":
            auth_ret = self.authenticate_key(load, key)
            msg = 'Authentication failure of type "user" occurred'
            if not auth_ret:  # auth_ret can be a boolean or the effective user id
                if show_username:
                    msg = "{} for user {}.".format(msg, username)
                ret["error"] = {"name": "UserAuthenticationError", "message": msg}
                return ret

            # Verify that the caller has root on master
            if auth_ret is not True:
                if AuthUser(load["user"]).is_sudo():
                    if not self.opts["sudo_acl"] or not self.opts["publisher_acl"]:
                        auth_ret = True

            if auth_ret is not True:
                # Avoid a circular import
                import salt.utils.master

                auth_list = salt.utils.master.get_values_of_matching_keys(
                    self.opts["publisher_acl"], auth_ret
                )
                if not auth_list:
                    ret["error"] = {"name": "UserAuthenticationError", "message": msg}
                    return ret
        else:
            ret["error"] = {
                "name": "SaltInvocationError",
                "message": "Authentication type not supported.",
            }
            return ret

        # Authentication checks passed
        ret["auth_list"] = auth_list
        return ret


class Resolver:
    """
    The class used to resolve options for the command line and for generic
    interactive interfaces
    """

    def __init__(self, opts):
        self.opts = opts
        self.auth = salt.loader.auth(opts)

    def _send_token_request(self, load):
        master_uri = "tcp://{}:{}".format(
            salt.utils.zeromq.ip_bracket(self.opts["interface"]),
            str(self.opts["ret_port"]),
        )
        with salt.transport.client.ReqChannel.factory(
            self.opts, crypt="clear", master_uri=master_uri
        ) as channel:
            return channel.send(load)

    def cli(self, eauth):
        """
        Execute the CLI options to fill in the extra data needed for the
        defined eauth system
        """
        ret = {}
        if not eauth:
            print("External authentication system has not been specified")
            return ret
        fstr = "{}.auth".format(eauth)
        if fstr not in self.auth:
            print(
                'The specified external authentication system "{}" is not available'.format(
                    eauth
                )
            )
            print(
                "Available eauth types: {}".format(
                    ", ".join(
                        sorted([k[:-5] for k in self.auth if k.endswith(".auth")])
                    )
                )
            )
            return ret

        args = salt.utils.args.arg_lookup(self.auth[fstr])
        for arg in args["args"]:
            if arg in self.opts:
                ret[arg] = self.opts[arg]
            elif arg.startswith("pass"):
                ret[arg] = getpass.getpass("{}: ".format(arg))
            else:
                ret[arg] = input("{}: ".format(arg))
        for kwarg, default in list(args["kwargs"].items()):
            if kwarg in self.opts:
                ret["kwarg"] = self.opts[kwarg]
            else:
                ret[kwarg] = input("{} [{}]: ".format(kwarg, default))

        # Use current user if empty
        if "username" in ret and not ret["username"]:
            ret["username"] = salt.utils.user.get_user()

        return ret

    def token_cli(self, eauth, load):
        """
        Create the token from the CLI and request the correct data to
        authenticate via the passed authentication mechanism
        """
        load["cmd"] = "mk_token"
        load["eauth"] = eauth
        tdata = self._send_token_request(load)
        if "token" not in tdata:
            return tdata
        try:
            with salt.utils.files.set_umask(0o177):
                with salt.utils.files.fopen(self.opts["token_file"], "w+") as fp_:
                    fp_.write(tdata["token"])
        except OSError:
            pass
        return tdata

    def mk_token(self, load):
        """
        Request a token from the master
        """
        load["cmd"] = "mk_token"
        tdata = self._send_token_request(load)
        return tdata

    def get_token(self, token):
        """
        Request a token from the master
        """
        load = {}
        load["token"] = token
        load["cmd"] = "get_token"
        tdata = self._send_token_request(load)
        return tdata


class AuthUser:
    """
    Represents a user requesting authentication to the salt master
    """

    def __init__(self, user):
        """
        Instantiate an AuthUser object.

        Takes a user to reprsent, as a string.
        """
        self.user = user

    def is_sudo(self):
        """
        Determines if the user is running with sudo

        Returns True if the user is running with sudo and False if the
        user is not running with sudo
        """
        return self.user.startswith("sudo_")

    def is_running_user(self):
        """
        Determines if the user is the same user as the one running
        this process

        Returns True if the user is the same user as the one running
        this process and False if not.
        """
        return self.user == salt.utils.user.get_user()

    def sudo_name(self):
        """
        Returns the username of the sudoer, i.e. self.user without the
        'sudo_' prefix.
        """
        return self.user.split("_", 1)[-1]

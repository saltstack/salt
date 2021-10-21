import binascii
import ctypes
import hashlib
import logging
import multiprocessing
import os
import shutil

import salt.crypt
import salt.ext.tornado.gen
import salt.master
import salt.payload
import salt.transport.frame
import salt.utils.event
import salt.utils.files
import salt.utils.minions
import salt.utils.stringutils
import salt.utils.verify
from salt.utils.cache import CacheCli

try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        from Crypto.Cipher import PKCS1_OAEP  # nosec


log = logging.getLogger(__name__)


# TODO: rename
class AESPubClientMixin:
    def _verify_master_signature(self, payload):
        if self.opts.get("sign_pub_messages"):
            if not payload.get("sig", False):
                raise salt.crypt.AuthenticationError(
                    "Message signing is enabled but the payload has no signature."
                )

            # Verify that the signature is valid
            master_pubkey_path = os.path.join(self.opts["pki_dir"], "minion_master.pub")
            if not salt.crypt.verify_signature(
                master_pubkey_path, payload["load"], payload.get("sig")
            ):
                raise salt.crypt.AuthenticationError(
                    "Message signature failed to validate."
                )

    @salt.ext.tornado.gen.coroutine
    def _decode_payload(self, payload):
        # we need to decrypt it
        log.trace("Decoding payload: %s", payload)
        if payload["enc"] == "aes":
            self._verify_master_signature(payload)
            try:
                payload["load"] = self.auth.crypticle.loads(payload["load"])
            except salt.crypt.AuthenticationError:
                yield self.auth.authenticate()
                payload["load"] = self.auth.crypticle.loads(payload["load"])

        raise salt.ext.tornado.gen.Return(payload)


# TODO: rename?
class AESReqServerMixin:
    """
    Mixin to house all of the master-side auth crypto
    """

    def pre_fork(self, _):
        """
        Pre-fork we need to create the zmq router device
        """
        if "aes" not in salt.master.SMaster.secrets:
            # TODO: This is still needed only for the unit tests
            # 'tcp_test.py' and 'zeromq_test.py'. Fix that. In normal
            # cases, 'aes' is already set in the secrets.
            salt.master.SMaster.secrets["aes"] = {
                "secret": multiprocessing.Array(
                    ctypes.c_char,
                    salt.utils.stringutils.to_bytes(
                        salt.crypt.Crypticle.generate_key_string()
                    ),
                ),
                "reload": salt.crypt.Crypticle.generate_key_string,
            }

    def post_fork(self, _, __):
        self.crypticle = salt.crypt.Crypticle(
            self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
        )

        # other things needed for _auth
        # Create the event manager
        self.event = salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=False
        )
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)

        # only create a con_cache-client if the con_cache is active
        if self.opts["con_cache"]:
            self.cache_cli = CacheCli(self.opts)
        else:
            self.cache_cli = False
            # Make an minion checker object
            self.ckminions = salt.utils.minions.CkMinions(self.opts)

        self.master_key = salt.crypt.MasterKeys(self.opts)

    def _encrypt_private(self, ret, dictkey, target):
        """
        The server equivalent of ReqChannel.crypted_transfer_decode_dictentry
        """
        # encrypt with a specific AES key
        pubfn = os.path.join(self.opts["pki_dir"], "minions", target)
        key = salt.crypt.Crypticle.generate_key_string()
        pcrypt = salt.crypt.Crypticle(self.opts, key)
        try:
            pub = salt.crypt.get_rsa_pub_key(pubfn)
        except (ValueError, IndexError, TypeError):
            return self.crypticle.dumps({})
        except OSError:
            log.error("AES key not found")
            return {"error": "AES key not found"}

        pret = {}
        key = salt.utils.stringutils.to_bytes(key)
        if HAS_M2:
            pret["key"] = pub.public_encrypt(key, RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(pub)
            pret["key"] = cipher.encrypt(key)
        pret[dictkey] = pcrypt.dumps(ret if ret is not False else {})
        return pret

    def _update_aes(self):
        """
        Check to see if a fresh AES key is available and update the components
        of the worker
        """
        if (
            salt.master.SMaster.secrets["aes"]["secret"].value
            != self.crypticle.key_string
        ):
            self.crypticle = salt.crypt.Crypticle(
                self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
            )
            return True
        return False

    def _decode_payload(self, payload):
        # we need to decrypt it
        if payload["enc"] == "aes":
            try:
                payload["load"] = self.crypticle.loads(payload["load"])
            except salt.crypt.AuthenticationError:
                if not self._update_aes():
                    raise
                payload["load"] = self.crypticle.loads(payload["load"])
        return payload

    def _auth(self, load):
        """
        Authenticate the client, use the sent public key to encrypt the AES key
        which was generated at start up.

        This method fires an event over the master event manager. The event is
        tagged "auth" and returns a dict with information about the auth
        event

            - Verify that the key we are receiving matches the stored key
            - Store the key if it is not there
            - Make an RSA key with the pub key
            - Encrypt the AES key as an encrypted salt.payload
            - Package the return and return it
        """

        if not salt.utils.verify.valid_id(self.opts, load["id"]):
            log.info("Authentication request from invalid id %s", load["id"])
            return {"enc": "clear", "load": {"ret": False}}
        log.info("Authentication request from %s", load["id"])

        # 0 is default which should be 'unlimited'
        if self.opts["max_minions"] > 0:
            # use the ConCache if enabled, else use the minion utils
            if self.cache_cli:
                minions = self.cache_cli.get_cached()
            else:
                minions = self.ckminions.connected_ids()
                if len(minions) > 1000:
                    log.info(
                        "With large numbers of minions it is advised "
                        "to enable the ConCache with 'con_cache: True' "
                        "in the masters configuration file."
                    )

            if not len(minions) <= self.opts["max_minions"]:
                # we reject new minions, minions that are already
                # connected must be allowed for the mine, highstate, etc.
                if load["id"] not in minions:
                    log.info(
                        "Too many minions connected (max_minions=%s). "
                        "Rejecting connection from id %s",
                        self.opts["max_minions"],
                        load["id"],
                    )
                    eload = {
                        "result": False,
                        "act": "full",
                        "id": load["id"],
                        "pub": load["pub"],
                    }

                    if self.opts.get("auth_events") is True:
                        self.event.fire_event(
                            eload, salt.utils.event.tagify(prefix="auth")
                        )
                    return {"enc": "clear", "load": {"ret": "full"}}

        # Check if key is configured to be auto-rejected/signed
        auto_reject = self.auto_key.check_autoreject(load["id"])
        auto_sign = self.auto_key.check_autosign(
            load["id"], load.get("autosign_grains", None)
        )

        pubfn = os.path.join(self.opts["pki_dir"], "minions", load["id"])
        pubfn_pend = os.path.join(self.opts["pki_dir"], "minions_pre", load["id"])
        pubfn_rejected = os.path.join(
            self.opts["pki_dir"], "minions_rejected", load["id"]
        )
        pubfn_denied = os.path.join(self.opts["pki_dir"], "minions_denied", load["id"])
        if self.opts["open_mode"]:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn_rejected):
            # The key has been rejected, don't place it in pending
            log.info(
                "Public key rejected for %s. Key is present in rejection key dir.",
                load["id"],
            )
            eload = {"result": False, "id": load["id"], "pub": load["pub"]}
            if self.opts.get("auth_events") is True:
                self.event.fire_event(eload, salt.utils.event.tagify(prefix="auth"))
            return {"enc": "clear", "load": {"ret": False}}

        elif os.path.isfile(pubfn):
            # The key has been accepted, check it
            with salt.utils.files.fopen(pubfn, "r") as pubfn_handle:
                if pubfn_handle.read().strip() != load["pub"].strip():
                    log.error(
                        "Authentication attempt from %s failed, the public "
                        "keys did not match. This may be an attempt to compromise "
                        "the Salt cluster.",
                        load["id"],
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.files.fopen(pubfn_denied, "w+") as fp_:
                        fp_.write(load["pub"])
                    eload = {
                        "result": False,
                        "id": load["id"],
                        "act": "denied",
                        "pub": load["pub"],
                    }
                    if self.opts.get("auth_events") is True:
                        self.event.fire_event(
                            eload, salt.utils.event.tagify(prefix="auth")
                        )
                    return {"enc": "clear", "load": {"ret": False}}

        elif not os.path.isfile(pubfn_pend):
            # The key has not been accepted, this is a new minion
            if os.path.isdir(pubfn_pend):
                # The key path is a directory, error out
                log.info("New public key %s is a directory", load["id"])
                eload = {"result": False, "id": load["id"], "pub": load["pub"]}
                if self.opts.get("auth_events") is True:
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix="auth"))
                return {"enc": "clear", "load": {"ret": False}}

            if auto_reject:
                key_path = pubfn_rejected
                log.info(
                    "New public key for %s rejected via autoreject_file", load["id"]
                )
                key_act = "reject"
                key_result = False
            elif not auto_sign:
                key_path = pubfn_pend
                log.info("New public key for %s placed in pending", load["id"])
                key_act = "pend"
                key_result = True
            else:
                # The key is being automatically accepted, don't do anything
                # here and let the auto accept logic below handle it.
                key_path = None

            if key_path is not None:
                # Write the key to the appropriate location
                with salt.utils.files.fopen(key_path, "w+") as fp_:
                    fp_.write(load["pub"])
                ret = {"enc": "clear", "load": {"ret": key_result}}
                eload = {
                    "result": key_result,
                    "act": key_act,
                    "id": load["id"],
                    "pub": load["pub"],
                }
                if self.opts.get("auth_events") is True:
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix="auth"))
                return ret

        elif os.path.isfile(pubfn_pend):
            # This key is in the pending dir and is awaiting acceptance
            if auto_reject:
                # We don't care if the keys match, this minion is being
                # auto-rejected. Move the key file from the pending dir to the
                # rejected dir.
                try:
                    shutil.move(pubfn_pend, pubfn_rejected)
                except OSError:
                    pass
                log.info(
                    "Pending public key for %s rejected via autoreject_file",
                    load["id"],
                )
                ret = {"enc": "clear", "load": {"ret": False}}
                eload = {
                    "result": False,
                    "act": "reject",
                    "id": load["id"],
                    "pub": load["pub"],
                }
                if self.opts.get("auth_events") is True:
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix="auth"))
                return ret

            elif not auto_sign:
                # This key is in the pending dir and is not being auto-signed.
                # Check if the keys are the same and error out if this is the
                # case. Otherwise log the fact that the minion is still
                # pending.
                with salt.utils.files.fopen(pubfn_pend, "r") as pubfn_handle:
                    if pubfn_handle.read() != load["pub"]:
                        log.error(
                            "Authentication attempt from %s failed, the public "
                            "key in pending did not match. This may be an "
                            "attempt to compromise the Salt cluster.",
                            load["id"],
                        )
                        # put denied minion key into minions_denied
                        with salt.utils.files.fopen(pubfn_denied, "w+") as fp_:
                            fp_.write(load["pub"])
                        eload = {
                            "result": False,
                            "id": load["id"],
                            "act": "denied",
                            "pub": load["pub"],
                        }
                        if self.opts.get("auth_events") is True:
                            self.event.fire_event(
                                eload, salt.utils.event.tagify(prefix="auth")
                            )
                        return {"enc": "clear", "load": {"ret": False}}
                    else:
                        log.info(
                            "Authentication failed from host %s, the key is in "
                            "pending and needs to be accepted with salt-key "
                            "-a %s",
                            load["id"],
                            load["id"],
                        )
                        eload = {
                            "result": True,
                            "act": "pend",
                            "id": load["id"],
                            "pub": load["pub"],
                        }
                        if self.opts.get("auth_events") is True:
                            self.event.fire_event(
                                eload, salt.utils.event.tagify(prefix="auth")
                            )
                        return {"enc": "clear", "load": {"ret": True}}
            else:
                # This key is in pending and has been configured to be
                # auto-signed. Check to see if it is the same key, and if
                # so, pass on doing anything here, and let it get automatically
                # accepted below.
                with salt.utils.files.fopen(pubfn_pend, "r") as pubfn_handle:
                    if pubfn_handle.read() != load["pub"]:
                        log.error(
                            "Authentication attempt from %s failed, the public "
                            "keys in pending did not match. This may be an "
                            "attempt to compromise the Salt cluster.",
                            load["id"],
                        )
                        # put denied minion key into minions_denied
                        with salt.utils.files.fopen(pubfn_denied, "w+") as fp_:
                            fp_.write(load["pub"])
                        eload = {"result": False, "id": load["id"], "pub": load["pub"]}
                        if self.opts.get("auth_events") is True:
                            self.event.fire_event(
                                eload, salt.utils.event.tagify(prefix="auth")
                            )
                        return {"enc": "clear", "load": {"ret": False}}
                    else:
                        os.remove(pubfn_pend)

        else:
            # Something happened that I have not accounted for, FAIL!
            log.warning("Unaccounted for authentication failure")
            eload = {"result": False, "id": load["id"], "pub": load["pub"]}
            if self.opts.get("auth_events") is True:
                self.event.fire_event(eload, salt.utils.event.tagify(prefix="auth"))
            return {"enc": "clear", "load": {"ret": False}}

        log.info("Authentication accepted from %s", load["id"])
        # only write to disk if you are adding the file, and in open mode,
        # which implies we accept any key from a minion.
        if not os.path.isfile(pubfn) and not self.opts["open_mode"]:
            with salt.utils.files.fopen(pubfn, "w+") as fp_:
                fp_.write(load["pub"])
        elif self.opts["open_mode"]:
            disk_key = ""
            if os.path.isfile(pubfn):
                with salt.utils.files.fopen(pubfn, "r") as fp_:
                    disk_key = fp_.read()
            if load["pub"] and load["pub"] != disk_key:
                log.debug("Host key change detected in open mode.")
                with salt.utils.files.fopen(pubfn, "w+") as fp_:
                    fp_.write(load["pub"])
            elif not load["pub"]:
                log.error("Public key is empty: %s", load["id"])
                return {"enc": "clear", "load": {"ret": False}}

        pub = None

        # the con_cache is enabled, send the minion id to the cache
        if self.cache_cli:
            self.cache_cli.put_cache([load["id"]])

        # The key payload may sometimes be corrupt when using auto-accept
        # and an empty request comes in
        try:
            pub = salt.crypt.get_rsa_pub_key(pubfn)
        except salt.crypt.InvalidKeyError as err:
            log.error('Corrupt public key "%s": %s', pubfn, err)
            return {"enc": "clear", "load": {"ret": False}}

        if not HAS_M2:
            cipher = PKCS1_OAEP.new(pub)
        ret = {
            "enc": "pub",
            "pub_key": self.master_key.get_pub_str(),
            "publish_port": self.opts["publish_port"],
        }

        # sign the master's pubkey (if enabled) before it is
        # sent to the minion that was just authenticated
        if self.opts["master_sign_pubkey"]:
            # append the pre-computed signature to the auth-reply
            if self.master_key.pubkey_signature():
                log.debug("Adding pubkey signature to auth-reply")
                log.debug(self.master_key.pubkey_signature())
                ret.update({"pub_sig": self.master_key.pubkey_signature()})
            else:
                # the master has its own signing-keypair, compute the master.pub's
                # signature and append that to the auth-reply

                # get the key_pass for the signing key
                key_pass = salt.utils.sdb.sdb_get(
                    self.opts["signing_key_pass"], self.opts
                )

                log.debug("Signing master public key before sending")
                pub_sign = salt.crypt.sign_message(
                    self.master_key.get_sign_paths()[1], ret["pub_key"], key_pass
                )
                ret.update({"pub_sig": binascii.b2a_base64(pub_sign)})

        if not HAS_M2:
            mcipher = PKCS1_OAEP.new(self.master_key.key)
        if self.opts["auth_mode"] >= 2:
            if "token" in load:
                try:
                    if HAS_M2:
                        mtoken = self.master_key.key.private_decrypt(
                            load["token"], RSA.pkcs1_oaep_padding
                        )
                    else:
                        mtoken = mcipher.decrypt(load["token"])
                    aes = "{}_|-{}".format(
                        salt.master.SMaster.secrets["aes"]["secret"].value, mtoken
                    )
                except Exception:  # pylint: disable=broad-except
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass
            else:
                aes = salt.master.SMaster.secrets["aes"]["secret"].value

            if HAS_M2:
                ret["aes"] = pub.public_encrypt(aes, RSA.pkcs1_oaep_padding)
            else:
                ret["aes"] = cipher.encrypt(aes)
        else:
            if "token" in load:
                try:
                    if HAS_M2:
                        mtoken = self.master_key.key.private_decrypt(
                            load["token"], RSA.pkcs1_oaep_padding
                        )
                        ret["token"] = pub.public_encrypt(
                            mtoken, RSA.pkcs1_oaep_padding
                        )
                    else:
                        mtoken = mcipher.decrypt(load["token"])
                        ret["token"] = cipher.encrypt(mtoken)
                except Exception:  # pylint: disable=broad-except
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass

            aes = salt.master.SMaster.secrets["aes"]["secret"].value
            if HAS_M2:
                ret["aes"] = pub.public_encrypt(aes, RSA.pkcs1_oaep_padding)
            else:
                ret["aes"] = cipher.encrypt(aes)
        # Be aggressive about the signature
        digest = salt.utils.stringutils.to_bytes(hashlib.sha256(aes).hexdigest())
        ret["sig"] = salt.crypt.private_encrypt(self.master_key.key, digest)
        eload = {"result": True, "act": "accept", "id": load["id"], "pub": load["pub"]}
        if self.opts.get("auth_events") is True:
            self.event.fire_event(eload, salt.utils.event.tagify(prefix="auth"))
        return ret

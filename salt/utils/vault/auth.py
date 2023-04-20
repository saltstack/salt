import logging

import salt.utils.vault.leases as leases
from salt.utils.vault.exceptions import VaultAuthExpired

log = logging.getLogger(__name__)


class VaultTokenAuth:
    """
    Container for authentication tokens
    """

    def __init__(self, cache=None, token=None):
        self.cache = cache
        if token is None and cache is not None:
            token = cache.get()
        if token is None:
            token = InvalidVaultToken()
        if isinstance(token, dict):
            token = leases.VaultToken(**token)
        self.token = token

    def is_renewable(self):
        """
        Check whether the contained token is renewable, which requires it
        to be currently valid for at least two uses and renewable
        """
        return self.token.is_renewable()

    def is_valid(self, valid_for=0):
        """
        Check whether the contained token is valid
        """
        return self.token.is_valid(valid_for)

    def get_token(self):
        """
        Get the contained token if it is valid, otherwise
        raises VaultAuthExpired
        """
        if self.token.is_valid():
            return self.token
        raise VaultAuthExpired()

    def used(self):
        """
        Increment the use counter for the contained token
        """
        self.token.used()
        if self.token.num_uses != 0:
            self._write_cache()

    def update_token(self, auth):
        """
        Partially update the contained token (e.g. after renewal)
        """
        self.token = self.token.with_renewed(**auth)
        self._write_cache()

    def replace_token(self, token):
        """
        Completely replace the contained token with a new one
        """
        self.token = token
        self._write_cache()

    def _write_cache(self):
        if self.cache is not None:
            # Write the token indiscriminately since flushing
            # raises VaultAuthExpired.
            # This will be handled as part of the next request.
            self.cache.store(self.token)


class VaultAppRoleAuth:
    """
    Issues tokens from AppRole credentials.
    """

    def __init__(self, approle, client, mount="approle", cache=None, token_store=None):
        self.approle = approle
        self.client = client
        self.mount = mount
        self.cache = cache
        if token_store is None:
            token_store = VaultTokenAuth()
        self.token = token_store

    def is_renewable(self):
        """
        Check whether the currently used token is renewable.
        Secret IDs are not renewable anyways.
        """
        return self.token.is_renewable()

    def is_valid(self, valid_for=0):
        """
        Check whether the contained authentication data can be used
        to issue a valid token
        """
        return self.token.is_valid(valid_for) or self.approle.is_valid(valid_for)

    def get_token(self):
        """
        Return the token issued by the last login, if it is still valid, otherwise
        login with the contained AppRole, if it is valid. Otherwise,
        raises VaultAuthExpired
        """
        if self.token.is_valid():
            return self.token.get_token()
        if self.approle.is_valid():
            return self._login()
        raise VaultAuthExpired()

    def used(self):
        """
        Increment the use counter for the currently used token
        """
        self.token.used()

    def update_token(self, auth):
        """
        Partially update the contained token (e.g. after renewal)
        """
        self.token.update_token(auth)

    def _login(self):
        log.debug("Vault token expired. Recreating one by authenticating with AppRole.")
        endpoint = f"auth/{self.mount}/login"
        payload = self.approle.payload()
        res = self.client.post(endpoint, payload=payload)
        self.approle.used()
        self._replace_token(res["auth"])
        self._write_cache()
        return self.token.get_token()

    def _write_cache(self):
        if self.cache is not None and self.approle.secret_id is not None:
            if isinstance(self.approle.secret_id, LocalVaultSecretId):
                pass
            elif self.approle.secret_id.num_uses == 0:
                pass
            elif self.approle.secret_id.is_valid():
                self.cache.store(self.approle.secret_id)
            else:
                self.cache.flush()

    def _replace_token(self, auth):
        self.token.replace_token(leases.VaultToken(**auth))


class VaultAppRole:
    """
    Container that represents an AppRole
    """

    def __init__(self, role_id, secret_id=None):
        self.role_id = role_id
        self.secret_id = secret_id

    def replace_secret_id(self, secret_id):
        """
        Replace the contained secret ID with a new one
        """
        self.secret_id = secret_id

    def is_valid(self, valid_for=0, uses=1):
        """
        Checks whether the contained data can be used to authenticate
        to Vault. Secret IDs might not be required by the server when
        bind_secret_id is set to false.

        valid_for
            Allows to check whether the AppRole will still be valid in the future.
            This can be an integer, which will be interpreted as seconds, or a
            time string using the same format as Vault does:
            Suffix ``s`` for seconds, ``m`` for minutes, ``h`` for hours, ``d`` for days.
            Defaults to 0.

        uses
            Check whether the AppRole has at least this number of uses left. Defaults to 1.
        """
        if self.secret_id is None:
            return True
        return self.secret_id.is_valid(valid_for=valid_for, uses=uses)

    def used(self):
        """
        Increment the secret ID use counter by one, if this AppRole uses one.
        """
        if self.secret_id is not None:
            self.secret_id.used()

    def payload(self):
        """
        Return the payload to use for POST requests using this AppRole
        """
        payload = {}
        if self.secret_id is not None:
            payload = self.secret_id.payload()
        payload["role_id"] = self.role_id
        return payload


class LocalVaultSecretId(leases.VaultSecretId):
    """
    Represents a secret ID from local configuration and should not be cached.
    """

    def is_valid(self, valid_for=0, uses=1):
        """
        Local secret IDs are always assumed to be valid until proven otherwise
        """
        return True


class InvalidVaultToken(leases.VaultToken):
    """
    Represents a missing token
    """

    def __init__(self, *args, **kwargs):  # pylint: disable=super-init-not-called
        self.renewable = False
        self.use_count = 0
        self.num_uses = 0

    def is_valid(self, valid_for=0, uses=1):
        return False


class InvalidVaultSecretId(leases.VaultSecretId):
    """
    Represents a missing secret ID
    """

    def __init__(self, *args, **kwargs):  # pylint: disable=super-init-not-called
        pass

    def is_valid(self, valid_for=0, uses=1):
        return False

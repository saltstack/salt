import logging
import re

import requests
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

import salt.exceptions
import salt.utils.vault.leases as leases
from salt.utils.vault.exceptions import (
    VaultAuthExpired,
    VaultInvocationError,
    VaultNotFoundError,
    VaultPermissionDeniedError,
    VaultPreconditionFailedError,
    VaultServerError,
    VaultUnavailableError,
    VaultUnsupportedOperationError,
    VaultUnwrapException,
)

log = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)

# This list is not complete at all, but contains
# the most important paths.
VAULT_UNAUTHD_PATHS = (
    "sys/wrapping/lookup",
    "sys/internal/ui/mounts",
    "sys/internal/ui/namespaces",
    "sys/seal-status",
    "sys/health",
)


def _get_expected_creation_path(secret_type, config=None):
    if secret_type == "token":
        return r"auth/token/create(/[^/]+)?"

    if secret_type == "secret_id":
        if config is not None:
            return r"auth/{}/role/{}/secret\-id".format(
                re.escape(config["auth"]["approle_mount"]),
                re.escape(config["auth"]["approle_name"]),
            )
        return r"auth/[^/]+/role/[^/]+/secret\-id"

    if secret_type == "role_id":
        if config is not None:
            return r"auth/{}/role/{}/role\-id".format(
                re.escape(config["auth"]["approle_mount"]),
                re.escape(config["auth"]["approle_name"]),
            )
        return r"auth/[^/]+/role/[^/]+/role\-id"

    raise salt.exceptions.SaltInvocationError(
        f"secret_type must be one of token, secret_id, role_id, got `{secret_type}`."
    )


class VaultClient:
    """
    Unauthenticated client for the Vault API.
    Base class for authenticated client.
    """

    def __init__(self, url, namespace=None, verify=None, session=None):
        self.url = url
        self.namespace = namespace
        self.verify = verify

        ca_cert = None
        try:
            if verify.startswith("-----BEGIN CERTIFICATE"):
                ca_cert = verify
                verify = None
        except AttributeError:
            pass

        # Keep the actual requests parameter separate from the client config
        # to reduce complexity in config validation.
        self._requests_verify = verify
        if session is None:
            session = requests.Session()
            if ca_cert:
                adapter = CACertHTTPSAdapter(ca_cert)
                session.mount(url, adapter)
        self.session = session

    def delete(self, endpoint, wrap=False, raise_error=True, add_headers=None):
        """
        Wrapper for client.request("DELETE", ...)
        """
        return self.request(
            "DELETE",
            endpoint,
            wrap=wrap,
            raise_error=raise_error,
            add_headers=add_headers,
        )

    def get(self, endpoint, wrap=False, raise_error=True, add_headers=None):
        """
        Wrapper for client.request("GET", ...)
        """
        return self.request(
            "GET", endpoint, wrap=wrap, raise_error=raise_error, add_headers=add_headers
        )

    def list(self, endpoint, wrap=False, raise_error=True, add_headers=None):
        """
        Wrapper for client.request("LIST", ...)
        TODO: configuration to enable GET requests with query parameters for LIST?
        """
        return self.request(
            "LIST",
            endpoint,
            wrap=wrap,
            raise_error=raise_error,
            add_headers=add_headers,
        )

    def post(
        self, endpoint, payload=None, wrap=False, raise_error=True, add_headers=None
    ):
        """
        Wrapper for client.request("POST", ...)
        Vault considers POST and PUT to be synonymous.
        """
        return self.request(
            "POST",
            endpoint,
            payload=payload,
            wrap=wrap,
            raise_error=raise_error,
            add_headers=add_headers,
        )

    def patch(self, endpoint, payload, wrap=False, raise_error=True, add_headers=None):
        """
        Wrapper for client.request("PATCH", ...)
        """
        return self.request(
            "PATCH",
            endpoint,
            payload=payload,
            wrap=wrap,
            raise_error=raise_error,
            add_headers=add_headers,
        )

    def request(
        self,
        method,
        endpoint,
        payload=None,
        wrap=False,
        raise_error=True,
        add_headers=None,
        **kwargs,
    ):
        """
        Issue a request against the Vault API.
        Returns boolean when no data was returned, otherwise the decoded json data
        or a VaultWrappedResponse object if wrapping was requested.
        """
        res = self.request_raw(
            method,
            endpoint,
            payload=payload,
            wrap=wrap,
            add_headers=add_headers,
            **kwargs,
        )
        if res.status_code == 204:
            return True
        data = res.json()
        if not res.ok:
            if raise_error:
                self._raise_status(res)
            return data
        if wrap:
            return leases.VaultWrappedResponse(**data["wrap_info"])
        return data

    def request_raw(
        self, method, endpoint, payload=None, wrap=False, add_headers=None, **kwargs
    ):
        """
        Issue a request against the Vault API. Returns the raw response object.
        """
        url = self._get_url(endpoint)
        headers = self._get_headers(wrap)
        try:
            headers.update(add_headers)
        except TypeError:
            pass
        res = self.session.request(
            method,
            url,
            headers=headers,
            json=payload,
            verify=self._requests_verify,
            **kwargs,
        )
        return res

    def unwrap(self, wrapped, expected_creation_path=None):
        """
        Unwraps the data associated with a wrapping token.

        wrapped
            Wrapping token to unwrap

        expected_creation_path
            Regex expression or list of expressions that should fully match the
            wrapping token creation path. At least one match is required.
            Defaults to None, which skips the check.

            .. note::
                This check prevents tampering with wrapping tokens, which are
                valid for one request only. Usually, if an attacker sniffs a wrapping
                token, there will be two unwrapping requests, causing an audit warning.
                If the attacker can issue a new wrapping token and insert it into the
                response instead, this warning would be silenced. Assuming they do not
                possess the permissions to issue a wrapping token from the correct
                endpoint, checking the creation path makes this kind of attack obvious.
        """
        if expected_creation_path:
            wrap_info = self.wrap_info(wrapped)
            if not isinstance(expected_creation_path, list):
                expected_creation_path = [expected_creation_path]
            if not any(
                re.fullmatch(p, wrap_info["creation_path"])
                for p in expected_creation_path
            ):
                raise VaultUnwrapException(
                    actual=wrap_info["creation_path"],
                    expected=expected_creation_path,
                    url=self.url,
                    namespace=self.namespace,
                    verify=self.verify,
                )
        endpoint = "sys/wrapping/unwrap"
        headers = self._get_headers()
        payload = {}
        if "X-Vault-Token" not in headers:
            headers["X-Vault-Token"] = str(wrapped)
        else:
            payload["token"] = str(wrapped)
        return self.post(endpoint=endpoint, add_headers=headers, payload=payload)

    def wrap_info(self, wrapped):
        """
        Lookup wrapping token meta information.
        """
        endpoint = "sys/wrapping/lookup"
        add_headers = {"X-Vault-Token": str(wrapped)}
        return self.post(endpoint, wrap=False, add_headers=add_headers)["data"]

    def token_lookup(self, token=None, accessor=None, raw=False):
        """
        Lookup token meta information.

        token
            The token to look up or to use to look up the accessor.
            Required.

        accessor
            The accessor to use to query the token meta information.

        raw
            Return the raw response object instead of response data.
            Also disables status code checking.
        """
        endpoint = "auth/token/lookup-self"
        method = "GET"
        payload = {}
        if token is None:
            raise VaultInvocationError(
                "Unauthenticated VaultClient needs a token to lookup."
            )
        add_headers = {"X-Vault-Token": token}

        if accessor is not None:
            endpoint = "auth/token/lookup-accessor"
            payload["accessor"] = accessor

        res = self.request_raw(
            method, endpoint, payload=payload, wrap=False, add_headers=add_headers
        )
        if raw:
            return res
        self._raise_status(res)
        return res.json()["data"]

    def token_valid(self, valid_for=0, remote=True):  # pylint: disable=unused-argument
        return False

    def get_config(self):
        """
        Returns Vault server configuration used by this client.
        """
        return {
            "url": self.url,
            "namespace": self.namespace,
            "verify": self.verify,
        }

    def _get_url(self, endpoint):
        endpoint = endpoint.strip("/")
        return f"{self.url}/v1/{endpoint}"

    def _get_headers(self, wrap=False):
        headers = {"Content-Type": "application/json", "X-Vault-Request": "true"}
        if self.namespace is not None:
            headers["X-Vault-Namespace"] = self.namespace
        if wrap:
            headers["X-Vault-Wrap-TTL"] = str(wrap)
        return headers

    def _raise_status(self, res):
        errors = ", ".join(res.json().get("errors", []))
        if res.status_code == 400:
            raise VaultInvocationError(errors)
        if res.status_code == 403:
            raise VaultPermissionDeniedError(errors)
        if res.status_code == 404:
            raise VaultNotFoundError(errors)
        if res.status_code == 405:
            raise VaultUnsupportedOperationError(errors)
        if res.status_code == 412:
            raise VaultPreconditionFailedError(errors)
        if res.status_code in [500, 502]:
            raise VaultServerError(errors)
        if res.status_code == 503:
            raise VaultUnavailableError(errors)
        res.raise_for_status()


class AuthenticatedVaultClient(VaultClient):
    """
    Authenticated client for the Vault API.
    This should be used for most operations.
    """

    auth = None

    def __init__(self, auth, url, **kwargs):
        self.auth = auth
        super().__init__(url, **kwargs)

    def token_valid(self, valid_for=0, remote=True):
        """
        Check whether this client's authentication information is
        still valid.

        remote
            Check with the remote Vault server as well. This consumes
            a token use. Defaults to true.
        """
        if not self.auth.is_valid(valid_for):
            return False
        if not remote:
            return True
        try:
            res = self.token_lookup(raw=True)
            if res.status_code != 200:
                return False
            return True
        except Exception as err:  # pylint: disable=broad-except
            raise salt.exceptions.CommandExecutionError(
                "Error while looking up self token."
            ) from err

    def token_lookup(self, token=None, accessor=None, raw=False):
        """
        Lookup token meta information.

        token
            The token to look up. If neither token nor accessor
            are specified, looks up the current token in use by
            this client.

        accessor
            The accessor of the token to query the meta information for.

        raw
            Return the raw response object instead of response data.
            Also disables status code checking.
        """
        endpoint = "auth/token/lookup"
        method = "POST"
        payload = {}
        if token is None and accessor is None:
            endpoint += "-self"
            method = "GET"
        if token is not None:
            payload["token"] = token
        elif accessor is not None:
            endpoint += "-accessor"
            payload["accessor"] = accessor
        if raw:
            return self.request_raw(method, endpoint, payload=payload, wrap=False)
        return self.request(method, endpoint, payload=payload, wrap=False)["data"]

    def token_renew(self, increment=None, token=None, accessor=None):
        """
        Renew a token.

        increment
            Request the token to be valid for this amount of time from the current
            point of time onwards. Can also be used to reduce the validity period.
            The server might not honor this increment.
            Can be an integer (seconds) or a time string like ``1h``. Optional.

        token
            The token that should be renewed. Optional.
            If token and accessor are unset, renews the token currently in use
            by this client.

        accessor
            The accessor of the token that should be renewed. Optional.
        """
        endpoint = "auth/token/renew"
        payload = {}

        if token is None and accessor is None:
            if not self.auth.is_renewable():
                return False
            endpoint += "-self"

        if increment is not None:
            payload["increment"] = increment
        if token is not None:
            payload["token"] = token
        elif accessor is not None:
            endpoint += "-accessor"
            payload["accessor"] = accessor

        res = self.post(endpoint, payload=payload)

        if token is None and accessor is None:
            self.auth.update_token(res["auth"])
        return res["auth"]

    def token_revoke(self, delta=1, token=None, accessor=None):
        """
        Revoke a token by setting its TTL to 1s.

        delta
            The time in seconds to request revocation after.
            Defaults to 1s.

        token
            The token that should be revoked. Optional.
            If token and accessor are unset, revokes the token currently in use
            by this client.

        accessor
            The accessor of the token that should be revoked. Optional.
        """
        try:
            self.token_renew(increment=delta, token=token, accessor=accessor)
        except (VaultPermissionDeniedError, VaultNotFoundError, VaultAuthExpired):
            # if we're trying to revoke ourselves and this happens,
            # the token was already invalid
            if token or accessor:
                raise
            return False
        return True

    def request_raw(
        self,
        method,
        endpoint,
        payload=None,
        wrap=False,
        add_headers=None,
        is_unauthd=False,
        **kwargs,
    ):  # pylint: disable=arguments-differ
        """
        Issue an authenticated request against the Vault API. Returns the raw response object.
        """
        ret = super().request_raw(
            method,
            endpoint,
            payload=payload,
            wrap=wrap,
            add_headers=add_headers,
            **kwargs,
        )
        # tokens are used regardless of status code
        if not is_unauthd and not endpoint.startswith(VAULT_UNAUTHD_PATHS):
            self.auth.used()
        return ret

    def _get_headers(self, wrap=False):
        headers = super()._get_headers(wrap)
        headers["X-Vault-Token"] = str(self.auth.get_token())
        return headers


class CACertHTTPSAdapter(requests.sessions.HTTPAdapter):
    """
    Allows to restrict requests CA chain validation
    to a single root certificate without writing it to disk.
    """

    def __init__(self, ca_cert_data, *args, **kwargs):
        self.ca_cert_data = ca_cert_data
        super().__init__(*args, **kwargs)

    def init_poolmanager(
        self,
        connections,
        maxsize,
        block=requests.adapters.DEFAULT_POOLBLOCK,
        **pool_kwargs,
    ):
        ssl_context = create_urllib3_context()
        ssl_context.load_verify_locations(cadata=self.ca_cert_data)
        pool_kwargs["ssl_context"] = ssl_context
        return super().init_poolmanager(
            connections, maxsize, block=block, **pool_kwargs
        )

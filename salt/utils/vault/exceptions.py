import salt.exceptions


class VaultException(salt.exceptions.SaltException):
    """
    Base class for exceptions raised by this module
    """


class VaultLeaseExpired(VaultException):
    """
    Raised when a cached lease is reported to be expired locally.
    """


class VaultAuthExpired(VaultException):
    """
    Raised when cached authentication data is reported to be outdated locally.
    """


class VaultConfigExpired(VaultException):
    """
    Raised when secret authentication data queried from the master reports
    a different server configuration than locally cached or an explicit
    cache TTL set in the configuration has been reached.
    """


class VaultUnwrapException(VaultException):
    """
    Raised when an expected creation path for a wrapping token differs
    from the reported one.
    This has to be taken seriously as it indicates tampering.
    """

    def __init__(self, expected, actual, url, namespace, verify, *args, **kwargs):
        msg = (
            "Wrapped response was not created from expected Vault path: "
            f"`{actual}` is not matched by any of `{expected}`.\n"
            "This indicates tampering with the wrapping token by a third party "
            "and should be taken very seriously! If you changed some authentication-"
            "specific configuration on the master recently, especially minion "
            "approle mount, you should consider if this error was caused by outdated "
            "cached data on this minion instead."
        )
        super().__init__(msg, *args, **kwargs)
        self.event_data = {
            "expected": expected,
            "actual": actual,
            "url": url,
            "namespace": namespace,
            "verify": verify,
        }


# https://www.vaultproject.io/api-docs#http-status-codes
class VaultInvocationError(VaultException):
    """
    HTTP 400 and InvalidArgumentException for this module
    """


class VaultPermissionDeniedError(VaultException):
    """
    HTTP 403
    """


class VaultNotFoundError(VaultException):
    """
    HTTP 404
    In some cases, this is also raised when the client does not have
    the correct permissions for the requested endpoint.
    """


class VaultUnsupportedOperationError(VaultException):
    """
    HTTP 405
    """


class VaultPreconditionFailedError(VaultException):
    """
    HTTP 412
    """


class VaultServerError(VaultException):
    """
    HTTP 500
    HTTP 502
    """


class VaultUnavailableError(VaultException):
    """
    HTTP 503
    Indicates maintenance or sealed status.
    """

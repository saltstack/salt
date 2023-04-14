import salt.exceptions


class VaultException(salt.exceptions.SaltException):
    """
    Base class for exceptions raised by this module
    """


class VaultAuthExpired(VaultException):
    """
    Raised when authentication data is reported to be outdated locally.
    """


class VaultConfigExpired(VaultException):
    """
    Raised when secret authentication data queried from the master reports
    a different server configuration than locally cached.
    """


class VaultUnwrapException(VaultException):
    """
    Raised when an expected creation path for a wrapping token differs
    from the reported one.
    This has to be taken seriously as it indicates tampering.
    """


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

"""
Authentication runner for creating, deleting, and managing eauth tokens.

.. versionadded:: 2016.11.0

"""

import os

import salt.auth
import salt.exceptions
import salt.netapi


def mk_token(**load):
    r"""
    Create an eauth token using provided credentials

    Non-root users may specify an expiration date -- if allowed via the
    :conf_master:`token_expire_user_override` setting -- by passing an
    additional ``token_expire`` param. This overrides the
    :conf_master:`token_expire` setting of the same name in the Master config
    and is how long a token should live in seconds.

    CLI Example:

    .. code-block:: shell

        salt-run auth.mk_token username=saltdev password=saltdev eauth=auto

        # Create a token valid for three years.
        salt-run auth.mk_token username=saltdev password=saltdev eauth=auto \
            token_expire=94670856

        # Calculate the number of seconds using expr.
        salt-run auth.mk_token username=saltdev password=saltdev eauth=auto \
            token_expire=$(expr \( 365 \* 24 \* 60 \* 60 \) \* 3)
    """
    # This will hang if the master daemon is not running.
    netapi = salt.netapi.NetapiClient(__opts__)
    if not netapi._is_master_running():
        raise salt.exceptions.SaltDaemonNotRunning("Salt Master must be running.")

    auth = salt.auth.Resolver(__opts__)
    return auth.mk_token(load)


def del_token(token):
    """
    Delete an eauth token by name

    CLI Example:

    .. code-block:: shell

        salt-run auth.del_token 6556760736e4077daa601baec2b67c24
    """
    token_path = os.path.join(__opts__["token_dir"], token)
    if os.path.exists(token_path):
        return os.remove(token_path) is None
    return False

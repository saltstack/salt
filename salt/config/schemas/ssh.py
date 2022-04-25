"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.config.schemas.ssh
    ~~~~~~~~~~~~~~~~~~~~~~~

    Salt SSH related configuration schemas
"""


from salt.config.schemas.minion import MinionConfiguration
from salt.utils.schema import (
    AnyOfItem,
    BooleanItem,
    DictItem,
    IntegerItem,
    PortItem,
    RequirementsItem,
    Schema,
    SecretItem,
    StringItem,
)


class RosterEntryConfig(Schema):
    """
    Schema definition of a Salt SSH Roster entry
    """

    title = "Roster Entry"
    description = "Salt SSH roster entry definition"

    host = StringItem(
        title="Host",
        description="The IP address or DNS name of the remote host",
        # Pretty naive pattern matching
        pattern=r"^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|([A-Za-z0-9][A-Za-z0-9\.\-]{1,255}))$",
        min_length=1,
        required=True,
    )
    port = PortItem(
        title="Port", description="The target system's ssh port number", default=22
    )
    user = StringItem(
        title="User",
        description="The user to log in as. Defaults to root",
        default="root",
        min_length=1,
        required=True,
    )
    passwd = SecretItem(
        title="Password", description="The password to log in with", min_length=1
    )
    priv = StringItem(
        title="Private Key",
        description="File path to ssh private key, defaults to salt-ssh.rsa",
        min_length=1,
    )
    priv_passwd = SecretItem(
        title="Private Key passphrase",
        description="Passphrase for private key file",
        min_length=1,
    )
    passwd_or_priv_requirement = AnyOfItem(
        items=(
            RequirementsItem(requirements=["passwd"]),
            RequirementsItem(requirements=["priv"]),
        )
    )(flatten=True)
    sudo = BooleanItem(
        title="Sudo",
        description="run command via sudo. Defaults to False",
        default=False,
    )
    timeout = IntegerItem(
        title="Timeout",
        description=(
            "Number of seconds to wait for response when establishing an SSH connection"
        ),
    )
    thin_dir = StringItem(
        title="Thin Directory",
        description=(
            "The target system's storage directory for Salt "
            "components. Defaults to /tmp/salt-<hash>."
        ),
    )
    minion_opts = DictItem(
        title="Minion Options",
        description="Dictionary of minion options",
        properties=MinionConfiguration(),
    )


class RosterItem(Schema):
    title = "Roster Configuration"
    description = "Roster entries definition"

    roster_entries = DictItem(pattern_properties={r"^([^:]+)$": RosterEntryConfig()})(
        flatten=True
    )

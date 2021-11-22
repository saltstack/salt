"""
Support IPMI commands over LAN. This module does not talk to the local
systems hardware through IPMI drivers. It uses a python module `pyghmi`.

:depends: Python module pyghmi.
    You can install pyghmi using pip:

    .. code-block:: bash

        pip install pyghmi

:configuration: The following configuration defaults can be
    define (pillar or config files):

    .. code-block:: python

        ipmi.config:
            api_host: 127.0.0.1
            api_user: admin
            api_pass: apassword
            api_port: 623
            api_kg: None

    Usage can override the config defaults:

    .. code-block:: bash

            salt-call ipmi.get_user api_host=myipmienabled.system
                                    api_user=admin api_pass=pass
                                    uid=1
"""


IMPORT_ERR = None
try:
    from pyghmi.ipmi import command
    from pyghmi.ipmi.private import session
except Exception as ex:  # pylint: disable=broad-except
    IMPORT_ERR = str(ex)

__virtualname__ = "ipmi"


def __virtual__():
    return (IMPORT_ERR is None, IMPORT_ERR)


def _get_config(**kwargs):
    """
    Return configuration
    """
    config = {
        "api_host": "localhost",
        "api_port": 623,
        "api_user": "admin",
        "api_pass": "",
        "api_kg": None,
        "api_login_timeout": 2,
    }
    if "__salt__" in globals():
        config_key = "{}.config".format(__virtualname__)
        config.update(__salt__["config.get"](config_key, {}))
    for k in set(config) & set(kwargs):
        config[k] = kwargs[k]
    return config


class _IpmiCommand:
    o = None

    def __init__(self, **kwargs):
        config = _get_config(**kwargs)
        self.o = command.Command(
            bmc=config["api_host"],
            userid=config["api_user"],
            password=config["api_pass"],
            port=config["api_port"],
            kg=config["api_kg"],
        )

    def __enter__(self):
        return self.o

    def __exit__(self, type, value, traceback):
        if self.o:
            self.o.ipmi_session.logout()


class _IpmiSession:
    o = None

    def _onlogon(self, response):
        if "error" in response:
            raise Exception(response["error"])

    def __init__(self, **kwargs):
        config = _get_config(**kwargs)
        self.o = session.Session(
            bmc=config["api_host"],
            userid=config["api_user"],
            password=config["api_pass"],
            port=config["api_port"],
            kg=config["api_kg"],
            onlogon=self._onlogon,
        )
        while not self.o.logged:
            # override timeout
            self.o.maxtimeout = config["api_login_timeout"]
            self.o.wait_for_rsp(timeout=1)
        self.o.maxtimeout = 5

    def __enter__(self):
        return self.o

    def __exit__(self, type, value, traceback):
        if self.o:
            self.o.logout()


def raw_command(
    netfn, command, bridge_request=None, data=(), retry=True, delay_xmit=None, **kwargs
):
    """
    Send raw ipmi command

    This allows arbitrary IPMI bytes to be issued.  This is commonly used
    for certain vendor specific commands.

    :param netfn: Net function number
    :param command: Command value
    :param bridge_request: The target slave address and channel number for
                        the bridge request.
    :param data: Command data as a tuple or list
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    :returns: dict -- The response from IPMI device

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.raw_command netfn=0x06 command=0x46 data=[0x02]
        # this will return the name of the user with id 2 in bytes
    """
    with _IpmiSession(**kwargs) as s:
        r = s.raw_command(
            netfn=int(netfn),
            command=int(command),
            bridge_request=bridge_request,
            data=data,
            retry=retry,
            delay_xmit=delay_xmit,
        )
        return r


def fast_connect_test(**kwargs):
    """
    Returns True if connection success.
    This uses an aggressive timeout value!

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.fast_connect_test api_host=172.168.0.9
    """
    try:
        if "api_login_timeout" not in kwargs:
            kwargs["api_login_timeout"] = 0
        with _IpmiSession(**kwargs) as s:
            # TODO: should a test command be fired?
            # s.raw_command(netfn=6, command=1, retry=False)
            return True
    except Exception as e:  # pylint: disable=broad-except
        return False
    return True


def set_channel_access(
    channel=14,
    access_update_mode="non_volatile",
    alerting=False,
    per_msg_auth=False,
    user_level_auth=False,
    access_mode="always",
    privilege_update_mode="non_volatile",
    privilege_level="administrator",
    **kwargs
):
    """
    Set channel access

    :param channel: number [1:7]

    :param access_update_mode:
        - 'dont_change'  = don't set or change Channel Access
        - 'non_volatile' = set non-volatile Channel Access
        - 'volatile'     = set volatile (active) setting of Channel Access

    :param alerting:
        PEF Alerting Enable/Disable

        - True  = enable PEF Alerting
        - False = disable PEF Alerting on this channel
          (Alert Immediate command can still be used to generate alerts)

    :param per_msg_auth:
        Per-message Authentication

        - True  = enable
        - False = disable Per-message Authentication. [Authentication required to
          activate any session on this channel, but authentication not
          used on subsequent packets for the session.]

    :param user_level_auth:
        User Level Authentication Enable/Disable

        - True  = enable User Level Authentication. All User Level commands are
          to be authenticated per the Authentication Type that was
          negotiated when the session was activated.
        - False = disable User Level Authentication. Allow User Level commands to
          be executed without being authenticated.
          If the option to disable User Level Command authentication is
          accepted, the BMC will accept packets with Authentication Type
          set to None if they contain user level commands.
          For outgoing packets, the BMC returns responses with the same
          Authentication Type that was used for the request.

    :param access_mode:
        Access Mode for IPMI messaging (PEF Alerting is enabled/disabled
        separately from IPMI messaging)

        - disabled = disabled for IPMI messaging
        - pre_boot = pre-boot only channel only available when system is
          in a powered down state or in BIOS prior to start of boot.
        - always   = channel always available regardless of system mode.
          BIOS typically dedicates the serial connection to the BMC.
        - shared   = same as always available, but BIOS typically leaves the
          serial port available for software use.

    :param privilege_update_mode:
        Channel Privilege Level Limit. This value sets the maximum privilege
        level that can be accepted on the specified channel.

        - dont_change  = don't set or change channel Privilege Level Limit
        - non_volatile = non-volatile Privilege Level Limit according
        - volatile     = volatile setting of Privilege Level Limit

    :param privilege_level:
        Channel Privilege Level Limit

        - reserved      = unused
        - callback
        - user
        - operator
        - administrator
        - proprietary   = used by OEM

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.set_channel_access privilege_level='administrator'
    """
    with _IpmiCommand(**kwargs) as s:
        return s.set_channel_access(
            channel,
            access_update_mode,
            alerting,
            per_msg_auth,
            user_level_auth,
            access_mode,
            privilege_update_mode,
            privilege_level,
        )


def get_channel_access(channel=14, read_mode="non_volatile", **kwargs):
    """
    :param kwargs:api_host='127.0.0.1' api_user='admin' api_pass='example' api_port=623

    :param channel: number [1:7]

    :param read_mode:
        - non_volatile  = get non-volatile Channel Access
        - volatile      = get present volatile (active) setting of Channel Access

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    Return Data

        A Python dict with the following keys/values:

        .. code-block:: python

            {
                alerting:
                per_msg_auth:
                user_level_auth:
                access_mode:{ (ONE OF)
                    0: 'disabled',
                    1: 'pre_boot',
                    2: 'always',
                    3: 'shared'
                }
                privilege_level: { (ONE OF)
                    1: 'callback',
                    2: 'user',
                    3: 'operator',
                    4: 'administrator',
                    5: 'proprietary',
                }
            }

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_channel_access channel=1
    """
    with _IpmiCommand(**kwargs) as s:
        return s.get_channel_access(channel)


def get_channel_info(channel=14, **kwargs):
    """
    Get channel info

    :param channel: number [1:7]
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    Return Data
        channel session supports

        .. code-block:: none

                - no_session: channel is session-less
                - single: channel is single-session
                - multi: channel is multi-session
                - auto: channel is session-based (channel could alternate between
                    single- and multi-session operation, as can occur with a
                    serial/modem channel that supports connection mode auto-detect)

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_channel_info
    """
    with _IpmiCommand(**kwargs) as s:
        return s.get_channel_info(channel)


def set_user_access(
    uid,
    channel=14,
    callback=True,
    link_auth=True,
    ipmi_msg=True,
    privilege_level="administrator",
    **kwargs
):
    """
    Set user access

    :param uid: user number [1:16]

    :param channel: number [1:7]

    :param callback:
        User Restricted to Callback

        - False = User Privilege Limit is determined by the User Privilege Limit
          parameter, below, for both callback and non-callback connections.
        - True  = User Privilege Limit is determined by the User Privilege Limit
          parameter for callback connections, but is restricted to Callback
          level for non-callback connections. Thus, a user can only initiate
          a Callback when they 'call in' to the BMC, but once the callback
          connection has been made, the user could potentially establish a
          session as an Operator.

    :param link_auth: User Link authentication enable/disable (used to enable
        whether this user's name and password information will be used for link
        authentication, e.g. PPP CHAP) for the given channel. Link
        authentication itself is a global setting for the channel and is
        enabled/disabled via the serial/modem configuration parameters.

    :param ipmi_msg: User IPMI Messaging: (used to enable/disable whether
        this user's name and password information will be used for IPMI
        Messaging. In this case, 'IPMI Messaging' refers to the ability to
        execute generic IPMI commands that are not associated with a
        particular payload type. For example, if IPMI Messaging is disabled for
        a user, but that user is enabled for activating the SOL
        payload type, then IPMI commands associated with SOL and session
        management, such as Get SOL Configuration Parameters and Close Session
        are available, but generic IPMI commands such as Get SEL Time are
        unavailable.)

    :param privilege_level:
        User Privilege Limit. (Determines the maximum privilege level that the
        user is allowed to switch to on the specified channel.)

        - callback
        - user
        - operator
        - administrator
        - proprietary
        - no_access

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.set_user_access uid=2 privilege_level='operator'
    """
    with _IpmiCommand(**kwargs) as s:
        return s.set_user_access(
            uid, channel, callback, link_auth, ipmi_msg, privilege_level
        )


def get_user_access(uid, channel=14, **kwargs):
    """
    Get user access

    :param uid: user number [1:16]
    :param channel: number [1:7]
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    Return Data

    .. code-block:: none

        channel_info:
            - max_user_count = maximum number of user IDs on this channel
            - enabled_users = count of User ID slots presently in use
            - users_with_fixed_names = count of user IDs with fixed names
        access:
            - callback
            - link_auth
            - ipmi_msg
            - privilege_level: [reserved, callback, user, operator
                               administrator, proprietary, no_access]

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_user_access uid=2
    """
    ## user access available during call-in or callback direct connection
    with _IpmiCommand(**kwargs) as s:
        return s.get_user_access(uid, channel=channel)


def set_user_name(uid, name, **kwargs):
    """
    Set user name

    :param uid: user number [1:16]
    :param name: username (limit of 16bytes)
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.set_user_name uid=2 name='steverweber'
    """
    with _IpmiCommand(**kwargs) as s:
        return s.set_user_name(uid, name)


def get_user_name(uid, return_none_on_error=True, **kwargs):
    """
    Get user name

    :param uid: user number [1:16]
    :param return_none_on_error: return None on error
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_user_name uid=2
    """
    with _IpmiCommand(**kwargs) as s:
        return s.get_user_name(uid, return_none_on_error=True)


def set_user_password(uid, mode="set_password", password=None, **kwargs):
    """
    Set user password and (modes)

    :param uid: id number of user.  see: get_names_uid()['name']

    :param mode:
        - disable       = disable user connections
        - enable        = enable user connections
        - set_password  = set or ensure password
        - test_password = test password is correct
    :param password: max 16 char string
        (optional when mode is [disable or enable])
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    :return:
        True on success
        when mode = test_password, return False on bad password

    CLI Example:

    .. code-block:: bash

        salt-call ipmi.set_user_password api_host=127.0.0.1 api_user=admin api_pass=pass
                                         uid=1 password=newPass
        salt-call ipmi.set_user_password uid=1 mode=enable
    """
    with _IpmiCommand(**kwargs) as s:
        s.set_user_password(uid, mode="set_password", password=password)
    return True


def get_health(**kwargs):
    """
    Get Summarize health

    This provides a summary of the health of the managed system.
    It additionally provides an iterable list of reasons for
    warning, critical, or failed assessments.

    good health: {'badreadings': [], 'health': 0}

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Example:

    .. code-block:: bash

        salt-call ipmi.get_health api_host=127.0.0.1 api_user=admin api_pass=pass
    """
    with _IpmiCommand(**kwargs) as s:
        return s.get_health()


def get_power(**kwargs):
    """
    Get current power state

    The response, if successful, should contain 'powerstate' key and
    either 'on' or 'off' to indicate current state.

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Example:

    .. code-block:: bash

        salt-call ipmi.get_power api_host=127.0.0.1 api_user=admin api_pass=pass
    """
    with _IpmiCommand(**kwargs) as s:
        return s.get_power()["powerstate"]


def get_sensor_data(**kwargs):
    """
    Get sensor readings

    Iterates sensor reading objects

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Example:

    .. code-block:: bash

        salt-call ipmi.get_sensor_data api_host=127.0.0.1 api_user=admin api_pass=pass
    """
    import ast

    with _IpmiCommand(**kwargs) as s:
        data = {}
        for reading in s.get_sensor_data():
            if reading:
                r = ast.literal_eval(repr(reading))
                data[r.pop("name")] = r
    return data


def get_bootdev(**kwargs):
    """
    Get current boot device override information.

    Provides the current requested boot device.  Be aware that not all IPMI
    devices support this.  Even in BMCs that claim to, occasionally the
    BIOS or UEFI fail to honor it. This is usually only applicable to the
    next reboot.

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Example:

    .. code-block:: bash

        salt-call ipmi.get_bootdev api_host=127.0.0.1 api_user=admin api_pass=pass
    """
    with _IpmiCommand(**kwargs) as s:
        return s.get_bootdev()


def set_power(state="power_on", wait=True, **kwargs):
    """
    Request power state change

    :param name:
        * power_on -- system turn on
        * power_off -- system turn off (without waiting for OS)
        * shutdown -- request OS proper shutdown
        * reset -- reset (without waiting for OS)
        * boot -- If system is off, then 'on', else 'reset'

    :param ensure: If (bool True), do not return until system actually completes
                requested state change for 300 seconds.
                If a non-zero (int), adjust the wait time to the
                requested number of seconds
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    :returns: dict -- A dict describing the response retrieved

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.set_power state=shutdown wait=True
    """
    if state is True or state == "power_on":
        state = "on"
    if state is False or state == "power_off":
        state = "off"
    with _IpmiCommand(**kwargs) as s:
        return s.set_power(state, wait=wait)


def set_bootdev(bootdev="default", persist=False, uefiboot=False, **kwargs):
    """
    Set boot device to use on next reboot

    :param bootdev:
        - network: Request network boot
        - hd: Boot from hard drive
        - safe: Boot from hard drive, requesting 'safe mode'
        - optical: boot from CD/DVD/BD drive
        - setup: Boot into setup utility
        - default: remove any IPMI directed boot device
          request

    :param persist: If true, ask that system firmware use this device
                    beyond next boot.  Be aware many systems do not honor
                    this

    :param uefiboot: If true, request UEFI boot explicitly.  Strictly
                    speaking, the spec suggests that if not set, the system
                    should BIOS boot and offers no "don't care" option.
                    In practice, this flag not being set does not preclude
                    UEFI boot on any system I've encountered.

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    :returns: dict or True -- If callback is not provided, the response

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.set_bootdev bootdev=network persist=True
    """
    with _IpmiCommand(**kwargs) as s:
        return s.set_bootdev(bootdev)


def set_identify(on=True, duration=600, **kwargs):
    """
    Request identify light

    Request the identify light to turn off, on for a duration,
    or on indefinitely.  Other than error exceptions,

    :param on: Set to True to force on or False to force off
    :param duration: Set if wanting to request turn on for a duration
                    in seconds, None = indefinitely.
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.set_identify
    """
    with _IpmiCommand(**kwargs) as s:
        return s.set_identify(on=on, duration=duration)


def get_channel_max_user_count(channel=14, **kwargs):
    """
    Get max users in channel

    :param channel: number [1:7]
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None
    :return: int -- often 16

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_channel_max_user_count
    """
    access = get_user_access(channel=channel, uid=1, **kwargs)
    return access["channel_info"]["max_user_count"]


def get_user(uid, channel=14, **kwargs):
    """
    Get user from uid and access on channel

    :param uid: user number [1:16]
    :param channel: number [1:7]
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    Return Data

    .. code-block:: none

        name: (str)
        uid: (int)
        channel: (int)
        access:
            - callback (bool)
            - link_auth (bool)
            - ipmi_msg (bool)
            - privilege_level: (str)[callback, user, operatorm administrator,
                                    proprietary, no_access]

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_user uid=2
    """
    name = get_user_name(uid, **kwargs)
    access = get_user_access(uid, channel, **kwargs)
    data = {"name": name, "uid": uid, "channel": channel, "access": access["access"]}
    return data


def get_users(channel=14, **kwargs):
    """
    get list of users and access information

    :param channel: number [1:7]

    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    :return:
        - name: (str)
        - uid: (int)
        - channel: (int)
        - access:
            - callback (bool)
            - link_auth (bool)
            - ipmi_msg (bool)
            - privilege_level: (str)[callback, user, operatorm administrator,
              proprietary, no_access]

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.get_users api_host=172.168.0.7
    """
    with _IpmiCommand(**kwargs) as c:
        return c.get_users(channel)


def create_user(
    uid,
    name,
    password,
    channel=14,
    callback=False,
    link_auth=True,
    ipmi_msg=True,
    privilege_level="administrator",
    **kwargs
):
    """
    create/ensure a user is created with provided settings.

    :param privilege_level:
        User Privilege Limit. (Determines the maximum privilege level that
        the user is allowed to switch to on the specified channel.)
        * callback
        * user
        * operator
        * administrator
        * proprietary
        * no_access
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.create_user uid=2 name=steverweber api_host=172.168.0.7 api_pass=nevertell
    """
    with _IpmiCommand(**kwargs) as c:
        return c.create_user(
            uid, name, password, channel, callback, link_auth, ipmi_msg, privilege_level
        )


def user_delete(uid, channel=14, **kwargs):
    """
    Delete user (helper)

    :param uid: user number [1:16]
    :param channel: number [1:7]
    :param kwargs:
        - api_host=127.0.0.1
        - api_user=admin
        - api_pass=example
        - api_port=623
        - api_kg=None

    CLI Examples:

    .. code-block:: bash

        salt-call ipmi.user_delete uid=2
    """
    with _IpmiCommand(**kwargs) as c:
        return c.user_delete(uid, channel)

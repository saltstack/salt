# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 IBM Corporation
# Copyright 2015 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# This represents the low layer message framing portion of IPMI

import pyghmi.constants as const
import pyghmi.exceptions as exc

from pyghmi.ipmi.private import session
import pyghmi.ipmi.sdr as sdr


boot_devices = {
    'net': 4,
    'network': 4,
    'pxe': 4,
    'hd': 8,
    'safe': 0xc,
    'cd': 0x14,
    'cdrom': 0x14,
    'optical': 0x14,
    'dvd': 0x14,
    'floppy': 0x3c,
    'default': 0x0,
    'setup': 0x18,
    'bios': 0x18,
    'f1': 0x18,
    1: 'network',
    2: 'hd',
    3: 'safe',
    5: 'optical',
    6: 'setup',
    15: 'floppy',
    0: 'default'
}

power_states = {
    "off": 0,
    "on": 1,
    "reset": 3,
    "softoff": 5,
    "shutdown": 5,
    # NOTE(jbjohnso): -1 is not a valid direct boot state,
    #                 but here for convenience of 'in' statement
    "boot": -1,
}


class Command(object):
    """Send IPMI commands to BMCs.

    This object represents a persistent session to an IPMI device (bmc) and
    allows the caller to reuse a single session to issue multiple commands.
    This class can be used in a synchronous (wait for answer and return) or
    asynchronous fashion (return immediately and provide responses by
    callbacks).  Synchronous mode is the default behavior.

    For asynchronous mode, simply pass in a callback function.  It is
    recommended to pass in an instance method to callback and ignore the
    callback_args parameter. However, callback_args can optionally be populated
    if desired.

    :param bmc: hostname or ip address of the BMC
    :param userid: username to use to connect
    :param password: password to connect to the BMC
    :param onlogon: function to run when logon completes in an asynchronous
                    fashion.  This will result in a greenthread behavior.
    :param kg: Optional parameter to use if BMC has a particular Kg configured
    """

    def __init__(self, bmc, userid, password, port=623, onlogon=None, kg=None):
        # TODO(jbjohnso): accept tuples and lists of each parameter for mass
        # operations without pushing the async complexities up the stack
        self.onlogon = onlogon
        self.bmc = bmc
        self._sdr = None
        if onlogon is not None:
            self.ipmi_session = session.Session(bmc=bmc,
                                                userid=userid,
                                                password=password,
                                                onlogon=self.logged,
                                                port=port,
                                                kg=kg)
            # induce one iteration of the loop, now that we would be
            # prepared for it in theory
            session.Session.wait_for_rsp(0)
        else:
            self.ipmi_session = session.Session(bmc=bmc,
                                                userid=userid,
                                                password=password,
                                                port=port,
                                                kg=kg)

    def logged(self, response):
        self.onlogon(response, self)

    @classmethod
    def eventloop(cls):
        while session.Session.wait_for_rsp():
            pass

    @classmethod
    def wait_for_rsp(cls, timeout):
        """Delay for no longer than timeout for next response.

        This acts like a sleep that exits on activity.

        :param timeout: Maximum number of seconds before returning
        """
        return session.Session.wait_for_rsp(timeout=timeout)

    def get_bootdev(self):
        """Get current boot device override information.

        Provides the current requested boot device.  Be aware that not all IPMI
        devices support this.  Even in BMCs that claim to, occasionally the
        BIOS or UEFI fail to honor it. This is usually only applicable to the
        next reboot.

        :raises: IpmiException on an error.
        :returns: dict --The response will be provided in the return as a dict
        """
        response = self.raw_command(netfn=0, command=9, data=(5, 0, 0))
        # interpret response per 'get system boot options'
        if 'error' in response:
            raise exc.IpmiException(response['error'])
        # this should only be invoked for get system boot option complying to
        # ipmi spec and targeting the 'boot flags' parameter
        assert (response['command'] == 9 and
                response['netfn'] == 1 and
                response['data'][0] == 1 and
                (response['data'][1] & 0b1111111) == 5)
        if (response['data'][1] & 0b10000000 or
                not response['data'][2] & 0b10000000):
            return {'bootdev': 'default', 'persistent': True}
        else:  # will consult data2 of the boot flags parameter for the data
            persistent = False
            uefimode = False
            if response['data'][2] & 0b1000000:
                persistent = True
            if response['data'][2] & 0b100000:
                uefimode = True
            bootnum = (response['data'][3] & 0b111100) >> 2
            bootdev = boot_devices.get(bootnum)
            if bootdev:
                return {'bootdev': bootdev,
                        'persistent': persistent,
                        'uefimode': uefimode}
            else:
                return {'bootdev': bootnum,
                        'persistent': persistent,
                        'uefimode': uefimode}

    def set_power(self, powerstate, wait=False):
        """Request power state change (helper)

        :param powerstate:
                            * on -- Request system turn on
                            * off -- Request system turn off without waiting
                                     for OS to shutdown
                            * shutdown -- Have system request OS proper
                                          shutdown
                            * reset -- Request system reset without waiting for
                              OS
                            * boot -- If system is off, then 'on', else 'reset'
        :param wait: If True, do not return until system actually completes
                     requested state change for 300 seconds.
                     If a non-zero number, adjust the wait time to the
                     requested number of seconds
        :returns: dict -- A dict describing the response retrieved
        """
        if powerstate not in power_states:
            raise exc.InvalidParameterValue(
                "Unknown power state %s requested" % powerstate)
        newpowerstate = powerstate
        response = self.raw_command(netfn=0, command=1)
        if 'error' in response:
            raise exc.IpmiException(response['error'])
        oldpowerstate = 'on' if (response['data'][0] & 1) else 'off'
        if oldpowerstate == newpowerstate:
            return {'powerstate': oldpowerstate}
        if newpowerstate == 'boot':
            newpowerstate = 'on' if oldpowerstate == 'off' else 'reset'
        response = self.raw_command(
            netfn=0, command=2, data=[power_states[newpowerstate]])
        if 'error' in response:
            raise exc.IpmiException(response['error'])
        lastresponse = {'pendingpowerstate': newpowerstate}
        waitattempts = 300
        if not isinstance(wait, bool):
            waitattempts = wait
        if (wait and
           newpowerstate in ('on', 'off', 'shutdown', 'softoff')):
            if newpowerstate in ('softoff', 'shutdown'):
                waitpowerstate = 'off'
            else:
                waitpowerstate = newpowerstate
            currpowerstate = None
            while currpowerstate != waitpowerstate and waitattempts > 0:
                response = self.raw_command(netfn=0, command=1, delay_xmit=1)
                if 'error' in response:
                    return response
                currpowerstate = 'on' if (response['data'][0] & 1) else 'off'
                waitattempts -= 1
            if currpowerstate != waitpowerstate:
                raise exc.IpmiException(
                    "System did not accomplish power state change")
            return {'powerstate': currpowerstate}
        else:
            return lastresponse

    def set_bootdev(self,
                    bootdev,
                    persist=False,
                    uefiboot=False):
        """Set boot device to use on next reboot (helper)

        :param bootdev:
                        *network -- Request network boot
                        *hd -- Boot from hard drive
                        *safe -- Boot from hard drive, requesting 'safe mode'
                        *optical -- boot from CD/DVD/BD drive
                        *setup -- Boot into setup utility
                        *default -- remove any IPMI directed boot device
                                    request
        :param persist: If true, ask that system firmware use this device
                        beyond next boot.  Be aware many systems do not honor
                        this
        :param uefiboot: If true, request UEFI boot explicitly.  Strictly
                         speaking, the spec sugests that if not set, the system
                         should BIOS boot and offers no "don't care" option.
                         In practice, this flag not being set does not preclude
                         UEFI boot on any system I've encountered.
        :raises: IpmiException on an error.
        :returns: dict or True -- If callback is not provided, the response
        """
        if bootdev not in boot_devices:
            return {'error': "Unknown bootdevice %s requested" % bootdev}
        bootdevnum = boot_devices[bootdev]
        # first, we disable timer by way of set system boot options,
        # then move on to set chassis capabilities
        # Set System Boot Options is netfn=0, command=8, data
        response = self.raw_command(netfn=0, command=8, data=(3, 8))
        if 'error' in response:
            raise exc.IpmiException(response['error'])
        bootflags = 0x80
        if uefiboot:
            bootflags |= 1 << 5
        if persist:
            bootflags |= 1 << 6
        if bootdevnum == 0:
            bootflags = 0
        data = (5, bootflags, bootdevnum, 0, 0, 0)
        response = self.raw_command(netfn=0, command=8, data=data)
        if 'error' in response:
            raise exc.IpmiException(response['error'])
        return {'bootdev': bootdev}

    def raw_command(self, netfn, command, bridge_request=(), data=(),
                    delay_xmit=None):
        """Send raw ipmi command to BMC

        This allows arbitrary IPMI bytes to be issued.  This is commonly used
        for certain vendor specific commands.

        Example: ipmicmd.raw_command(netfn=0,command=4,data=(5))

        :param netfn: Net function number
        :param command: Command value
        :param bridge_request: The target slave address and channel number for
                               the bridge request.
        :param data: Command data as a tuple or list
        :returns: dict -- The response from IPMI device
        """
        return self.ipmi_session.raw_command(netfn=netfn, command=command,
                                             bridge_request=bridge_request,
                                             data=data, delay_xmit=delay_xmit)

    def get_power(self):
        """Get current power state of the managed system

        The response, if successful, should contain 'powerstate' key and
        either 'on' or 'off' to indicate current state.

        :returns: dict -- {'powerstate': value}
        """
        response = self.raw_command(netfn=0, command=1)
        if 'error' in response:
            raise exc.IpmiException(response['error'])
        assert(response['command'] == 1 and response['netfn'] == 1)
        powerstate = 'on' if (response['data'][0] & 1) else 'off'
        return {'powerstate': powerstate}

    def set_identify(self, on=True, duration=None):
        """Request identify light

        Request the identify light to turn off, on for a duration,
        or on indefinitely.  Other than error exceptions,

        :param on: Set to True to force on or False to force off
        :param duration: Set if wanting to request turn on for a duration
                         rather than indefinitely on
        """
        if duration is not None:
            duration = int(duration)
            if duration > 255:
                duration = 255
            if duration < 0:
                duration = 0
            response = self.raw_command(netfn=0, command=4, data=[duration])
            if 'error' in response:
                raise exc.IpmiException(response['error'])
            return
        forceon = 0
        if on:
            forceon = 1
        if self.ipmi_session.ipmiversion < 2.0:
            # ipmi 1.5 made due with just one byte, make best effort
            # to imitate indefinite as close as possible
            identifydata = [255 * forceon]
        else:
            identifydata = [0, forceon]
        response = self.raw_command(netfn=0, command=4, data=identifydata)
        if 'error' in response:
            raise exc.IpmiException(response['error'])

    def get_health(self):
        """Summarize health of managed system

        This provides a summary of the health of the managed system.
        It additionally provides an iterable list of reasons for
        warning, critical, or failed assessments.
        """
        summary = {'badreadings': [], 'health': const.Health.Ok}
        for reading in self.get_sensor_data():
            if reading.health != const.Health.Ok:
                summary['health'] |= reading.health
                summary['badreadings'].append(reading)
        return summary

    def get_sensor_reading(self, sensorname):
        """Get a sensor reading by name

        Returns a single decoded sensor reading per the name
        passed in

        :param sensorname:  Name of the desired sensor
        :returns: sdr.SensorReading object
        """
        if self._sdr is None:
            self._sdr = sdr.SDR(self)
        for sensor in self._sdr.get_sensor_numbers():
            if self._sdr.sensors[sensor].name == sensorname:
                rsp = self.raw_command(command=0x2d, netfn=4, data=(sensor,))
                if 'error' in rsp:
                    raise exc.IpmiException(rsp['error'], rsp['code'])
                return self._sdr.sensors[sensor].decode_sensor_reading(
                    rsp['data'])
        raise Exception('Sensor not found: ' + sensorname)

    def get_sensor_data(self):
        """Get sensor reading objects

        Iterates sensor reading objects pertaining to the currently
        managed BMC.

        :returns: Iterator of sdr.SensorReading objects
        """
        if self._sdr is None:
            self._sdr = sdr.SDR(self)
        for sensor in self._sdr.get_sensor_numbers():
            rsp = self.raw_command(command=0x2d, netfn=4, data=(sensor,))
            if 'error' in rsp:
                if rsp['code'] == 203:  # Sensor does not exist, optional dev
                    continue
                raise exc.IpmiException(rsp['error'], code=rsp['code'])
            yield self._sdr.sensors[sensor].decode_sensor_reading(rsp['data'])

    def get_sensor_descriptions(self):
        """Get available sensor names

        Iterates over the available sensor descriptions

        :returns: Iterator of dicts describing each sensor
        """
        if self._sdr is None:
            self._sdr = sdr.SDR(self)
        for sensor in self._sdr.get_sensor_numbers():
            yield {'name': self._sdr.sensors[sensor].name,
                   'type': self._sdr.sensors[sensor].sensor_type}

    def set_channel_access(self, channel=14, access_update_mode='non_volatile',
                           alerting=False, per_msg_auth=False,
                           user_level_auth=False, access_mode='always',
                           privilege_update_mode='non_volatile',
                           privilege_level='administrator'):
        """Set channel access

        :param channel: number [1:7]

        :param access_update_mode:
            dont_change  = don't set or change Channel Access
            non_volatile = set non-volatile Channel Access
            volatile     = set volatile (active) setting of Channel Access

        :param alerting: PEF Alerting Enable/Disable
        True  = enable PEF Alerting
        False = disable PEF Alerting on this channel
                (Alert Immediate command can still be used to generate alerts)

        :param per_msg_auth: Per-message Authentication
        True  = enable
        False = disable Per-message Authentication. [Authentication required to
                activate any session on this channel, but authentication not
                used on subsequent packets for the session.]

        :param user_level_auth: User Level Authentication Enable/Disable.
        True  = enable User Level Authentication. All User Level commands are
            to be authenticated per the Authentication Type that was
            negotiated when the session was activated.
        False = disable User Level Authentication. Allow User Level commands to
            be executed without being authenticated.
            If the option to disable User Level Command authentication is
            accepted, the BMC will accept packets with Authentication Type
            set to None if they contain user level commands.
            For outgoing packets, the BMC returns responses with the same
            Authentication Type that was used for the request.

        :param access_mode: Access Mode for IPMI messaging
        (PEF Alerting is enabled/disabled separately from IPMI messaging)
        disabled = disabled for IPMI messaging
        pre_boot = pre-boot only channel only available when system is in a
                powered down state or in BIOS prior to start of boot.
        always   = channel always available regardless of system mode.
                BIOS typically dedicates the serial connection to the BMC.
        shared   = same as always available, but BIOS typically leaves the
                serial port available for software use.

        :param privilege_update_mode: Channel Privilege Level Limit.
            This value sets the maximum privilege level
            that can be accepted on the specified channel.
            dont_change  = don't set or change channel Privilege Level Limit
            non_volatile = non-volatile Privilege Level Limit according
            volatile     = volatile setting of Privilege Level Limit

        :param privilege_level: Channel Privilege Level Limit
            * reserved      = unused
            * callback
            * user
            * operator
            * administrator
            * proprietary   = used by OEM
        """
        data = []
        data.append(channel & 0b00001111)
        access_update_modes = {
            'dont_change': 0,
            'non_volatile': 1,
            'volatile': 2,
            #'reserved': 3
        }
        b = 0
        b |= (access_update_modes[access_update_mode] << 6) & 0b11000000
        if alerting:
            b |= 0b00100000
        if per_msg_auth:
            b |= 0b00010000
        if user_level_auth:
            b |= 0b00001000
        access_modes = {
            'disabled': 0,
            'pre_boot': 1,
            'always': 2,
            'shared': 3,
        }
        b |= access_modes[access_mode] & 0b00000111
        data.append(b)
        b = 0
        privilege_update_modes = {
            'dont_change': 0,
            'non_volatile': 1,
            'volatile': 2,
            #'reserved': 3
        }
        b |= (privilege_update_modes[privilege_update_mode] << 6) & 0b11000000
        privilege_levels = {
            'reserved': 0,
            'callback': 1,
            'user': 2,
            'operator': 3,
            'administrator': 4,
            'proprietary': 5,
            # 'no_access': 0x0F,
        }
        b |= privilege_levels[privilege_level] & 0b00000111
        data.append(b)
        response = self.raw_command(netfn=0x06, command=0x40, data=data)
        if 'error' in response:
            raise Exception(response['error'])
        return True

    def get_channel_access(self, channel=14, read_mode='volatile'):
        """Get channel access

        :param channel: number [1:7]
        :param read_mode:
        non_volatile  = get non-volatile Channel Access
        volatile      = get present volatile (active) setting of Channel Access

        :return: A Python dict with the following keys/values:
          {
            - alerting:
            - per_msg_auth:
            - user_level_auth:
            - access_mode:{
                0: 'disabled',
                1: 'pre_boot',
                2: 'always',
                3: 'shared'
              }
            - privilege_level: {
                1: 'callback',
                2: 'user',
                3: 'operator',
                4: 'administrator',
                5: 'proprietary',
              }
           }
        """
        data = []
        data.append(channel & 0b00001111)
        b = 0
        read_modes = {
            'non_volatile': 1,
            'volatile': 2,
        }
        b |= (read_modes[read_mode] << 6) & 0b11000000
        data.append(b)

        response = self.raw_command(netfn=0x06, command=0x41, data=data)
        if 'error' in response:
            raise Exception(response['error'])

        data = response['data']
        if len(data) != 2:
            raise Exception('expecting 2 data bytes')

        r = {}
        r['alerting'] = data[0] & 0b10000000 > 0
        r['per_msg_auth'] = data[0] & 0b01000000 > 0
        r['user_level_auth'] = data[0] & 0b00100000 > 0
        access_modes = {
            0: 'disabled',
            1: 'pre_boot',
            2: 'always',
            3: 'shared'
        }
        r['access_mode'] = access_modes[data[0] & 0b00000011]
        privilege_levels = {
            0: 'reserved',
            1: 'callback',
            2: 'user',
            3: 'operator',
            4: 'administrator',
            5: 'proprietary',
            #0x0F: 'no_access'
        }
        r['privilege_level'] = privilege_levels[data[1] & 0b00001111]
        return r

    def get_channel_info(self, channel=14):
        """Get channel info

        :param channel: number [1:7]

        :return:
        session_support:
            no_session: channel is session-less
            single: channel is single-session
            multi: channel is multi-session
            auto: channel is session-based (channel could alternate between
                single- and multi-session operation, as can occur with a
                serial/modem channel that supports connection mode auto-detect)
        """
        data = []
        data.append(channel & 0b00001111)
        response = self.raw_command(netfn=0x06, command=0x42, data=data)
        if 'error' in response:
            raise Exception(response['error'])
        data = response['data']
        if len(data) != 9:
            raise Exception('expecting 10 data bytes got: {0}'.format(data))
        r = {}
        r['Actual channel'] = data[0] & 0b00000111
        channel_medium_types = {
            0: 'reserved',
            1: 'IPMB',
            2: 'ICMB v1.0',
            3: 'ICMB v0.9',
            4: '802.3 LAN',
            5: 'Asynch. Serial/Modem (RS-232)',
            6: 'Other LAN',
            7: 'PCI SMBus',
            8: 'SMBus v1.0/1.1',
            9: 'SMBus v2.0',
            0x0a: 'reserved for USB 1.x',
            0x0b: 'reserved for USB 2.x',
            0x0c: 'System Interface (KCS, SMIC, or BT)',
            ## 60h-7Fh: OEM
            ## all other  reserved
        }
        t = data[1] & 0b01111111
        if t in channel_medium_types:
            r['Channel Medium type'] = channel_medium_types[t]
        else:
            r['Channel Medium type'] = 'OEM {:02X}'.format(t)
        r['5-bit Channel IPMI Messaging Protocol Type'] = data[2] & 0b00001111
        session_supports = {
            0: 'no_session',
            1: 'single',
            2: 'multi',
            3: 'auto'
        }
        r['session_support'] = session_supports[(data[3] & 0b11000000) >> 6]
        r['active_session_count'] = data[3] & 0b00111111
        r['Vendor ID'] = [data[4], data[5], data[6]]
        r['Auxiliary Channel Info'] = [data[7], data[8]]
        return r

    def set_user_access(self, uid, channel=14, callback=False, link_auth=True,
                        ipmi_msg=True, privilege_level='user'):
        """Set user access

        :param uid: user number [1:16]

        :param channel: number [1:7]

        :parm callback: User Restricted to Callback
        False = User Privilege Limit is determined by the User Privilege Limit
            parameter, below, for both callback and non-callback connections.
        True  = User Privilege Limit is determined by the User Privilege Limit
            parameter for callback connections, but is restricted to Callback
            level for non-callback connections. Thus, a user can only initiate
            a Callback when they 'call in' to the BMC, but once the callback
            connection has been made, the user could potentially establish a
            session as an Operator.

        :param link_auth: User Link authentication
        enable/disable (used to enable whether this
        user's name and password information will be used for link
        authentication, e.g. PPP CHAP) for the given channel. Link
        authentication itself is a global setting for the channel and is
        enabled/disabled via the serial/modem configuration parameters.

        :param ipmi_msg: User IPMI Messaginge:
        (used to enable/disable whether
        this user's name and password information will be used for IPMI
        Messaging. In this case, 'IPMI Messaging' refers to the ability to
        execute generic IPMI commands that are not associated with a
        particular payload type. For example, if IPMI Messaging is disabled for
        a user, but that user is enabled for activatallow_authing the SOL
        payload type, then IPMI commands associated with SOL and session
        management, such as Get SOL Configuration Parameters and Close Session
        are available, but generic IPMI commands such as Get SEL Time are
        unavailable.)

        :param privilege_level:
        User Privilege Limit. (Determines the maximum privilege level that the
        user is allowed to switch to on the specified channel.)
            * callback
            * user
            * operator
            * administrator
            * proprietary
            * no_access
        """
        b = 0b10000000
        if callback:
            b |= 0b01000000
        if link_auth:
            b |= 0b00100000
        if ipmi_msg:
            b |= 0b00010000
        b |= channel & 0b00001111
        privilege_levels = {
            'reserved': 0,
            'callback': 1,
            'user': 2,
            'operator': 3,
            'administrator': 4,
            'proprietary': 5,
            'no_access': 0x0F,
        }
        data = [b, uid & 0b00111111,
                privilege_levels[privilege_level] & 0b00001111]
        response = self.raw_command(netfn=0x06, command=0x43, data=data)
        if 'error' in response:
            raise Exception(response['error'])
        return True

    def get_user_access(self, uid, channel=14):
        """Get user access

        :param uid: user number [1:16]
        :param channel: number [1:7]

        :return:
        channel_info:
            max_user_count = maximum number of user IDs on this channel
            enabled_users = count of User ID slots presently in use
            users_with_fixed_names = count of user IDs with fixed names

        access:
            callback
            link_auth
            ipmi_msg
            privilege_level: [reserved, callback, user,
                              operatorm administrator, proprietary, no_access]
        """
        ## user access available during call-in or callback direct connection
        data = [channel, uid]
        response = self.raw_command(netfn=0x06, command=0x44, data=data)
        if 'error' in response:
            raise Exception(response['error'])
        data = response['data']
        if len(data) != 4:
            raise Exception('expecting 4 data bytes')
        r = {'channel_info': {}, 'access': {}}
        r['channel_info']['max_user_count'] = data[0]
        r['channel_info']['enabled_users'] = data[1] & 0b00111111
        r['channel_info']['users_with_fixed_names'] = data[2] & 0b00111111
        r['access']['callback'] = (data[3] & 0b01000000) != 0
        r['access']['link_auth'] = (data[3] & 0b00100000) != 0
        r['access']['ipmi_msg'] = (data[3] & 0b00010000) != 0
        privilege_levels = {
            0: 'reserved',
            1: 'callback',
            2: 'user',
            3: 'operator',
            4: 'administrator',
            5: 'proprietary',
            0x0F: 'no_access'
        }
        r['access']['privilege_level'] = privilege_levels[data[3] & 0b00001111]
        return r

    def set_user_name(self, uid, name):
        """Set user name

        :param uid: user number [1:16]
        :param name: username (limit of 16bytes)
        """
        data = [uid]
        if len(name) > 16:
            raise Exception('name must be less than or = 16 chars')
        name = name.ljust(16, "\x00")
        data.extend([ord(x) for x in name])
        response = self.raw_command(netfn=0x06, command=0x45, data=data)
        if 'error' in response:
            raise Exception(response['error'])
        return True

    def get_user_name(self, uid, return_none_on_error=True):
        """Get user name

        :param uid: user number [1:16]
        :param return_none_on_error: return None on error
            TODO: investigate return code on error
        """
        response = self.raw_command(netfn=0x06, command=0x46, data=(uid,))
        if 'error' in response:
            if return_none_on_error:
                return None
            raise Exception(response['error'])
        name = None
        if 'data' in response:
            data = response['data']
            if len(data) == 16:
                # convert int array to string
                n = ''.join(chr(data[i]) for i in range(0, len(data)))
                # remove padded \x00 chars
                n = n.rstrip("\x00")
                if len(n) > 0:
                    name = n
        return name

    def set_user_password(self, uid, mode='set_password', password=None):
        """Set user password and (modes)

        :param uid: id number of user.  see: get_names_uid()['name']

        :param mode:
            disable       = disable user connections
            enable        = enable user connections
            set_password  = set or ensure password
            test_password = test password is correct

        :param password: max 16 char string
            (optional when mode is [disable or enable])

        :return:
            True on success
            when mode = test_password, return False on bad password
        """
        mode_mask = {
            'disable': 0,
            'enable': 1,
            'set_password': 2,
            'test_password': 3
        }
        data = [uid, mode_mask[mode]]
        if password:
            password = str(password)
            if len(password) > 16:
                raise Exception('password has limit of 16 chars')
            password = password.ljust(16, "\x00")
            data.extend([ord(x) for x in password])
        response = self.raw_command(netfn=0x06, command=0x47, data=data)
        if 'error' in response:
            if mode == 'test_password':
                # return false if password test failed
                return False
            raise Exception(response['error'])
        return True

    def get_channel_max_user_count(self, channel=14):
        """Get max users in channel (helper)

        :param channel: number [1:7]
        :return: int -- often 16
        """
        access = self.get_user_access(channel=channel, uid=1)
        return access['channel_info']['max_user_count']

    def get_user(self, uid, channel=14):
        """Get user (helper)

        :param uid: user number [1:16]
        :param channel: number [1:7]

        :return:
            name: (str)
            uid: (int)
            channel: (int)
            access:
                callback (bool)
                link_auth (bool)
                ipmi_msg (bool)
                privilege_level: (str)[callback, user, operatorm administrator,
                                       proprietary, no_access]
        """
        name = self.get_user_name(uid)
        access = self.get_user_access(uid, channel)
        data = {'name': name, 'uid': uid, 'channel': channel,
                'access': access['access']}
        return data

    def get_name_uids(self, name, channel=14):
        """get list of users (helper)

        :param channel: number [1:7]

        :return: list of users
        """
        uid_list = []
        max_ids = self.get_channel_max_user_count(channel)
        for uid in range(1, max_ids):
            if name == self.get_user_name(uid=uid):
                uid_list.append(uid)
        return uid_list

    def get_users(self, channel=14):
        """get list of users and channel access information (helper)

        :param channel: number [1:7]

        :return:
            name: (str)
            uid: (int)
            channel: (int)
            access:
                callback (bool)
                link_auth (bool)
                ipmi_msg (bool)
                privilege_level: (str)[callback, user, operatorm administrator,
                                       proprietary, no_access]
        """
        names = {}
        max_ids = self.get_channel_max_user_count(channel)
        for uid in range(1, max_ids):
            name = self.get_user_name(uid=uid)
            if name is not None:
                names[uid] = self.get_user(uid=uid, channel=channel)
        return names

    def create_user(self, uid, name, password, channel=14, callback=False,
                    link_auth=True, ipmi_msg=True,
                    privilege_level='user'):
        """create/ensure a user is created with provided settings (helper)

        :param privilege_level:
            User Privilege Limit. (Determines the maximum privilege level that
            the user is allowed to switch to on the specified channel.)
            * callback
            * user
            * operator
            * administrator
            * proprietary
            * no_access
        """
        # current user might be trying to update.. dont disable
        # set_user_password(uid, password, mode='disable')
        self.set_user_name(uid, name)
        self.set_user_access(uid, channel, callback=callback,
                             link_auth=link_auth, ipmi_msg=ipmi_msg,
                             privilege_level=privilege_level)
        self.set_user_password(uid, password=password)
        self.set_user_password(uid, mode='enable', password=password)
        return True

    def user_delete(self, uid, channel=14):
        """Delete user (helper)

        :param uid: user number [1:16]
        :param channel: number [1:7]
        """
        self.set_user_password(uid, mode='disable', password=None)
        self.set_user_name(uid, '')
        # TODO(steveweber) perhaps should set user access on all channels
        # so new users dont get extra access
        self.set_user_access(uid, channel=channel, callback=False,
                             link_auth=False, ipmi_msg=False,
                             privilege_level='no_access')
        return True

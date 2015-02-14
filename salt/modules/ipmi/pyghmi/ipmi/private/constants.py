# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 IBM Corporation
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

IPMI_BMC_ADDRESS = 0x20
IPMI_SEND_MESSAGE_CMD = 0x34

import pyghmi.constants as const


payload_types = {
    'ipmi': 0x0,
    'sol': 0x1,
    'rmcpplusopenreq': 0x10,
    'rmcpplusopenresponse': 0x11,
    'rakp1': 0x12,
    'rakp2': 0x13,
    'rakp3': 0x14,
    'rakp4': 0x15,
}

#sensor type codes, table 42-3
sensor_type_codes = {
    1: 'Temperature',
    2: 'Voltage',
    3: 'Current',
    4: 'Fan',
    5: 'Chassis Intrusion',
    6: 'Platform Security',
    7: 'Processor',
    8: 'Power Supply',
    9: 'Power Unit',
    0xa: 'Cooling Device',
    0xb: 'Other',
    0xc: 'Memory',
    0xd: 'Drive Bay',
    0xe: 'POST Memory Resize',
    0xf: 'System Firmware Progress',
    0x10: 'Event Log Disabled',
    0x11: 'Watchdog',
    0x12: 'System Event',
    0x13: 'Critical interrupt',
    0x14: 'Button/switch',
    0x15: 'Module/Board',
    0x16: 'Microcontroller/Coprocessor',
    0x17: 'Add-in Card',
    0x18: 'Chassis',
    0x19: 'Chip Set',
    0x1a: 'Other FRU',
    0x1b: 'Cable/Interconnect',
    0x1c: 'Terminator',
    0x1d: 'System Boot',
    0x1e: 'Boot Error',
    0x1f: 'OS Boot',
    0x20: 'OS Stop',
    0x21: 'Slot/Connector',
    0x22: 'System ACPI Power State',
    0x23: 'Watchdog',
    0x24: 'Platform alert',
    0x25: 'Entity Presence',
    0x26: 'Monitor ASIC/IC',
    0x27: 'LAN',
    0x28: 'Management Subsystem Health',
    0x29: 'Battery',
    0x2a: 'Session Audit',
    0x2b: 'Version Change',
    0x2c: 'FRU State',
}

# This is from table 42-2
#digital discrete poses a challenge from a health perspective.  So far all
#observed ones are no more or less 'healthy' by being asserted or not asserted
#for example asserting that an add-on is installed

discrete_type_offsets = {
    2: {
        0: {
            'desc': 'Idle',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Active',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Busy',
            'severity': const.Health.Ok,
        },
    },
    3: {
        0: {
            'desc': 'Deasserted',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Asserted',
            'severity': const.Health.Ok,
        },
    },
    4: {
        0: {
            'desc': 'Predictive Failure deasserted',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Predictive Failure',
            'severity': const.Health.Warning,
        },
    },
    5: {
        0: {
            'desc': 'Limit Not Exceeded',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Limit Exceeded',
            'severity': const.Health.Warning,
        },
    },
    6: {
        0: {
            'desc': 'Performance Met',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Perfermance Lags',
            'severity': const.Health.Warning,
        },
    },
    7: {
        0: {
            'desc': 'Ok',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Non-Critical',
            'severity': const.Health.Warning,
        },
        2: {
            'desc': 'Critical',
            'severity': const.Health.Critical,
        },
        3: {
            'desc': 'Non-recoverable',
            'severity': const.Health.Failed,
        },
        4: {
            'desc': 'Non-Critical',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'Critical',
            'severity': const.Health.Critical,
        },
        6: {
            'desc': 'Non-recoverable',
            'severity': const.Health.Failed,
        },
        7: {
            'desc': 'Monitor',
            'severity': const.Health.Ok,
        },
        8: {
            'desc': 'Informational',
            'severity': const.Health.Ok,
        },
    },
    8: {
        0: {
            'desc': 'Absent',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Present',
            'severity': const.Health.Ok,
        },
    },
    9: {
        0: {
            'desc': 'Disabled',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Enabled',
            'severity': const.Health.Ok,
        },
    }
}

sensor_type_offsets = {
    # For the security sensors, we assume if armed,
    # the operator considers these to  be critical situations
    5: {
        0: {
            'desc': 'General Chassis Intrusion',
            'severity': const.Health.Critical,
        },
        1: {
            'desc': 'Drive Bay intrusion',
            'severity': const.Health.Critical,
        },
        2: {
            'desc': 'I/O Card area intrusion',
            'severity': const.Health.Critical,
        },
        3: {
            'desc': 'Processor area intrusion',
            'severity': const.Health.Critical,
        },
        4: {
            'desc': 'Lost LAN connection',
            'severity': const.Health.Critical,
        },
        5: {
            'desc': 'Unauthorized dock',
            'severity': const.Health.Critical,
        },
        6: {
            'desc': 'Fan area intrusion',
            'severity': const.Health.Critical,
        },
    },
    6: {
        0: {
            'desc': 'Front Panel Lockout Violation attempt',
            'severity': const.Health.Critical,
        },
        1: {
            'desc': 'Pre-boot password violation - user',
            'severity': const.Health.Critical,
        },
        2: {
            'desc': 'Pre-boot password violation - setup',
            'severity': const.Health.Critical,
        },
        3: {
            'desc': 'Pre-boot password violation - netboot',
            'severity': const.Health.Critical,
        },
        4: {
            'desc': 'Pre-boot password violation',
            'severity': const.Health.Critical,
        },
        5: {
            'desc': 'Out-of-band access password violation',
            'severity': const.Health.Critical,
        },
    },
    7: {
        0: {
            'desc': 'processor IERR',
            'severity': const.Health.Failed,
        },
        1: {
            'desc': 'processor thermal trip',
            'severity': const.Health.Failed,
        },
        2: {
            'desc': 'processor FRB1/BIST failure',
            'severity': const.Health.Failed,
        },
        3: {
            'desc': 'processor FRB2/Hang in POST failure',
            'severity': const.Health.Failed,
        },
        4: {
            'desc': 'processor FRB3/processor startup failure',
            'severity': const.Health.Failed,
        },
        5: {
            'desc': 'processor configuration error',
            'severity': const.Health.Failed,
        },
        6: {
            'desc': 'uncorrectable cpu complex error',
            'severity': const.Health.Failed,
        },
        7: {
            'desc': 'Present',
            'severity': const.Health.Ok,
        },
        8: {
            'desc': 'Disabled',
            'severity': const.Health.Warning,
        },
        9: {
            'desc': 'processor terminator presence detected',
            'severity': const.Health.Ok,
        },
        0xa: {
            'desc': 'processor throttled',
            'severity': const.Health.Warning,
        },
        0xb: {
            'desc': 'uncorrectable machine check exception',
            'severity': const.Health.Failed,
        },
        0xc: {
            'desc': 'correctable machine check exception',
            'severity': const.Health.Warning,
        },
    },
    8: {  # power supply
        0: {
            'desc': 'Present',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'power supply failure',
            'severity': const.Health.Critical,
        },
        2: {
            'desc': 'power supply predictive failure',
            'severity': const.Health.Critical,
        },
        3: {
            'desc': 'power supply input lost',
            'severity': const.Health.Critical,
        },
        4: {
            'desc': 'power supply input out of range or lost',
            'severity': const.Health.Critical,
        },
        5: {
            'desc': 'power supply input out of range',
            'severity': const.Health.Critical,
        },
        6: {
            # clarified by SEL/PET event data 3
            'desc': 'power supply configuration error',
            'severity': const.Health.Warning,
        },
        7: {
            'desc': 'Standby',
            'severity': const.Health.Ok,
        },
    },
    9: {  # power unit
        0: {
            'desc': 'power off/down',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'power cycle',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': '240VA power down',
            'severity': const.Health.Warning,
        },
        3: {
            'desc': 'interlock power down',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'power input lost',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'soft power control failure',
            'severity': const.Health.Failed,
        },
        6: {
            'desc': 'power unit failure',
            'severity': const.Health.Critical,
        },
        7: {
            'desc': 'power unit predictive failure',
            'severity': const.Health.Warning,
        },
    },
    0xc: {  # memory
        0: {
            'desc': 'correctable memory error',
            'severity': const.Health.Warning,
        },
        1: {
            'desc': 'uncorrectable memory error',
            'severity': const.Health.Failed,
        },
        2: {
            'desc': 'memory parity',
            'severity': const.Health.Warning,
        },
        3: {
            'desc': 'memory scrub failed',
            'severity': const.Health.Critical,
        },
        4: {
            'desc': 'memory device disabled',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'correctable memory error logging limit reached',
            'severity': const.Health.Critical,
        },
        6: {
            'desc': 'Present',
            'severity': const.Health.Ok,
        },
        7: {
            'desc': 'memory configuration error',
            'severity': const.Health.Critical,
        },
        8: {
            'desc': 'spare memory',  # event data 3 available
            'severity': const.Health.Ok,
        },
        9: {
            'desc': 'memory throttled',
            'severity': const.Health.Warning,
        },
        0xa: {
            'desc': 'critical memory overtemperature',
            'severity': const.Health.Critical,
        },
    },
    0xd: {  # drive bay
        0: {
            'desc': 'Present',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'drive fault',
            'severity': const.Health.Critical,
        },
        2: {
            'desc': 'predictive drive failure',
            'severity': const.Health.Warning,
        },
        3: {
            'desc': 'hot spare drive',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'drive consitency check in progress',
            'severity': const.Health.Ok,
        },
        5: {
            'desc': 'drive in critical array',
            'severity': const.Health.Critical,
        },
        6: {
            'desc': 'drive in failed array',
            'severity': const.Health.Failed,
        },
        7: {
            'desc': 'rebuild in progress',
            'severity': const.Health.Ok,
        },
        8: {
            'desc': 'rebuild aborted',
            'severity': const.Health.Critical,
        },
    },
    0xf: {
        0: {
            'desc': 'System Firmware boot error',
            'severity': const.Health.Failed,
        },
        1: {
            'desc': 'System Firmware hang',
            'severity': const.Health.Failed,
        },
        2: {
            'desc': 'System Firmware Progress',
            'severity': const.Health.Ok,
        },
    },
    0x10: {  # event log disabled
        0: {
            'desc': 'Correctable Memory Error Logging Disabled',
            'severity': const.Health.Warning,
        },
        1: {
            'desc': 'Specific event logging disabled',
            'severity': const.Health.Warning,
        },
        2: {
            'desc': 'Log Cleared',
            'severity': const.Health.Ok,
        },
        3: {
            'desc': 'Logging Disabled',
            'severity': const.Health.Warning,
        },
        4: {
            'desc': 'Event log full',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'Event log nearly full',
            'severity': const.Health.Warning,
        },
        6: {
            'desc': 'Correctable Machine Check Logging Disabled',
            'severity': const.Health.Warning,
        },
    },
    0x12: {  # system event
        0: {
            'desc': 'System reconfigured',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'OEM boot event',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Undetermined hardware failure',
            'severity': const.Health.Failed,
        },
        3: {
            'desc': 'Aux log entry',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'Event Response',
            'severity': const.Health.Ok,
        },
        5: {
            'desc': 'Clock time change',
            'severity': const.Health.Ok,
        },
    },
    0x13: {  # critical interrupt
        0: {
            'desc': 'Front panel diagnostic interrupt',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Bus Timeout',
            'severity': const.Health.Critical,
        },
        2: {
            'desc': 'I/O NMI',
            'severity': const.Health.Critical,
        },
        3: {
            'desc': 'Software NMI',
            'severity': const.Health.Critical,
        },
        4: {
            'desc': 'PCI PERR',
            'severity': const.Health.Failed,
        },
        5: {
            'desc': 'PCI SERR',
            'severity': const.Health.Failed,
        },
        6: {
            'desc': 'EISA Fail safe timeout',
            'severity': const.Health.Failed,
        },
        7: {
            'desc': 'Bus Correctable Error',
            'severity': const.Health.Warning,
        },
        8: {
            'desc': 'Bus Uncorrectable Error',
            'severity': const.Health.Failed,
        },
        9: {
            'desc': 'Fatal NMI',
            'severity': const.Health.Failed,
        },
        0xa: {
            'desc': 'Bus Fatal Error',
            'severity': const.Health.Failed,
        },
        0xb: {
            'desc': 'Bus Degraded',
            'severity': const.Health.Warning,
        },
    },
    0x14: {  # button/switch
        0: {
            'desc': 'Power button pressed',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Sleep button pressed',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Reset button pressed',
            'severity': const.Health.Ok,
        },
        3: {
            'desc': 'FRU latch open',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'Service requested',
            'severity': const.Health.Warning,
        },
    },
    0x19: {  # chipset
        0: {
            'desc': 'Soft power control failure',
            'severity': const.Health.Critical,
        },
        1: {
            'desc': 'Thermal Trip',
            'severity': const.Health.Failed,
        },
    },
    0x1b: {  # Cable/Interconnect
        0: {
            'desc': 'Connected',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Connection error',
            'severity': const.Health.Critical,
        },
    },
    0x1d: {  # system boot initiated
        0: {
            'desc': 'Power up',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Hard Reset',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Warm Reset',
            'severity': const.Health.Ok,
        },
        3: {
            'desc': 'PXE Boot',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'Autoboot to diagnostic',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'OS hard reset',
            'severity': const.Health.Ok,
        },
        6: {
            'desc': 'OS warm reset',
            'severity': const.Health.Ok,
        },
        7: {
            'desc': 'System restart',
            'severity': const.Health.Ok,
        },
    },
    0x1e: {  # boot error
        0: {
            'desc': 'No bootable media',
            'severity': const.Health.Failed,
        },
        1: {
            'desc': 'Unbootable removable media',
            'severity': const.Health.Failed,
        },
        2: {
            'desc': 'PXE Failure',
            'severity': const.Health.Failed,
        },
        3: {
            'desc': 'Invalid boot sector',
            'severity': const.Health.Failed,
        },
        4: {
            'desc': 'Interactive boot timeout',
            'severity': const.Health.Failed,
        },
    },
    0x1f: {  # OS boot
        0: {
            'desc': 'A: boot completed',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Hard drive boot completed',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Network boot completed',
            'severity': const.Health.Ok,
        },
        3: {
            'desc': 'Diagnostic boot completed',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'CD boot completed',
            'severity': const.Health.Ok,
        },
        5: {
            'desc': 'ROM boot completed',
            'severity': const.Health.Ok,
        },
        6: {
            'desc': 'Boot completed',
            'severity': const.Health.Ok,
        },
        7: {
            'desc': 'OS deployment started',
            'severity': const.Health.Ok,
        },
        8: {
            'desc': 'OS deployment completed',
            'severity': const.Health.Ok,
        },
        9: {
            'desc': 'OS deployment aborted',
            'severity': const.Health.Ok,
        },
        0xa: {
            'desc': 'OS deployment failed',
            'severity': const.Health.Failed,
        },
    },
    0x20: {  # OS Stop
        0: {
            'desc': 'OS boot stop',
            'severity': const.Health.Failed,
        },
        1: {
            'desc': 'OS Crash',
            'severity': const.Health.Failed,
        },
        2: {
            'desc': 'OS Cleanly Halted',
            'severity': const.Health.Ok,
        },
        3: {
            'desc': 'OS Cleanly shutdown',
            'severity': const.Health.Ok,
        },
        4: {
            'desc': 'Event driven soft shutdown',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'Event driven soft shutdown failed',
            'severity': const.Health.Warning,
        },
    },
    0x21:  {  # slot/connector
        0x0: {
            'desc': 'Fault',
            'severity': const.Health.Critical,
        },
        0x1: {
            'desc': 'Identify',
            'severity': const.Health.Ok,
        },
        0x2: {
            'desc': 'Slot/Connector installed',
            'severity': const.Health.Ok,
        },
        0x3: {
            'desc': 'Slot/connector ready for install',
            'severity': const.Health.Ok,
        },
        0x4: {
            'desc': 'Slot/connector ready for removal',
            'severity': const.Health.Ok,
        },
        0x5: {
            'desc': 'Slot powered down',
            'severity': const.Health.Ok,
        },
        0x6: {
            'desc': 'Slot/connector device removal requested',
            'severity': const.Health.Warning,
        },
        0x7: {
            'desc': 'Slot/connector Interlock',
            'severity': const.Health.Ok,
        },
        0x8: {
            'desc': 'Slot/connector disabled',
            'severity': const.Health.Warning,
        },
        0x9: {
            'desc': 'Slot holds spare device',
            'severity': const.Health.Ok,
        },
    },
    0x22: {  # system acpi power state
        0x0: {
            'desc': 'Online',
            'severity': const.Health.Ok,
        },
        0x1: {
            'desc': 'S1 Sleep',
            'severity': const.Health.Ok,
        },
        0x2: {
            'desc': 'S2 Sleep',
            'severity': const.Health.Ok,
        },
        0x3: {
            'desc': 'Sleep',
            'severity': const.Health.Ok,
        },
        0x4: {
            'desc': 'Hibernated',
            'severity': const.Health.Ok,
        },
        0x5: {
            'desc': 'Off',
            'severity': const.Health.Ok,
        },
        0x6: {
            'desc': 'Hibernated or Off',
            'severity': const.Health.Ok,
        },
        0x7: {
            'desc': 'Mechanically Off',
            'severity': const.Health.Ok,
        },
        0x8: {
            'desc': 'Sleep',
            'severity': const.Health.Ok,
        },
        0x9: {
            'desc': 'G1 Sleep',
            'severity': const.Health.Ok,
        },
        0xa: {
            'desc': 'Shutdown',
            'severity': const.Health.Ok,
        },
        0xb: {
            'desc': 'On',
            'severity': const.Health.Ok,
        },
        0xc: {
            'desc': 'Off',
            'severity': const.Health.Ok,
        },
        0xe: {
            'desc': 'Unknown',
            'severity': const.Health.Ok,
        },
    },
    0x23: {  # watchdog
        0x0: {
            'desc': 'Watchdog expired',
            'severity': const.Health.Critical,
        },
        0x1: {
            'desc': 'Watchdog hard reset',
            'severity': const.Health.Failed,
        },
        0x2: {
            'desc': 'Watchdog Power down',
            'severity': const.Health.Failed,
        },
        0x3: {
            'desc': 'Watchdog Power Cycle',
            'severity': const.Health.Failed,
        },
        0x8: {
            'desc': 'Watchdog Interrupt',
            'severity': const.Health.Ok,
        },
    },
    0x24: {  # platform event
        0x0: {
            'desc': 'Platform generated page',
            'severity': const.Health.Ok,
        },
        0x1: {
            'desc': 'Platform generated Network alert',
            'severity': const.Health.Ok,
        },
        0x2: {
            'desc': 'Platform generated Network alert, PET format',
            'severity': const.Health.Ok,
        },
        0x3: {
            'desc': 'Platform generated Network alert, OEM SNMP format',
            'severity': const.Health.Ok,
        },
    },
    0x25: {  # entity presence
        0: {
            'desc': 'Present',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Absent',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Disabled',
            'severity': const.Health.Warning,
        },
    },
    0x27: {  # LAN heartbeat
        0: {
            'desc': 'Heartbeat lost',
            'severity': const.Health.Warning,
        },
        1: {
            'desc': 'Heartbeat',
            'severity': const.Health.Ok,
        },
    },
    0x28: {  # management subsystem health
        0: {
            'desc': 'Sensor access degraded or unavailable',
            'severity': const.Health.Warning,
        },
        1: {
            'desc': 'Controller access degraded or unavailable',
            'severity': const.Health.Warning,
        },
        2: {
            'desc': 'Controller Offline',
            'severity': const.Health.Warning,
        },
        3: {
            'desc': 'Controller Offline',
            'severity': const.Health.Warning,
        },
        4: {
            'desc': 'Sensor Error',
            'severity': const.Health.Warning,
        },
        5: {
            'desc': 'FRU Failure',
            'severity': const.Health.Warning,
        },
    },
    0x29: {  # battery
        0: {
            'desc': 'Battery Low',
            'severity': const.Health.Warning,
        },
        1: {
            'desc': 'Battery Failed',
            # Critical here because typical battery failure
            # does not indicate a 'failed' runtime
            'severity': const.Health.Critical,
        },
        2: {
            'desc': 'Battery Present',
            'severity': const.Health.Ok,
        },
    },
    0x2a: {  # session audit
        0: {
            'desc': 'Session activated',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Session deactivated',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Invalid username or password',
            'severity': const.Health.Warning,
        },
        3: {
            'desc': 'Account disabled due to failure count',
            'severity': const.Health.Critical,
        },
    },
    0x2b: {  # Version Change
        0: {
            'desc': 'Hardware change detected',
            'severity': const.Health.Ok,
        },
        1: {
            'desc': 'Firmware or software change detected',
            'severity': const.Health.Ok,
        },
        2: {
            'desc': 'Hardware incompatibility detected',
            'severity': const.Health.Critical,
        },
        3: {
            'desc': 'Firmware/software incompatibility detected',
            'severity': const.Health.Critical,
        },
        4: {
            'desc': 'Invalid/Unsupported hardware revision',
            'severity': const.Health.Critical,
        },
        5: {
            'desc': 'Invalid/Unsupported firmware/software version',
            'severity': const.Health.Critical,
        },
        6: {
            'desc': 'Successful Hardware Change',
            'severity': const.Health.Ok,
        },
        7: {
            'desc': 'Successful Software/Firmware Change',
            'severity': const.Health.Ok,
        },
    },
}


#entity ids from table 43-13 entity id codes
entity_ids = {
    0x0: 'unspecified',
    0x1: 'other',
    0x2: 'unknown',
    0x3: 'processor',
    0x4: 'disk or disk bay',
    0x5: 'peripheral bay',
    0x6: 'system management module',
    0x7: 'system board',
    0x8: 'memory module',
    0x9: 'processor module',
    0xa: 'power supply',
    0xb: 'add-in card',
    0xc: 'front panel board',
    0xd: 'back panel board',
    0xe: 'power system board',
    0xf: 'drive backplane',
    0x10: 'system internal expansion board',
    0x11: 'other system board',
    0x12: 'processor board',
    0x13: 'power unit / power domain',
    0x14: 'power module / DC-to-DC converter',
    0x15: 'power management /power distribution board',
    0x16: 'chassis back panel board',
    0x17: 'system chassis',
    0x18: 'sub-chassis',
    0x19: 'other chassis board',
    0x1a: 'disk drive bay',
    0x1b: 'peripheral bay',
    0x1c: 'device bay',
    0x1d: 'fan/cooling device',
    0x1e: 'cooling unit / cooling domain',
    0x1f: 'cable / interconnect',
    0x20: 'memory device',
    0x21: 'system management software',
    0x22: 'system firmware',
    0x23: 'operating system',
    0x24: 'system bus',
    0x25: 'group',
    0x26: 'remote management communication device',
    0x27: 'external environment',
    0x28: 'battery',
    0x29: 'processing blade',
    0x2a: 'connectivity switch',
    0x2b: 'processor/memory module',
    0x2c: 'I/O module',
    0x2d: 'Processor I/O module',
    0x2e: 'management controller firmware',
    0x2f: 'IPMI channel',
    0x30: 'PCI Bus',
    0x31: 'PCIe Bus',
    0x32: 'SCSI Bus',
    0x33: 'SATA/SAS Bus',
    0x34: 'processor / front-side bus',
    0x35: 'real time clock',
    0x37: 'air inlet',
    0x40: 'air inlet',
    0x41: 'processor',
    0x42: 'system board',
}


rmcp_codes = {
    1: ("Insufficient resources to create new session (wait for existing "
        "sessions to timeout)"),
    2: "Invalid Session ID",
    3: "Invalid payload type",
    4: "Invalid authentication algorithm",
    5: "Invalid integrity algorithm",
    6: "No matching integrity payload",
    7: "No matching integrity payload",
    8: "Inactive Session ID",
    9: "Invalid role",
    0xa: "Unauthorized role or privilege level requested",
    0xb: "Insufficient resources to create a session at the requested role",
    0xc: "Invalid username length",
    0xd: "Unauthorized name",
    0xe: "Unauthorized GUID",
    0xf: "Invalid integrity check value",
    0x10: "Invalid confidentiality algorithm",
    0x11: "No Cipher suite match with proposed security algorithms",
    0x12: "Illegal or unrecognized parameter",
}

netfn_codes = {
    "chassis": 0x0,
    "bridge": 0x2,
    "sensorevent": 0x4,
    "application": 0x6,
    "firmware": 0x8,
    "storage": 0xa,
    "transport": 0xc,
}

command_completion_codes = {
    (7, 0x39): {
        0x81: "Invalid user name",
        0x82: "Null user disabled",
    },
    (7, 0x3a): {
        0x81: "No available login slots",
        0x82: "No available login slots for requested user",
        0x83: "No slot available with requested privilege level",
        0x84: "Session sequence number out of range",
        0x85: "Invalid session ID",
        0x86: ("Requested privilege level exceeds requested user permissions "
               "on this channel"),
    },
    (7, 0x3b): {  # Set session privilege level
        0x80: "User is not allowed requested privilege level",
        0x81: "Requested privilege level is not allowed over this channel",
        0x82: "Cannot disable user level authentication",
    },
    (1, 8): {  # set system boot options
        0x80: "Parameter not supported",
        0x81: "Attempt to set set 'set in progress' when not 'set complete'",
        0x82: "Attempt to write read-only parameter",
    },
    (7, 0x48): {  # activate payload
        0x80: "Payload already active on another session",
        0x81: "Payload is disabled",
        0x82: "Payload activation limit reached",
        0x83: "Cannot activate payload with encryption",
        0x84: "Cannot activate payload without encryption",
    },
    (6, 0x47): {  # set user password
        0x80: "Password test failed. Password does not match stored value",
        0x81: "Password test failed. Wrong password size was used"
    },
}

ipmi_completion_codes = {
    0x00: "Success",
    0xc0: "Node Busy",
    0xc1: "Invalid command",
    0xc2: "Invalid command for given LUN",
    0xc3: "Timeout while processing command",
    0xc4: "Out of storage space on BMC",
    0xc5: "Reservation canceled or invalid reservation ID",
    0xc6: "Request data truncated",
    0xc7: "Request data length invalid",
    0xc8: "Request data field length limit exceeded",
    0xc9: "Parameter out of range",
    0xca: "Cannot return number of requested data bytes",
    0xcb: "Requested sensor, data, or record not present",
    0xcc: "Invalid data field in request",
    0xcd: "Command illegal for specified sensor or record type",
    0xce: "Command response could not be provided",
    0xcf: "Cannot execute duplicated request",
    0xd0: "SDR repository in update mode",
    0xd1: "Device in firmware update mode",
    0xd2: "BMC initialization in progress",
    0xd3: "Internal destination unavailable",
    0xd4: "Insufficient privilege level or firmware firewall",
    0xd5: "Command not supported in present state",
    0xd6: "Cannot execute command because subfunction disabled or unavailable",
    0xff: "Unspecified",
    0xffff: "Timeout",  # not ipmi, but used internally
}

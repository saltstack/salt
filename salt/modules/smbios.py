# -*- coding: utf-8 -*-
'''
Interface to SMBIOS/DMI

(Parsing through dmidecode)

External References
-------------------
| `Desktop Management Interface (DMI) <http://www.dmtf.org/standards/dmi>`_
| `System Management BIOS <http://www.dmtf.org/standards/smbios>`_
| `DMIdecode <http://www.nongnu.org/dmidecode/>`_

'''
# Import python libs
from __future__ import absolute_import
import logging
import uuid
import re

# Import salt libs
# import salt.log
import salt.utils

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)

DMIDECODER = salt.utils.which_bin(['dmidecode', 'smbios'])


def __virtual__():
    '''
    Only work when dmidecode is installed.
    '''
    if DMIDECODER is None:
        log.debug('SMBIOS: neither dmidecode nor smbios found!')
        return (False, 'The smbios execution module failed to load: neither dmidecode nor smbios in the path.')
    else:
        return True


def get(string, clean=True):
    '''
    Get an individual DMI string from SMBIOS info

    string
        The string to fetch. DMIdecode supports:
          - ``bios-vendor``
          - ``bios-version``
          - ``bios-release-date``
          - ``system-manufacturer``
          - ``system-product-name``
          - ``system-version``
          - ``system-serial-number``
          - ``system-uuid``
          - ``baseboard-manufacturer``
          - ``baseboard-product-name``
          - ``baseboard-version``
          - ``baseboard-serial-number``
          - ``baseboard-asset-tag``
          - ``chassis-manufacturer``
          - ``chassis-type``
          - ``chassis-version``
          - ``chassis-serial-number``
          - ``chassis-asset-tag``
          - ``processor-family``
          - ``processor-manufacturer``
          - ``processor-version``
          - ``processor-frequency``

    clean
      | Don't return well-known false information
      | (invalid UUID's, serial 000000000's, etcetera)
      | Defaults to ``True``

    CLI Example:

    .. code-block:: bash

        salt '*' smbios.get system-uuid clean=False
    '''

    val = _dmidecoder('-s {0}'.format(string)).strip()
    if not clean or _dmi_isclean(string, val):
        return val


def records(rec_type=None, fields=None, clean=True):
    '''
    Return DMI records from SMBIOS

    type
        Return only records of type(s)
        The SMBIOS specification defines the following DMI types:

        ====  ======================================
        Type  Information
        ====  ======================================
         0    BIOS
         1    System
         2    Baseboard
         3    Chassis
         4    Processor
         5    Memory Controller
         6    Memory Module
         7    Cache
         8    Port Connector
         9    System Slots
        10    On Board Devices
        11    OEM Strings
        12    System Configuration Options
        13    BIOS Language
        14    Group Associations
        15    System Event Log
        16    Physical Memory Array
        17    Memory Device
        18    32-bit Memory Error
        19    Memory Array Mapped Address
        20    Memory Device Mapped Address
        21    Built-in Pointing Device
        22    Portable Battery
        23    System Reset
        24    Hardware Security
        25    System Power Controls
        26    Voltage Probe
        27    Cooling Device
        28    Temperature Probe
        29    Electrical Current Probe
        30    Out-of-band Remote Access
        31    Boot Integrity Services
        32    System Boot
        33    64-bit Memory Error
        34    Management Device
        35    Management Device Component
        36    Management Device Threshold Data
        37    Memory Channel
        38    IPMI Device
        39    Power Supply
        40    Additional Information
        41    Onboard Devices Extended Information
        42    Management Controller Host Interface
        ====  ======================================

    clean
      | Don't return well-known false information
      | (invalid UUID's, serial 000000000's, etcetera)
      | Defaults to ``True``

    CLI Example:

    .. code-block:: bash

        salt '*' smbios.records clean=False
        salt '*' smbios.records 14
        salt '*' smbios.records 4 core_count,thread_count,current_speed

    '''
    if rec_type is None:
        smbios = _dmi_parse(_dmidecoder(), clean, fields)
    else:
        smbios = _dmi_parse(_dmidecoder('-t {0}'.format(rec_type)), clean, fields)

    return smbios


def _dmi_parse(data, clean=True, fields=None):
    '''
    Structurize DMI records into a nice list
    Optionally trash bogus entries and filter output
    '''
    dmi = []

    # Detect & split Handle records
    dmi_split = re.compile('(handle [0-9]x[0-9a-f]+[^\n]+)\n', re.MULTILINE+re.IGNORECASE)
    dmi_raw = iter(re.split(dmi_split, data)[1:])
    for handle, dmi_raw in zip(dmi_raw, dmi_raw):
        handle, htype = [hline.split()[-1] for hline in handle.split(',')][0:2]
        dmi_raw = dmi_raw.split('\n')
        # log.debug('{0} record contains {1}'.format(handle, dmi_raw))
        log.debug('Parsing handle {0}'.format(handle))

        # The first line of a handle is a description of the type
        record = {
            'handle':      handle,
            'description': dmi_raw.pop(0).strip(),
            'type':        int(htype)
        }

        if not len(dmi_raw):
            # empty record
            if not clean:
                dmi.append(record)
            continue

        # log.debug('{0} record contains {1}'.format(record, dmi_raw))
        dmi_data = _dmi_data(dmi_raw, clean, fields)
        if len(dmi_data):
            record['data'] = dmi_data
            dmi.append(record)
        elif not clean:
            dmi.append(record)

    return dmi


def _dmi_data(dmi_raw, clean, fields):
    '''
    Parse the raw DMIdecode output of a single handle
    into a nice dict
    '''
    dmi_data = {}

    key = None
    key_data = [None, []]
    for line in dmi_raw:
        if re.match(r'\t[^\s]+', line):
            # Finish previous key
            if key is not None:
                # log.debug('Evaluating DMI key {0}: {1}'.format(key, key_data))
                value, vlist = key_data
                if len(vlist):
                    if value is not None:
                        # On the rare occasion
                        # (I counted 1 on all systems we have)
                        # that there's both a value <and> a list
                        # just insert the value on top of the list
                        vlist.insert(0, value)
                    dmi_data[key] = vlist
                elif value is not None:
                    dmi_data[key] = value

            # Family: Core i5
            # Keyboard Password Status: Not Implemented
            key, val = line.split(':', 1)
            key = key.strip().lower().replace(' ', '_')
            if (clean and key == 'header_and_data') \
                    or (fields and key not in fields):
                key = None
                continue
            else:
                key_data = [_dmi_cast(key, val.strip(), clean), []]
        elif key is None:
            continue
        elif re.match(r'\t\t[^\s]+', line):
            # Installable Languages: 1
            #        en-US
            # Characteristics:
            #        PCI is supported
            #        PNP is supported
            val = _dmi_cast(key, line.strip(), clean)
            if val is not None:
                # log.debug('DMI key {0} gained list item {1}'.format(key, val))
                key_data[1].append(val)

    return dmi_data


def _dmi_cast(key, val, clean=True):
    '''
    Simple caster thingy for trying to fish out at least ints & lists from strings
    '''
    if clean and not _dmi_isclean(key, val):
        return
    elif not re.match(r'serial|part|asset|product', key, flags=re.IGNORECASE):
        if ',' in val:
            val = [el.strip() for el in val.split(',')]
        else:
            try:
                val = int(val)
            # pylint: disable=bare-except
            except:
                pass

    return val


def _dmi_isclean(key, val):
    '''
    Clean out well-known bogus values
    '''
    if val is None or not len(val) or re.match('none', val, flags=re.IGNORECASE):
        # log.debug('DMI {0} value {1} seems invalid or empty'.format(key, val))
        return False
    elif 'uuid' in key:
        # Try each version (1-5) of RFC4122 to check if it's actually a UUID
        for uuidver in range(1, 5):
            try:
                uuid.UUID(val, version=uuidver)
                return True
            except ValueError:
                continue
        log.trace('DMI {0} value {1} is an invalid UUID'.format(key, val.replace('\n', ' ')))
        return False
    elif re.search('serial|part|version', key):
        # 'To be filled by O.E.M.
        # 'Not applicable' etc.
        # 'Not specified' etc.
        # 0000000, 1234667 etc.
        # begone!
        return not re.match(r'^[0]+$', val) \
                and not re.match(r'[0]?1234567[8]?[9]?[0]?', val) \
                and not re.search(r'sernum|part[_-]?number|specified|filled|applicable', val, flags=re.IGNORECASE)
    elif re.search('asset|manufacturer', key):
        # AssetTag0. Manufacturer04. Begone.
        return not re.search(r'manufacturer|to be filled|available|asset|^no(ne|t)', val, flags=re.IGNORECASE)
    else:
        # map unspecified, undefined, unknown & whatever to None
        return not re.search(r'to be filled', val, flags=re.IGNORECASE) \
            and not re.search(r'un(known|specified)|no(t|ne)? (asset|provided|defined|available|present|specified)',
                              val, flags=re.IGNORECASE)


def _dmidecoder(args=None):
    '''
    Call DMIdecode
    '''
    if args is None:
        return salt.modules.cmdmod._run_quiet(DMIDECODER)
    else:
        return salt.modules.cmdmod._run_quiet('{0} {1}'.format(DMIDECODER, args))

# -*- coding: utf-8 -*-
'''
This module allows you to manage windows licensing via slmgr.vbs

.. code-block:: bash

    salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
'''

# Import Python Libs
from __future__ import absolute_import
import re
import logging
import os.path

# Import Salt Libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'license'


def __virtual__():
    '''
    Only work on Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def installed(product_key):
    '''
    Check to see if the product key is already installed.

    Note: This is not 100% accurate as we can only see the last
     5 digits of the license.

    CLI Example:

    .. code-block:: bash

        salt '*' license.installed XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /dli'
    out = __salt__['cmd.run'](cmd)
    return product_key[-5:] in out


def install(product_key):
    '''
    Install the given product key.

    CLI Example:

    .. code-block:: bash

        salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /ipk {0}'.format(product_key)
    return __salt__['cmd.run'](cmd)


def manual_kms_host(host=None, port='1688'):
    '''
    Manually set client to use specific KMS host and/or port.

    IPv4 ONLY

    CLI Example:

    .. code-block: bash

        salt '*' license.install_kms host=192.168.1.1
        salt '*' license.install_kms host=192.168.1.1 port=1688
        salt '*' license.install_kms host=FQDN port=1688
    '''

    set_kms_host_cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /skms {0}:{1}'.format(host, port)
    return __salt__['cmd.run'](set_kms_host_cmd)


def manual_kms_key():
    '''
    Installs the appropriate KMS key based on the OS version.

    Keys were obtained from https://technet.microsoft.com/en-us/library/jj612867(v=ws.11).aspx
    These KMS keys are public information and not bound to any single organization.

    Does not include Windows Vista or Server 2008. Only Windows 7 and 2008R2 and newer

    This is used when converting a Retail or MAK licensed system to KMS.

    CLI Example:

    .. code-block: bash

        salt '*' license.manual_kms_key
    '''

    os_version = __salt__['grains.get']('osfullname')

    if os_version == 'Microsoft Windows 10 Professional':
        kms_client_key = 'W269N-WFGWX-YVC9B-4J6C9-T83GX'

    if os_version == 'Microsoft Windows 10 Professional N':
        kms_client_key = 'MH37W-N47XK-V7XM9-C7227-GCQG9'

    if os_version == 'Microsoft Windows 10 Enterprise':
        kms_client_key = 'NPPR9-FWDCX-D2C8J-H872K-2YT43'

    if os_version == 'Microsoft Windows 10 Enterprise N':
        kms_client_key = 'DPH2V-TTNVB-4X9Q3-TJR4H-KHJW4'

    if os_version == 'Microsoft Windows 10 Education':
        kms_client_key = 'NW6C2-QMPVW-D7KKK-3GKT6-VCFB2'

    if os_version == 'Microsoft Windows 10 Education N':
        kms_client_key = '2WH4N-8QGBV-H22JP-CT43Q-MDWWJ'

    if os_version == 'Microsoft Windows 10 Enterprise 2015 LTSB':
        kms_client_key = 'WNMTR-4C88C-JK8YV-HQ7T2-76DF9'

    if os_version == 'Microsoft Windows 10 Enterprise 2015 LTSB N':
        kms_client_key = '2F77B-TNFGY-69QQF-B8YKP-D69TJ'

    if os_version == 'Microsoft Windows 10 Enterprise 2016 LTSB':
        kms_client_key = 'DCPHK-NFMTC-H88MJ-PFHPY-QJ4BJ'

    if os_version == 'Microsoft Windows 10 Enterprise 2016 LTSB N':
        kms_client_key = 'QFFDN-GRT3P-VKWWX-X7T3R-8B639'

    if os_version == 'Microsoft Windows 7 Professional':
        kms_client_key = 'FJ82H-XT6CR-J8D7P-XQJJ2-GPDD4'

    if os_version == 'Microsoft Windows 7 Enterprise':
        kms_client_key = '33PXH-7Y6KF-2VJC9-XBBR8-HVTHH'

    if os_version == 'Microsoft Windows 7 Professional N':
        kms_client_key = 'MRPKT-YTG23-K7D7T-X2JMM-QY7MG'

    if os_version == 'Microsoft Windows 7 Professional E':
        kms_client_key = 'W82YF-2Q76Y-63HXB-FGJG9-GF7QX'

    if os_version == 'Microsoft Windows 7 Enterprise N':
        kms_client_key = 'YDRBP-3D83W-TY26F-D46B2-XCKRJ'

    if os_version == 'Microsoft Windows 7 Enterprise E':
        kms_client_key = 'C29WB-22CC8-VJ326-GHFJW-H9DH4'

    if os_version == 'Microsoft Windows Server 2008 R2 Web':
        kms_client_key = '6TPJF-RBVHG-WBW2R-86QPH-6RTM4'

    if os_version == 'Microsoft Windows Server 2008 R2 HPC edition':
        kms_client_key = 'TT8MH-CG224-D3D7Q-498W2-9QCTX'

    if os_version == 'Microsoft Windows Server 2008 R2 Standard':
        kms_client_key = 'YC6KT-GKW9T-YTKYR-T4X34-R7VHC'

    if os_version == 'Microsoft Windows Server 2008 R2 Enterprise':
        kms_client_key = '489J6-VHDMP-X63PK-3K798-CPX3Y'

    if os_version == 'Microsoft Windows Server 2008 R2 Datacenter':
        kms_client_key = '74YFP-3QFB3-KQT8W-PMXWJ-7M648'

    if os_version == 'Microsoft Windows Server 2008 R2 for Itanium-based Systems':
        kms_client_key = 'GT63C-RJFQ3-4GMB6-BRFB9-CB83V'

    if os_version == 'Microsoft Windows 8 Professional':
        kms_client_key = 'NG4HW-VH26C-733KW-K6F98-J8CK4'

    if os_version == 'Microsoft Windows 8 Professional N':
        kms_client_key = 'XCVCF-2NXM9-723PB-MHCB7-2RYQQ'

    if os_version == 'Microsoft Windows 8 Enterprise':
        kms_client_key = '32JNW-9KQ84-P47T8-D8GGY-CWCK7'

    if os_version == 'Microsoft Windows 8 Enterprise N':
        kms_client_key = 'JMNMF-RHW7P-DMY6X-RF3DR-X2BQT'

    if os_version == 'Microsoft Windows Server 2012':
        kms_client_key = 'BN3D2-R7TKB-3YPBD-8DRP2-27GG4'

    if os_version == 'Microsoft Windows Server 2012 N':
        kms_client_key = '8N2M2-HWPGY-7PGT9-HGDD8-GVGGY'

    if os_version == 'Microsoft Windows Server 2012 Single Language':
        kms_client_key = '2WN2H-YGCQR-KFX6K-CD6TF-84YXQ'

    if os_version == 'Microsoft Windows Server 2012 Country Specific':
        kms_client_key = '4K36P-JN4VD-GDC6V-KDT89-DYFKP'

    if os_version == 'Microsoft Windows Server 2012 Server Standard':
        kms_client_key = 'XC9B7-NBPP2-83J2H-RHMBY-92BT4'

    if os_version == 'Microsoft Windows Server 2012 MultiPoint Standard':
        kms_client_key = 'HM7DN-YVMH3-46JC3-XYTG7-CYQJJ'

    if os_version == 'Microsoft Windows Server 2012 MultiPoint Premium':
        kms_client_key = 'XNH6W-2V9GX-RGJ4K-Y8X6F-QGJ2G'

    if os_version == 'Microsoft Windows Server 2012 Datacenter':
        kms_client_key = '48HP8-DN98B-MYWDG-T2DCC-8W83P'

    if os_version == 'Microsoft Windows 8.1 Professional':
        kms_client_key = 'GCRJD-8NW9H-F2CDX-CCM8D-9D6T9'

    if os_version == 'Microsoft Windows 8.1 Professional N':
        kms_client_key = 'HMCNV-VVBFX-7HMBH-CTY9B-B4FXY'

    if os_version == 'Microsoft Windows 8.1 Enterprise':
        kms_client_key = 'MHF9N-XY6XB-WVXMC-BTDCT-MKKG7'

    if os_version == 'Microsoft Windows 8.1 Enterprise N':
        kms_client_key = 'TT4HM-HN7YT-62K67-RGRQJ-JFFXW'

    if os_version == 'Microsoft Windows Server 2012 R2 Server Standard':
        kms_client_key = 'D2N9P-3P6X9-2R39C-7RTCD-MDVJX'

    if os_version == 'Microsoft Windows Server 2012 R2 Datacenter':
        kms_client_key = 'W3GGN-FT8W3-Y4M27-J84CP-Q3VJ9'

    if os_version == 'Microsoft Windows Server 2012 R2 Essentials':
        kms_client_key = 'KNC87-3J2TX-XB4WP-VCPJV-M4FWM'

    if os_version == 'Microsoft Windows Server 2016 Datacenter':
        kms_client_key = 'CB7KF-BWN84-R7R2Y-793K2-8XDDG'

    if os_version == 'Microsoft Windows Server 2016 Standard':
        kms_client_key = 'WC2BQ-8NRM3-FDDYY-2BFGV-KHKQY'

    if os_version == 'Microsoft Windows Server 2016 Essentials':
        kms_client_key = 'JCKRF-N37P4-C2D82-9YXRT-4M63B'

    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /ipk ' + kms_client_key
    return __salt__['cmd.run'](cmd)


def uninstall():
    '''
    Uninstall the current product key.
    Note that the key is still saved in the registry. (See uninstall_reg)

    CLI Example:

    .. code-block:: bash

        salt '*' license.uninstall
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /upk'
    return __salt__['cmd.run'](cmd)


def uninstall_reg():
    '''
    Remove product key from the registry.

    CLI Example:

    .. code-block:: bash

        salt '*' license.uninstall_reg
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /cpky'
    return __salt__['cmd.run'](cmd)


def rearm():
    '''
    Rearm grace period.

    CLI Example:

    .. code-block:: bash

        salt '*' license.rearm
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /rearm'
    return __salt__['cmd.run'](cmd)


def activate():
    '''
    Attempt to activate the current machine via Windows Online Activation.

    CLI Example:

    .. code-block:: bash

        salt '*' license.activate
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /ato'
    return __salt__['cmd.run'](cmd)


def licensed():
    '''
    Return true if the current machine is licensed correctly.

    CLI Example:

    .. code-block:: bash

        salt '*' license.licensed
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /dli'
    out = __salt__['cmd.run'](cmd)
    return 'License Status: Licensed' in out


def type():
    '''
    Returns the type of license configured. (OEM, MAK, KMS, etc.)

    CLI Example:

    .. code-block: bash

        salt '*' license.type

    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /dli'
    out = __salt__['cmd.run'](cmd)

    match = re.search(r'Description: (.*)\r\n', out,
                      re.MULTILINE)

    if match is not None:
        groups = match.groups()
        return {
            'Key Type': groups[0].split()[-2]

        }

    return None


def info():
    '''
    Return information about the license, if the license is not
    correctly activated this will return None.

    CLI Example:

    .. code-block:: bash

        salt '*' license.info
    '''
    cmd = r'cscript ' + os.path.expandvars("%systemroot%") + '\System32\slmgr.vbs /dli'
    out = __salt__['cmd.run'](cmd)

    match = re.search(r'Name: (.*)\r\nDescription: (.*)\r\nPartial Product Key: (.*)\r\nLicense Status: (.*)', out,
                      re.MULTILINE)

    if match is not None:
        groups = match.groups()
        return {
            'name': groups[0],
            'description': groups[1],
            'partial_key': groups[2],
            'licensed': 'Licensed' in groups[3]
        }

    return None

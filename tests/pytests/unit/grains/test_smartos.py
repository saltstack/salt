"""
    :codeauthor: :email:`Jorge Schrauwen <sjorge@blackdot.be>`
"""

import textwrap

import salt.grains.smartos as smartos
from tests.support.mock import MagicMock, Mock, mock_open, patch


def test_smartos_computenode_data():
    """
    Get a tally of running/stopped zones
    Output used form a test host with one running
    and one stopped of each vm type.
    """
    grains_exp_res = {
        "computenode_sdc_version": "7.0",
        "computenode_vm_capable": True,
        "computenode_vm_hw_virt": "vmx",
        "computenode_vms_running": 3,
        "computenode_vms_stopped": 3,
        "computenode_vms_total": 6,
        "computenode_vms_type": {"KVM": 2, "LX": 2, "OS": 2},
        "manufacturer": "Supermicro",
        "productname": "X8STi",
        "uuid": "534d4349-0002-2790-2500-2790250054c5",
    }

    cmd_mock = Mock(
        side_effect=[
            textwrap.dedent(
                """\
            99e40ee7-a8f9-4b57-9225-e7bd19f64b07:test_hvm1:running:BHYV
            cde351a9-e23d-6856-e268-fff10fe603dc:test_hvm2:stopped:BHYV
            99e40ee7-a8f9-4b57-9225-e7bd19f64b07:test_hvm3:running:KVM
            cde351a9-e23d-6856-e268-fff10fe603dc:test_hvm4:stopped:KVM
            179b50ca-8a4d-4f28-bb08-54b2cd350aa5:test_zone1:running:OS
            42846fbc-c48a-6390-fd85-d7ac6a76464c:test_zone2:stopped:OS
            4fd2d7a4-38c4-4068-a2c8-74124364a109:test_zone3:running:LX
            717abe34-e7b9-4387-820e-0bb041173563:test_zone4:stopped:LX"""
            ),
            textwrap.dedent(
                """\
            {
                "Live Image": "20181011T004530Z",
                "System Type": "SunOS",
                "Boot Time": "1562528522",
                "SDC Version": "7.0",
                "Manufacturer": "Supermicro",
                "Product": "X8STi",
                "Serial Number": "1234567890",
                "SKU Number": "To Be Filled By O.E.M.",
                "HW Version": "1234567890",
                "HW Family": "High-End Desktop",
                "Setup": "false",
                "VM Capable": true,
                "Bhyve Capable": false,
                "Bhyve Max Vcpus": 0,
                "HVM API": false,
                "CPU Type": "Intel(R) Xeon(R) CPU W3520 @ 2.67GHz",
                "CPU Virtualization": "vmx",
                "CPU Physical Cores": 1,
                "Admin NIC Tag": "",
                "UUID": "534d4349-0002-2790-2500-2790250054c5",
                "Hostname": "sdc",
                "CPU Total Cores": 8,
                "MiB of Memory": "16375",
                "Zpool": "zones",
                "Zpool Disks": "c1t0d0,c1t1d0",
                "Zpool Profile": "mirror",
                "Zpool Creation": 1406392163,
                "Zpool Size in GiB": 1797,
                "Disks": {
                "c1t0d0": {"Size in GB": 2000},
                "c1t1d0": {"Size in GB": 2000}
                },
                "Boot Parameters": {
                "smartos": "true",
                "console": "text",
                "boot_args": "",
                "bootargs": ""
                },
                "Network Interfaces": {
                "e1000g0": {"MAC Address": "00:00:00:00:00:01", "ip4addr": "123.123.123.123", "Link Status": "up", "NIC Names": ["admin"]},
                "e1000g1": {"MAC Address": "00:00:00:00:00:05", "ip4addr": "", "Link Status": "down", "NIC Names": []}
                },
                "Virtual Network Interfaces": {
                },
                "Link Aggregations": {
                }
            }"""
            ),
        ]
    )
    with patch.dict(smartos.__salt__, {"cmd.run": cmd_mock}):
        grains_res = smartos._smartos_computenode_data()
        assert grains_exp_res == grains_res


def test_smartos_zone_data():
    """
    Get basic information about a non-global zone
    """
    grains_exp_res = {
        "imageversion": "pkgbuild 18.1.0",
        "zoneid": "5",
        "zonename": "dda70f61-70fe-65e7-cf70-d878d69442d4",
    }

    cmd_mock = Mock(
        side_effect=[
            "5:dda70f61-70fe-65e7-cf70-d878d69442d4:running:/:dda70f61-70fe-65e7-cf70-d878d69442d4:native:excl:0",
        ]
    )
    fopen_mock = mock_open(
        read_data={
            "/etc/product": textwrap.dedent(
                """\
            Name: Joyent Instance
            Image: pkgbuild 18.1.0
            Documentation: https://docs.joyent.com/images/smartos/pkgbuild
            """
            ),
        }
    )
    with patch.dict(smartos.__salt__, {"cmd.run": cmd_mock}), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ), patch("salt.utils.files.fopen", fopen_mock):
        grains_res = smartos._smartos_zone_data()
        assert grains_exp_res == grains_res


def test_smartos_zone_pkgsrc_data_in_zone():
    """
    Get pkgsrc information from a zone
    """
    grains_exp_res = {
        "pkgsrcpath": ("https://pkgsrc.joyent.com/packages/SmartOS/2018Q1/x86_64/All"),
        "pkgsrcversion": "2018Q1",
    }

    isfile_mock = Mock(side_effect=[True, False])
    fopen_mock = mock_open(
        read_data={
            "/opt/local/etc/pkg_install.conf": textwrap.dedent(
                """\
            GPG_KEYRING_VERIFY=/opt/local/etc/gnupg/pkgsrc.gpg
            GPG_KEYRING_PKGVULN=/opt/local/share/gnupg/pkgsrc-security.gpg
            PKG_PATH=https://pkgsrc.joyent.com/packages/SmartOS/2018Q1/x86_64/All
            """
            ),
        }
    )

    with patch("os.path.isfile", isfile_mock), patch(
        "salt.utils.files.fopen", fopen_mock
    ):
        grains_res = smartos._smartos_zone_pkgsrc_data()
        assert grains_exp_res == grains_res


def test_smartos_zone_pkgsrc_data_in_globalzone():
    """
    Get pkgsrc information from the globalzone
    """
    grains_exp_res = {
        "pkgsrcpath": "https://pkgsrc.joyent.com/packages/SmartOS/trunk/tools/All",
        "pkgsrcversion": "trunk",
    }

    isfile_mock = Mock(side_effect=[False, True])
    fopen_mock = mock_open(
        read_data={
            "/opt/tools/etc/pkg_install.conf": textwrap.dedent(
                """\
            GPG_KEYRING_PKGVULN=/opt/tools/share/gnupg/pkgsrc-security.gpg
            GPG_KEYRING_VERIFY=/opt/tools/etc/gnupg/pkgsrc.gpg
            PKG_PATH=https://pkgsrc.joyent.com/packages/SmartOS/trunk/tools/All
            VERIFIED_INSTALLATION=always
            """
            ),
        }
    )

    with patch("os.path.isfile", isfile_mock), patch(
        "salt.utils.files.fopen", fopen_mock
    ):
        grains_res = smartos._smartos_zone_pkgsrc_data()
        assert grains_exp_res == grains_res


def test_smartos_zone_pkgin_data_in_zone():
    """
    Get pkgin information from a zone
    """
    grains_exp_res = {
        "pkgin_repositories": [
            "https://pkgsrc.joyent.com/packages/SmartOS/2018Q1/x86_64/All",
            "http://pkg.blackdot.be/packages/2018Q1/x86_64/All",
        ],
    }

    isfile_mock = Mock(side_effect=[True, False])
    fopen_mock = mock_open(
        read_data={
            "/opt/local/etc/pkgin/repositories.conf": textwrap.dedent(
                """\
            # $Id: repositories.conf,v 1.3 2012/06/13 13:50:17 imilh Exp $
            #
            # Pkgin repositories list
            #
            # Simply add repositories URIs one below the other
            #
            # WARNING: order matters, duplicates will not be added, if two
            # repositories hold the same package, it will be fetched from
            # the first one listed in this file.
            #
            # This file format supports the following macros:
            # $arch to define the machine hardware platform
            # $osrelease to define the release version for the operating system
            #
            # Remote ftp repository
            #
            # ftp://ftp.netbsd.org/pub/pkgsrc/packages/NetBSD/$arch/5.1/All
            #
            # Remote http repository
            #
            # http://mirror-master.dragonflybsd.org/packages/$arch/DragonFly-$osrelease/stable/All
            #
            # Local repository (must contain a pkg_summary.gz or bz2)
            #
            # file:///usr/pkgsrc/packages/All
            #
            https://pkgsrc.joyent.com/packages/SmartOS/2018Q1/x86_64/All
            http://pkg.blackdot.be/packages/2018Q1/x86_64/All
            """
            ),
        }
    )

    with patch("os.path.isfile", isfile_mock), patch(
        "salt.utils.files.fopen", fopen_mock
    ):
        grains_res = smartos._smartos_zone_pkgin_data()
        assert grains_exp_res == grains_res


def test_smartos_zone_pkgin_data_in_globalzone():
    """
    Get pkgin information from the globalzone
    """
    grains_exp_res = {
        "pkgin_repositories": [
            "https://pkgsrc.joyent.com/packages/SmartOS/trunk/tools/All",
        ],
    }

    isfile_mock = Mock(side_effect=[False, True])
    fopen_mock = mock_open(
        read_data={
            "/opt/tools/etc/pkgin/repositories.conf": textwrap.dedent(
                """\
            #
            # Pkgin repositories list
            #
            # Simply add repositories URIs one below the other
            #
            # WARNING: order matters, duplicates will not be added, if two
            # repositories hold the same package, it will be fetched from
            # the first one listed in this file.
            #
            # This file format supports the following macros:
            # $arch to define the machine hardware platform
            # $osrelease to define the release version for the operating system
            #
            # Remote ftp repository
            #
            # ftp://ftp.netbsd.org/pub/pkgsrc/packages/NetBSD/$arch/5.1/All
            #
            # Remote http repository
            #
            # http://mirror-master.dragonflybsd.org/packages/$arch/DragonFly-$osrelease/stable/All
            #
            # Local repository (must contain a pkg_summary.gz or bz2)
            #
            # file:///usr/pkgsrc/packages/All
            #
            https://pkgsrc.joyent.com/packages/SmartOS/trunk/tools/All
            """
            ),
        }
    )

    with patch("os.path.isfile", isfile_mock), patch(
        "salt.utils.files.fopen", fopen_mock
    ):
        grains_res = smartos._smartos_zone_pkgin_data()
        assert grains_exp_res == grains_res

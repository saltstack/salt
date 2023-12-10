import os.path

import pytest

import salt.modules.virt as virt
from tests.support.mock import MagicMock, patch

from .conftest import loader_modules_config


@pytest.fixture
def configure_loader_modules():
    return loader_modules_config()


def test_node_devices(make_mock_device):
    """
    Test the virt.node_devices() function
    """
    mock_devs = [
        make_mock_device(
            """
            <device>
              <name>pci_1002_71c4</name>
              <parent>pci_8086_27a1</parent>
              <capability type='pci'>
                <class>0xffffff</class>
                <domain>0</domain>
                <bus>1</bus>
                <slot>0</slot>
                <function>0</function>
                <product id='0x71c4'>M56GL [Mobility FireGL V5200]</product>
                <vendor id='0x1002'>ATI Technologies Inc</vendor>
                <numa node='1'/>
              </capability>
            </device>
        """
        ),
        # Linux USB hub to be ignored
        make_mock_device(
            """
            <device>
              <name>usb_device_1d6b_1_0000_00_1d_0</name>
              <parent>pci_8086_27c8</parent>
              <capability type='usb_device'>
                <bus>2</bus>
                <device>1</device>
                <product id='0x0001'>1.1 root hub</product>
                <vendor id='0x1d6b'>Linux Foundation</vendor>
              </capability>
            </device>
        """
        ),
        # SR-IOV PCI device with multiple capabilities
        make_mock_device(
            """
            <device>
              <name>pci_0000_02_10_7</name>
              <parent>pci_0000_00_04_0</parent>
              <capability type='pci'>
                <domain>0</domain>
                <bus>2</bus>
                <slot>16</slot>
                <function>7</function>
                <product id='0x10ca'>82576 Virtual Function</product>
                <vendor id='0x8086'>Intel Corporation</vendor>
                <capability type='phys_function'>
                  <address domain='0x0000' bus='0x02' slot='0x00' function='0x1'/>
                </capability>
                <capability type='virt_functions' maxCount='7'>
                  <address domain='0x0000' bus='0x02' slot='0x00' function='0x2'/>
                  <address domain='0x0000' bus='0x02' slot='0x00' function='0x3'/>
                  <address domain='0x0000' bus='0x02' slot='0x00' function='0x4'/>
                  <address domain='0x0000' bus='0x02' slot='0x00' function='0x5'/>
                </capability>
                <iommuGroup number='31'>
                  <address domain='0x0000' bus='0x02' slot='0x10' function='0x7'/>
                </iommuGroup>
                <numa node='0'/>
                <pci-express>
                  <link validity='cap' port='0' speed='2.5' width='4'/>
                  <link validity='sta' width='0'/>
                </pci-express>
              </capability>
            </device>
        """
        ),
        # PCI bridge to be ignored
        make_mock_device(
            """
            <device>
              <name>pci_0000_00_1c_0</name>
              <parent>computer</parent>
              <capability type='pci'>
                <class>0xffffff</class>
                <domain>0</domain>
                <bus>0</bus>
                <slot>28</slot>
                <function>0</function>
                <product id='0x8c10'>8 Series/C220 Series Chipset Family PCI Express Root Port #1</product>
                <vendor id='0x8086'>Intel Corporation</vendor>
                <capability type='pci-bridge'/>
                <iommuGroup number='8'>
                  <address domain='0x0000' bus='0x00' slot='0x1c' function='0x0'/>
                </iommuGroup>
                <pci-express>
                  <link validity='cap' port='1' speed='5' width='1'/>
                  <link validity='sta' speed='2.5' width='1'/>
                </pci-express>
              </capability>
            </device>
        """
        ),
        # Other device to be ignored
        make_mock_device(
            """
            <device>
              <name>mdev_3627463d_b7f0_4fea_b468_f1da537d301b</name>
              <parent>computer</parent>
              <capability type='mdev'>
                <type id='mtty-1'/>
                <iommuGroup number='12'/>
              </capability>
            </device>
        """
        ),
        # USB device to be listed
        make_mock_device(
            """
            <device>
              <name>usb_3_1_3</name>
              <path>/sys/devices/pci0000:00/0000:00:1d.6/0000:06:00.0/0000:07:02.0/0000:3e:00.0/usb3/3-1/3-1.3</path>
              <devnode type='dev'>/dev/bus/usb/003/004</devnode>
              <parent>usb_3_1</parent>
              <driver>
                <name>usb</name>
              </driver>
              <capability type='usb_device'>
                <bus>3</bus>
                <device>4</device>
                <product id='0x6006'>AUKEY PC-LM1E Camera</product>
                <vendor id='0x0458'>KYE Systems Corp. (Mouse Systems)</vendor>
              </capability>
            </device>
        """
        ),
        # Network device to be listed
        make_mock_device(
            """
            <device>
              <name>net_eth8_e6_86_48_46_c5_29</name>
              <path>/sys/devices/pci0000:3a/0000:3a:00.0/0000:3b:00.0/0000:3c:03.0/0000:3d:02.2/net/eth8</path>
              <parent>pci_0000_02_10_7</parent>
              <capability type='net'>
                <interface>eth8</interface>
                <address>e6:86:48:46:c5:29</address>
                <link state='down'/>
              </capability>
            </device>
            """
        ),
        # Network device to be ignored
        make_mock_device(
            """
            <device>
              <name>net_lo_00_00_00_00_00_00</name>
              <path>/sys/devices/virtual/net/lo</path>
              <parent>computer</parent>
              <capability type='net'>
                <interface>lo</interface>
                <address>00:00:00:00:00:00</address>
                <link state='unknown'/>
              </capability>
            </device>
            """
        ),
    ]
    virt.libvirt.openAuth().listAllDevices.return_value = mock_devs

    assert virt.node_devices() == [
        {
            "name": "pci_1002_71c4",
            "caps": "pci",
            "vendor_id": "0x1002",
            "vendor": "ATI Technologies Inc",
            "product_id": "0x71c4",
            "product": "M56GL [Mobility FireGL V5200]",
            "address": "0000:01:00.0",
            "PCI class": "0xffffff",
        },
        {
            "name": "pci_0000_02_10_7",
            "caps": "pci",
            "vendor_id": "0x8086",
            "vendor": "Intel Corporation",
            "product_id": "0x10ca",
            "product": "82576 Virtual Function",
            "address": "0000:02:10.7",
            "physical function": "0000:02:00.1",
            "virtual functions": [
                "0000:02:00.2",
                "0000:02:00.3",
                "0000:02:00.4",
                "0000:02:00.5",
            ],
        },
        {
            "name": "usb_3_1_3",
            "caps": "usb_device",
            "vendor": "KYE Systems Corp. (Mouse Systems)",
            "vendor_id": "0x0458",
            "product": "AUKEY PC-LM1E Camera",
            "product_id": "0x6006",
            "address": "003:004",
        },
        {
            "name": "eth8",
            "caps": "net",
            "address": "e6:86:48:46:c5:29",
            "state": "down",
            "device name": "pci_0000_02_10_7",
        },
    ]


@pytest.mark.parametrize(
    "dev_kvm, libvirtd", [(True, True), (False, False), (True, False)]
)
def test_is_kvm(dev_kvm, libvirtd):
    """
    Test the virt._is_kvm_hyper() function
    """
    with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=dev_kvm)}):
        processes = ["libvirtd"] if libvirtd else []
        with patch.dict(virt.__grains__, {"ps": MagicMock(return_value="foo")}):
            with patch.dict(
                virt.__salt__, {"cmd.run": MagicMock(return_value=processes)}
            ):
                assert virt._is_kvm_hyper() == (dev_kvm and libvirtd)

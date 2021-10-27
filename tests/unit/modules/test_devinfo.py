import textwrap

from salt.modules import devinfo
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class DevinfoTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {devinfo: {}}

    def test_udev(self):
        self.assertEqual(devinfo._udev({"A": {"B": 1}}, "a.b"), 1)
        self.assertEqual(devinfo._udev({"A": {"B": 1}}, "A.B"), 1)
        self.assertEqual(devinfo._udev({"A": {"B": 1}}, "a.c"), "n/a")
        self.assertEqual(devinfo._udev({"A": [1, 2]}, "a.b"), "n/a")
        self.assertEqual(devinfo._udev({"A": {"B": 1}}, ""), {"A": {"B": 1}})

    def test_match(self):
        self.assertTrue(devinfo._match({"A": {"B": 1}}, {"a.b": 1}))
        self.assertFalse(devinfo._match({"A": {"B": 1}}, {"a.b": 2}))
        self.assertTrue(devinfo._match({"A": {"B": 1}}, {"a.b": [1, 2]}))
        self.assertFalse(devinfo._match({"A": {"B": 1}}, {"a.b": [2, 3]}))
        self.assertTrue(devinfo._match({"A": {"B": [1, 2]}}, {"a.b": 1}))
        self.assertTrue(devinfo._match({"A": {"B": [1, 2]}}, {"a.b": [1, 3]}))
        self.assertFalse(devinfo._match({"A": {"B": [1, 2]}}, {"a.b": [3, 4]}))
        self.assertTrue(devinfo._match({"A": 1}, {}))

    def test_devices(self):
        cdrom = {
            "S": ["dvd", "cdrom"],
            "E": {"ID_BUS": "ata"},
        }
        usb = {
            "E": {"ID_BUS": "usb"},
        }
        hd = {
            "E": {"ID_BUS": "ata"},
        }

        with patch.dict(
            devinfo.__salt__,
            {"udev.info": lambda d: {"sda": hd, "sdb": usb, "sr0": cdrom}[d]},
        ), patch.dict(devinfo.__grains__, {"disks": ["sda", "sdb", "sr0"]}):
            self.assertEqual(devinfo.filter_({"e.id_bus": "ata"}, {}), ["sda", "sr0"])
            self.assertEqual(devinfo.filter_({"e.id_bus": "usb"}, {}), ["sdb"])
            self.assertEqual(
                devinfo.filter_({"e.id_bus": "ata"}, {"s": ["cdrom"]}), ["sda"]
            )

    def test__hwinfo_parse_short(self):
        hwinfo = textwrap.dedent(
            """
            cpu:
                                   QEMU Virtual CPU version 2.5+, 3591 MHz
            keyboard:
              /dev/input/event0    AT Translated Set 2 keyboard
            mouse:
              /dev/input/mice      VirtualPS/2 VMware VMMouse
              /dev/input/mice      VirtualPS/2 VMware VMMouse
            graphics card:
                                   VGA compatible controller
            storage:
                                   Floppy disk controller
                                   Red Hat Qemu virtual machine
            network:
              ens3                 Virtio Ethernet Card 0
            network interface:
              lo                   Loopback network interface
              ens3                 Ethernet network interface
            disk:
              /dev/fd0             Disk
              /dev/sda             QEMU HARDDISK
            cdrom:
              /dev/sr0             QEMU DVD-ROM
            floppy:
              /dev/fd0             Floppy Disk
            bios:
                                   BIOS
            bridge:
                                   Red Hat Qemu virtual machine
                                   Red Hat Qemu virtual machine
                                   Red Hat Qemu virtual machine
            memory:
                                   Main Memory
            unknown:
                                   FPU
                                   DMA controller
                                   PIC
                                   Keyboard controller
              /dev/lp0             Parallel controller
                                   PS/2 Controller
                                   Red Hat Virtio network device
              /dev/ttyS0           16550A
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_short(hwinfo),
            {
                "cpu": {0: "QEMU Virtual CPU version 2.5+, 3591 MHz"},
                "keyboard": {"/dev/input/event0": "AT Translated Set 2 keyboard"},
                "mouse": {"/dev/input/mice": "VirtualPS/2 VMware VMMouse"},
                "graphics card": {0: "VGA compatible controller"},
                "storage": {
                    0: "Floppy disk controller",
                    1: "Red Hat Qemu virtual machine",
                },
                "network": {"ens3": "Virtio Ethernet Card 0"},
                "network interface": {
                    "lo": "Loopback network interface",
                    "ens3": "Ethernet network interface",
                },
                "disk": {"/dev/fd0": "Disk", "/dev/sda": "QEMU HARDDISK"},
                "cdrom": {"/dev/sr0": "QEMU DVD-ROM"},
                "floppy": {"/dev/fd0": "Floppy Disk"},
                "bios": {0: "BIOS"},
                "bridge": {
                    0: "Red Hat Qemu virtual machine",
                    1: "Red Hat Qemu virtual machine",
                    2: "Red Hat Qemu virtual machine",
                },
                "memory": {0: "Main Memory"},
                "unknown": {
                    0: "FPU",
                    1: "DMA controller",
                    2: "PIC",
                    3: "Keyboard controller",
                    "/dev/lp0": "Parallel controller",
                    4: "PS/2 Controller",
                    5: "Red Hat Virtio network device",
                    "/dev/ttyS0": "16550A",
                },
            },
        )

    def test__hwinfo_parse_full_floppy(self):
        hwinfo = textwrap.dedent(
            """
            01: None 00.0: 0102 Floppy disk controller
              [Created at floppy.112]
              Unique ID: rdCR.3wRL2_g4d2B
              Hardware Class: storage
              Model: "Floppy disk controller"
              I/O Port: 0x3f2 (rw)
              I/O Ports: 0x3f4-0x3f5 (rw)
              I/O Port: 0x3f7 (rw)
              DMA: 2
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            02: Floppy 00.0: 10603 Floppy Disk
              [Created at floppy.127]
              Unique ID: sPPV.oZ89vuho4Y3
              Parent ID: rdCR.3wRL2_g4d2B
              Hardware Class: floppy
              Model: "Floppy Disk"
              Device File: /dev/fd0
              Size: 3.5 ''
              Config Status: cfg=new, avail=yes, need=no, active=unknown
              Size: 5760 sectors a 512 bytes
              Capacity: 0 GB (2949120 bytes)
              Drive status: no medium
              Config Status: cfg=new, avail=yes, need=no, active=unknown
              Attached to: #1 (Floppy disk controller)
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "01": {
                    "None 00.0": "0102 Floppy disk controller",
                    "Note": "Created at floppy.112",
                    "Unique ID": "rdCR.3wRL2_g4d2B",
                    "Hardware Class": "storage",
                    "Model": "Floppy disk controller",
                    "I/O Ports": ["0x3f2 (rw)", "0x3f4-0x3f5 (rw)", "0x3f7 (rw)"],
                    "DMA": "2",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "02": {
                    "Floppy 00.0": "10603 Floppy Disk",
                    "Note": "Created at floppy.127",
                    "Unique ID": "sPPV.oZ89vuho4Y3",
                    "Parent ID": "rdCR.3wRL2_g4d2B",
                    "Hardware Class": "floppy",
                    "Model": "Floppy Disk",
                    "Device File": "/dev/fd0",
                    "Size": ["3.5 ''", "5760 sectors a 512 bytes"],
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                    "Capacity": "0 GB (2949120 bytes)",
                    "Drive status": "no medium",
                    "Attached to": {"Handle": "#1 (Floppy disk controller)"},
                },
            },
        )

    def test__hwinfo_parse_full_bios(self):
        hwinfo = textwrap.dedent(
            """
            03: None 00.0: 10105 BIOS
              [Created at bios.186]
              Unique ID: rdCR.lZF+r4EgHp4
              Hardware Class: bios
              BIOS Keyboard LED Status:
                Scroll Lock: off
                Num Lock: off
                Caps Lock: off
              Serial Port 0: 0x3f8
              Parallel Port 0: 0x378
              Base Memory: 639 kB
              PnP BIOS: @@@0000
              MP spec rev 1.4 info:
                OEM id: "BOCHSCPU"
                Product id: "0.1"
                1 CPUs (0 disabled)
              BIOS32 Service Directory Entry: 0xfd2b0
              SMBIOS Version: 2.8
              BIOS Info: #0
                Vendor: "SeaBIOS"
                Version: "rel-1.12.1-0-ga5cab58e9a3f-prebuilt.qemu.org"
                Date: "04/01/2014"
                Start Address: 0xe8000
                ROM Size: 64 kB
                Features: 0x04000000000000000008
              System Info: #256
                Manufacturer: "QEMU"
                Product: "Standard PC (i440FX + PIIX, 1996)"
                Version: "pc-i440fx-4.0"
                UUID: undefined
                Wake-up: 0x06 (Power Switch)
              Chassis Info: #768
                Manufacturer: "QEMU"
                Version: "pc-i440fx-4.0"
                Type: 0x01 (Other)
                Bootup State: 0x03 (Safe)
                Power Supply State: 0x03 (Safe)
                Thermal State: 0x03 (Safe)
                Security Status: 0x02 (Unknown)
              Processor Info: #1024
                Socket: "CPU 0"
                Socket Type: 0x01 (Other)
                Socket Status: Populated
                Type: 0x03 (CPU)
                Family: 0x01 (Other)
                Manufacturer: "QEMU"
                Version: "pc-i440fx-4.0"
                Processor ID: 0x078bfbfd00000663
                Status: 0x01 (Enabled)
                Max. Speed: 2000 MHz
                Current Speed: 2000 MHz
              Physical Memory Array: #4096
                Use: 0x03 (System memory)
                Location: 0x01 (Other)
                Slots: 1
                Max. Size: 1 GB
                ECC: 0x06 (Multi-bit)
              Memory Device: #4352
                Location: "DIMM 0"
                Manufacturer: "QEMU"
                Memory Array: #4096
                Form Factor: 0x09 (DIMM)
                Type: 0x07 (RAM)
                Type Detail: 0x0002 (Other)
                Data Width: 0 bits
                 Size: 1 GB
              Memory Array Mapping: #4864
                Memory Array: #4096
                Partition Width: 1
                Start Address: 0x00000000
                End Address: 0x40000000
              Type 32 Record: #8192
                Data 00: 20 0b 00 20 00 00 00 00 00 00 00
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "03": {
                    "None 00.0": "10105 BIOS",
                    "Note": "Created at bios.186",
                    "Unique ID": "rdCR.lZF+r4EgHp4",
                    "Hardware Class": "bios",
                    "BIOS Keyboard LED Status": {
                        "Scroll Lock": "off",
                        "Num Lock": "off",
                        "Caps Lock": "off",
                    },
                    "Serial Port 0": "0x3f8",
                    "Parallel Port 0": "0x378",
                    "Base Memory": "639 kB",
                    "PnP BIOS": "@@@0000",
                    "MP spec rev 1.4 info": {
                        "OEM id": "BOCHSCPU",
                        "Product id": "0.1",
                        "Note": "1 CPUs (0 disabled)",
                    },
                    "BIOS32 Service Directory Entry": "0xfd2b0",
                    "SMBIOS Version": "2.8",
                    "BIOS Info": {
                        "Handle": "#0",
                        "Vendor": "SeaBIOS",
                        "Version": "rel-1.12.1-0-ga5cab58e9a3f-prebuilt.qemu.org",
                        "Date": "04/01/2014",
                        "Start Address": "0xe8000",
                        "ROM Size": "64 kB",
                        "Features": ["0x04000000000000000008"],
                    },
                    "System Info": {
                        "Handle": "#256",
                        "Manufacturer": "QEMU",
                        "Product": "Standard PC (i440FX + PIIX, 1996)",
                        "Version": "pc-i440fx-4.0",
                        "UUID": "undefined",
                        "Wake-up": "0x06 (Power Switch)",
                    },
                    "Chassis Info": {
                        "Handle": "#768",
                        "Manufacturer": "QEMU",
                        "Version": "pc-i440fx-4.0",
                        "Type": "0x01 (Other)",
                        "Bootup State": "0x03 (Safe)",
                        "Power Supply State": "0x03 (Safe)",
                        "Thermal State": "0x03 (Safe)",
                        "Security Status": "0x02 (Unknown)",
                    },
                    "Processor Info": {
                        "Handle": "#1024",
                        "Socket": "CPU 0",
                        "Socket Type": "0x01 (Other)",
                        "Socket Status": "Populated",
                        "Type": "0x03 (CPU)",
                        "Family": "0x01 (Other)",
                        "Manufacturer": "QEMU",
                        "Version": "pc-i440fx-4.0",
                        "Processor ID": "0x078bfbfd00000663",
                        "Status": "0x01 (Enabled)",
                        "Max. Speed": "2000 MHz",
                        "Current Speed": "2000 MHz",
                    },
                    "Physical Memory Array": {
                        "Handle": "#4096",
                        "Use": "0x03 (System memory)",
                        "Location": "0x01 (Other)",
                        "Slots": "1",
                        "Max. Size": "1 GB",
                        "ECC": "0x06 (Multi-bit)",
                    },
                    "Memory Device": {
                        "Handle": "#4352",
                        "Location": "DIMM 0",
                        "Manufacturer": "QEMU",
                        "Memory Array": {"Handle": "#4096"},
                        "Form Factor": "0x09 (DIMM)",
                        "Type": "0x07 (RAM)",
                        "Type Detail": "0x0002 (Other)",
                        "Data Width": "0 bits",
                        "Size": "1 GB",
                    },
                    "Memory Array Mapping": {
                        "Handle": "#4864",
                        "Memory Array": {"Handle": "#4096"},
                        "Partition Width": "1",
                        "Start Address": "0x00000000",
                        "End Address": "0x40000000",
                    },
                    "Type 32 Record": {
                        "Handle": "#8192",
                        "Data 00": "20 0b 00 20 00 00 00 00 00 00 00",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_system(self):
        hwinfo = textwrap.dedent(
            """
            04: None 00.0: 10107 System
              [Created at sys.64]
              Unique ID: rdCR.n_7QNeEnh23
              Hardware Class: system
              Model: "System"
              Formfactor: "desktop"
              Driver Info #0:
                Driver Status: thermal,fan are not active
                Driver Activation Cmd: "modprobe thermal; modprobe fan"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "04": {
                    "None 00.0": "10107 System",
                    "Note": "Created at sys.64",
                    "Unique ID": "rdCR.n_7QNeEnh23",
                    "Hardware Class": "system",
                    "Model": "System",
                    "Formfactor": "desktop",
                    "Driver Info #0": {
                        "Driver Status": "thermal,fan are not active",
                        "Driver Activation Cmd": "modprobe thermal; modprobe fan",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_unknown(self):
        hwinfo = textwrap.dedent(
            """
            05: None 00.0: 10104 FPU
              [Created at misc.191]
              Unique ID: rdCR.EMpH5pjcahD
              Hardware Class: unknown
              Model: "FPU"
              I/O Ports: 0xf0-0xff (rw)
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            06: None 00.0: 0801 DMA controller (8237)
              [Created at misc.205]
              Unique ID: rdCR.f5u1ucRm+H9
              Hardware Class: unknown
              Model: "DMA controller"
              I/O Ports: 0x00-0xcf7 (rw)
              I/O Ports: 0xc0-0xdf (rw)
              I/O Ports: 0x80-0x8f (rw)
              DMA: 4
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            07: None 00.0: 0800 PIC (8259)
              [Created at misc.218]
              Unique ID: rdCR.8uRK7LxiIA2
              Hardware Class: unknown
              Model: "PIC"
              I/O Ports: 0x20-0x21 (rw)
              I/O Ports: 0xa0-0xa1 (rw)
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            08: None 00.0: 0900 Keyboard controller
              [Created at misc.250]
              Unique ID: rdCR.9N+EecqykME
              Hardware Class: unknown
              Model: "Keyboard controller"
              I/O Port: 0x60 (rw)
              I/O Port: 0x64 (rw)
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            09: None 00.0: 0701 Parallel controller (SPP)
              [Created at misc.261]
              Unique ID: YMnp.ecK7NLYWZ5D
              Hardware Class: unknown
              Model: "Parallel controller"
              Device File: /dev/lp0
              I/O Ports: 0x378-0x37a (rw)
              I/O Ports: 0x37b-0x37f (rw)
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            10: None 00.0: 10400 PS/2 Controller
              [Created at misc.303]
              Unique ID: rdCR.DziBbWO85o5
              Hardware Class: unknown
              Model: "PS/2 Controller"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "05": {
                    "None 00.0": "10104 FPU",
                    "Note": "Created at misc.191",
                    "Unique ID": "rdCR.EMpH5pjcahD",
                    "Hardware Class": "unknown",
                    "Model": "FPU",
                    "I/O Ports": "0xf0-0xff (rw)",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "06": {
                    "None 00.0": "0801 DMA controller (8237)",
                    "Note": "Created at misc.205",
                    "Unique ID": "rdCR.f5u1ucRm+H9",
                    "Hardware Class": "unknown",
                    "Model": "DMA controller",
                    "I/O Ports": [
                        "0x00-0xcf7 (rw)",
                        "0xc0-0xdf (rw)",
                        "0x80-0x8f (rw)",
                    ],
                    "DMA": "4",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "07": {
                    "None 00.0": "0800 PIC (8259)",
                    "Note": "Created at misc.218",
                    "Unique ID": "rdCR.8uRK7LxiIA2",
                    "Hardware Class": "unknown",
                    "Model": "PIC",
                    "I/O Ports": ["0x20-0x21 (rw)", "0xa0-0xa1 (rw)"],
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "08": {
                    "None 00.0": "0900 Keyboard controller",
                    "Note": "Created at misc.250",
                    "Unique ID": "rdCR.9N+EecqykME",
                    "Hardware Class": "unknown",
                    "Model": "Keyboard controller",
                    "I/O Ports": ["0x60 (rw)", "0x64 (rw)"],
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "09": {
                    "None 00.0": "0701 Parallel controller (SPP)",
                    "Note": "Created at misc.261",
                    "Unique ID": "YMnp.ecK7NLYWZ5D",
                    "Hardware Class": "unknown",
                    "Model": "Parallel controller",
                    "Device File": "/dev/lp0",
                    "I/O Ports": ["0x378-0x37a (rw)", "0x37b-0x37f (rw)"],
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "10": {
                    "None 00.0": "10400 PS/2 Controller",
                    "Note": "Created at misc.303",
                    "Unique ID": "rdCR.DziBbWO85o5",
                    "Hardware Class": "unknown",
                    "Model": "PS/2 Controller",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_memory(self):
        hwinfo = textwrap.dedent(
            """
            12: None 00.0: 10102 Main Memory
              [Created at memory.74]
              Unique ID: rdCR.CxwsZFjVASF
              Hardware Class: memory
              Model: "Main Memory"
              Memory Range: 0x00000000-0x3cefffff (rw)
              Memory Size: 960 MB
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "12": {
                    "None 00.0": "10102 Main Memory",
                    "Note": "Created at memory.74",
                    "Unique ID": "rdCR.CxwsZFjVASF",
                    "Hardware Class": "memory",
                    "Model": "Main Memory",
                    "Memory Range": "0x00000000-0x3cefffff (rw)",
                    "Memory Size": "960 MB",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_bridge(self):
        hwinfo = textwrap.dedent(
            """
            13: PCI 01.0: 0601 ISA bridge
              [Created at pci.386]
              Unique ID: vSkL.ucdhKwLeeAA
              SysFS ID: /devices/pci0000:00/0000:00:01.0
              SysFS BusID: 0000:00:01.0
              Hardware Class: bridge
              Model: "Red Hat Qemu virtual machine"
              Vendor: pci 0x8086 "Intel Corporation"
              Device: pci 0x7000 "82371SB PIIX3 ISA [Natoma/Triton II]"
              SubVendor: pci 0x1af4 "Red Hat, Inc."
              SubDevice: pci 0x1100 "Qemu virtual machine"
              Module Alias: "pci:v00008086d00007000sv00001AF4sd00001100bc06sc01i00"
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            14: PCI 00.0: 0600 Host bridge
              [Created at pci.386]
              Unique ID: qLht.YeL3TKDjrxE
              SysFS ID: /devices/pci0000:00/0000:00:00.0
              SysFS BusID: 0000:00:00.0
              Hardware Class: bridge
              Model: "Red Hat Qemu virtual machine"
              Vendor: pci 0x8086 "Intel Corporation"
              Device: pci 0x1237 "440FX - 82441FX PMC [Natoma]"
              SubVendor: pci 0x1af4 "Red Hat, Inc."
              SubDevice: pci 0x1100 "Qemu virtual machine"
              Revision: 0x02
              Module Alias: "pci:v00008086d00001237sv00001AF4sd00001100bc06sc00i00"
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            15: PCI 01.3: 0680 Bridge
              [Created at pci.386]
              Unique ID: VRCs.M9Cc8lcQjE2
              SysFS ID: /devices/pci0000:00/0000:00:01.3
              SysFS BusID: 0000:00:01.3
              Hardware Class: bridge
              Model: "Red Hat Qemu virtual machine"
              Vendor: pci 0x8086 "Intel Corporation"
              Device: pci 0x7113 "82371AB/EB/MB PIIX4 ACPI"
              SubVendor: pci 0x1af4 "Red Hat, Inc."
              SubDevice: pci 0x1100 "Qemu virtual machine"
              Revision: 0x03
              Driver: "piix4_smbus"
              Driver Modules: "i2c_piix4"
              IRQ: 9 (no events)
              Module Alias: "pci:v00008086d00007113sv00001AF4sd00001100bc06sc80i00"
              Driver Info #0:
                Driver Status: i2c_piix4 is active
                Driver Activation Cmd: "modprobe i2c_piix4"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "13": {
                    "PCI 01.0": "0601 ISA bridge",
                    "Note": "Created at pci.386",
                    "Unique ID": "vSkL.ucdhKwLeeAA",
                    "SysFS ID": "/devices/pci0000:00/0000:00:01.0",
                    "SysFS BusID": "0000:00:01.0",
                    "Hardware Class": "bridge",
                    "Model": "Red Hat Qemu virtual machine",
                    "Vendor": 'pci 0x8086 "Intel Corporation"',
                    "Device": 'pci 0x7000 "82371SB PIIX3 ISA [Natoma/Triton II]"',
                    "SubVendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "SubDevice": 'pci 0x1100 "Qemu virtual machine"',
                    "Module Alias": (
                        "pci:v00008086d00007000sv00001AF4sd00001100bc06sc01i00"
                    ),
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "14": {
                    "PCI 00.0": "0600 Host bridge",
                    "Note": "Created at pci.386",
                    "Unique ID": "qLht.YeL3TKDjrxE",
                    "SysFS ID": "/devices/pci0000:00/0000:00:00.0",
                    "SysFS BusID": "0000:00:00.0",
                    "Hardware Class": "bridge",
                    "Model": "Red Hat Qemu virtual machine",
                    "Vendor": 'pci 0x8086 "Intel Corporation"',
                    "Device": 'pci 0x1237 "440FX - 82441FX PMC [Natoma]"',
                    "SubVendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "SubDevice": 'pci 0x1100 "Qemu virtual machine"',
                    "Revision": "0x02",
                    "Module Alias": (
                        "pci:v00008086d00001237sv00001AF4sd00001100bc06sc00i00"
                    ),
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "15": {
                    "PCI 01.3": "0680 Bridge",
                    "Note": "Created at pci.386",
                    "Unique ID": "VRCs.M9Cc8lcQjE2",
                    "SysFS ID": "/devices/pci0000:00/0000:00:01.3",
                    "SysFS BusID": "0000:00:01.3",
                    "Hardware Class": "bridge",
                    "Model": "Red Hat Qemu virtual machine",
                    "Vendor": 'pci 0x8086 "Intel Corporation"',
                    "Device": 'pci 0x7113 "82371AB/EB/MB PIIX4 ACPI"',
                    "SubVendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "SubDevice": 'pci 0x1100 "Qemu virtual machine"',
                    "Revision": "0x03",
                    "Driver": ["piix4_smbus"],
                    "Driver Modules": ["i2c_piix4"],
                    "IRQ": "9 (no events)",
                    "Module Alias": (
                        "pci:v00008086d00007113sv00001AF4sd00001100bc06sc80i00"
                    ),
                    "Driver Info #0": {
                        "Driver Status": "i2c_piix4 is active",
                        "Driver Activation Cmd": "modprobe i2c_piix4",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_ethernet(self):
        hwinfo = textwrap.dedent(
            """
            16: PCI 03.0: 0200 Ethernet controller
              [Created at pci.386]
              Unique ID: 3hqH.pkM7KXDR457
              SysFS ID: /devices/pci0000:00/0000:00:03.0
              SysFS BusID: 0000:00:03.0
              Hardware Class: unknown
              Model: "Red Hat Virtio network device"
              Vendor: pci 0x1af4 "Red Hat, Inc."
              Device: pci 0x1000 "Virtio network device"
              SubVendor: pci 0x1af4 "Red Hat, Inc."
              SubDevice: pci 0x0001
              Driver: "virtio-pci"
              Driver Modules: "virtio_pci"
              I/O Ports: 0xc000-0xc01f (rw)
              Memory Range: 0xfebd1000-0xfebd1fff (rw,non-prefetchable)
              Memory Range: 0xfe000000-0xfe003fff (ro,non-prefetchable)
              Memory Range: 0xfeb80000-0xfebbffff (ro,non-prefetchable,disabled)
              IRQ: 11 (no events)
              Module Alias: "pci:v00001AF4d00001000sv00001AF4sd00000001bc02sc00i00"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "16": {
                    "PCI 03.0": "0200 Ethernet controller",
                    "Note": "Created at pci.386",
                    "Unique ID": "3hqH.pkM7KXDR457",
                    "SysFS ID": "/devices/pci0000:00/0000:00:03.0",
                    "SysFS BusID": "0000:00:03.0",
                    "Hardware Class": "unknown",
                    "Model": "Red Hat Virtio network device",
                    "Vendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "Device": 'pci 0x1000 "Virtio network device"',
                    "SubVendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "SubDevice": "pci 0x0001",
                    "Driver": ["virtio-pci"],
                    "Driver Modules": ["virtio_pci"],
                    "I/O Ports": "0xc000-0xc01f (rw)",
                    "Memory Range": [
                        "0xfebd1000-0xfebd1fff (rw,non-prefetchable)",
                        "0xfe000000-0xfe003fff (ro,non-prefetchable)",
                        "0xfeb80000-0xfebbffff (ro,non-prefetchable,disabled)",
                    ],
                    "IRQ": "11 (no events)",
                    "Module Alias": (
                        "pci:v00001AF4d00001000sv00001AF4sd00000001bc02sc00i00"
                    ),
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_storage(self):
        hwinfo = textwrap.dedent(
            """
            17: PCI 01.1: 0101 IDE interface (ISA Compatibility mode-only controller, supports bus mts bus mastering)
              [Created at pci.386]
              Unique ID: mnDB.3sKqaxiizg6
              SysFS ID: /devices/pci0000:00/0000:00:01.1
              SysFS BusID: 0000:00:01.1
              Hardware Class: storage
              Model: "Red Hat Qemu virtual machine"
              Vendor: pci 0x8086 "Intel Corporation"
              Device: pci 0x7010 "82371SB PIIX3 IDE [Natoma/Triton II]"
              SubVendor: pci 0x1af4 "Red Hat, Inc."
              SubDevice: pci 0x1100 "Qemu virtual machine"
              Driver: "ata_piix"
              Driver Modules: "ata_piix"
              I/O Ports: 0x1f0-0x1f7 (rw)
              I/O Port: 0x3f6 (rw)
              I/O Ports: 0x170-0x177 (rw)
              I/O Port: 0x376 (rw)
              I/O Ports: 0xc020-0xc02f (rw)
              Module Alias: "pci:v00008086d00007010sv00001AF4sd00001100bc01sc01i80"
              Driver Info #0:
                Driver Status: ata_piix is active
                Driver Activation Cmd: "modprobe ata_piix"
              Driver Info #1:
                Driver Status: ata_generic is active
                Driver Activation Cmd: "modprobe ata_generic"
              Driver Info #2:
                Driver Status: pata_acpi is active
                Driver Activation Cmd: "modprobe pata_acpi"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "17": {
                    "PCI 01.1": (
                        "0101 IDE interface (ISA Compatibility mode-only controller,"
                        " supports bus mts bus mastering)"
                    ),
                    "Note": "Created at pci.386",
                    "Unique ID": "mnDB.3sKqaxiizg6",
                    "SysFS ID": "/devices/pci0000:00/0000:00:01.1",
                    "SysFS BusID": "0000:00:01.1",
                    "Hardware Class": "storage",
                    "Model": "Red Hat Qemu virtual machine",
                    "Vendor": 'pci 0x8086 "Intel Corporation"',
                    "Device": 'pci 0x7010 "82371SB PIIX3 IDE [Natoma/Triton II]"',
                    "SubVendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "SubDevice": 'pci 0x1100 "Qemu virtual machine"',
                    "Driver": ["ata_piix"],
                    "Driver Modules": ["ata_piix"],
                    "I/O Ports": [
                        "0x1f0-0x1f7 (rw)",
                        "0x3f6 (rw)",
                        "0x170-0x177 (rw)",
                        "0x376 (rw)",
                        "0xc020-0xc02f (rw)",
                    ],
                    "Module Alias": (
                        "pci:v00008086d00007010sv00001AF4sd00001100bc01sc01i80"
                    ),
                    "Driver Info #0": {
                        "Driver Status": "ata_piix is active",
                        "Driver Activation Cmd": "modprobe ata_piix",
                    },
                    "Driver Info #1": {
                        "Driver Status": "ata_generic is active",
                        "Driver Activation Cmd": "modprobe ata_generic",
                    },
                    "Driver Info #2": {
                        "Driver Status": "pata_acpi is active",
                        "Driver Activation Cmd": "modprobe pata_acpi",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_video(self):
        hwinfo = textwrap.dedent(
            """
            18: PCI 02.0: 0300 VGA compatible controller (VGA)
              [Created at pci.386]
              Unique ID: _Znp.WspiKb87LiA
              SysFS ID: /devices/pci0000:00/0000:00:02.0
              SysFS BusID: 0000:00:02.0
              Hardware Class: graphics card
              Model: "VGA compatible controller"
              Vendor: pci 0x1234
              Device: pci 0x1111
              SubVendor: pci 0x1af4 "Red Hat, Inc."
              SubDevice: pci 0x1100
              Revision: 0x02
              Driver: "bochs-drm"
              Driver Modules: "bochs_drm"
              Memory Range: 0xfd000000-0xfdffffff (ro,non-prefetchable)
              Memory Range: 0xfebd0000-0xfebd0fff (rw,non-prefetchable)
              Memory Range: 0x000c0000-0x000dffff (rw,non-prefetchable,disabled)
              Module Alias: "pci:v00001234d00001111sv00001AF4sd00001100bc03sc00i00"
              Driver Info #0:
                Driver Status: bochs_drm is active
                Driver Activation Cmd: "modprobe bochs_drm"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "18": {
                    "PCI 02.0": "0300 VGA compatible controller (VGA)",
                    "Note": "Created at pci.386",
                    "Unique ID": "_Znp.WspiKb87LiA",
                    "SysFS ID": "/devices/pci0000:00/0000:00:02.0",
                    "SysFS BusID": "0000:00:02.0",
                    "Hardware Class": "graphics card",
                    "Model": "VGA compatible controller",
                    "Vendor": "pci 0x1234",
                    "Device": "pci 0x1111",
                    "SubVendor": 'pci 0x1af4 "Red Hat, Inc."',
                    "SubDevice": "pci 0x1100",
                    "Revision": "0x02",
                    "Driver": ["bochs-drm"],
                    "Driver Modules": ["bochs_drm"],
                    "Memory Range": [
                        "0xfd000000-0xfdffffff (ro,non-prefetchable)",
                        "0xfebd0000-0xfebd0fff (rw,non-prefetchable)",
                        "0x000c0000-0x000dffff (rw,non-prefetchable,disabled)",
                    ],
                    "Module Alias": (
                        "pci:v00001234d00001111sv00001AF4sd00001100bc03sc00i00"
                    ),
                    "Driver Info #0": {
                        "Driver Status": "bochs_drm is active",
                        "Driver Activation Cmd": "modprobe bochs_drm",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_network(self):
        hwinfo = textwrap.dedent(
            """
            19: Virtio 00.0: 0200 Ethernet controller
              [Created at pci.1679]
              Unique ID: vWuh.VIRhsc57kTD
              Parent ID: 3hqH.pkM7KXDR457
              SysFS ID: /devices/pci0000:00/0000:00:03.0/virtio0
              SysFS BusID: virtio0
              Hardware Class: network
              Model: "Virtio Ethernet Card 0"
              Vendor: int 0x6014 "Virtio"
              Device: int 0x0001 "Ethernet Card 0"
              Driver: "virtio_net"
              Driver Modules: "virtio_net"
              Device File: ens3
              HW Address: 52:54:00:12:34:56
              Permanent HW Address: 52:54:00:12:34:56
              Link detected: yes
              Module Alias: "virtio:d00000001v00001AF4"
              Driver Info #0:
                Driver Status: virtio_net is active
                Driver Activation Cmd: "modprobe virtio_net"
              Config Status: cfg=new, avail=yes, need=no, active=unknown
              Attached to: #16 (Ethernet controller)

            20: None 00.0: 0700 Serial controller (16550)
              [Created at serial.74]
              Unique ID: S_Uw.3fyvFV+mbWD
              Hardware Class: unknown
              Model: "16550A"
              Device: "16550A"
              Device File: /dev/ttyS0
              Tags: mouse, modem, braille
              I/O Ports: 0x3f8-0x3ff (rw)
              IRQ: 4 (55234 events)
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "19": {
                    "Virtio 00.0": "0200 Ethernet controller",
                    "Note": "Created at pci.1679",
                    "Unique ID": "vWuh.VIRhsc57kTD",
                    "Parent ID": "3hqH.pkM7KXDR457",
                    "SysFS ID": "/devices/pci0000:00/0000:00:03.0/virtio0",
                    "SysFS BusID": "virtio0",
                    "Hardware Class": "network",
                    "Model": "Virtio Ethernet Card 0",
                    "Vendor": 'int 0x6014 "Virtio"',
                    "Device": 'int 0x0001 "Ethernet Card 0"',
                    "Driver": ["virtio_net"],
                    "Driver Modules": ["virtio_net"],
                    "Device File": "ens3",
                    "HW Address": "52:54:00:12:34:56",
                    "Permanent HW Address": "52:54:00:12:34:56",
                    "Link detected": "yes",
                    "Module Alias": "virtio:d00000001v00001AF4",
                    "Driver Info #0": {
                        "Driver Status": "virtio_net is active",
                        "Driver Activation Cmd": "modprobe virtio_net",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                    "Attached to": {"Handle": "#16 (Ethernet controller)"},
                },
                "20": {
                    "None 00.0": "0700 Serial controller (16550)",
                    "Note": "Created at serial.74",
                    "Unique ID": "S_Uw.3fyvFV+mbWD",
                    "Hardware Class": "unknown",
                    "Model": "16550A",
                    "Device": "16550A",
                    "Device File": "/dev/ttyS0",
                    "Tags": ["mouse", "modem", "braille"],
                    "I/O Ports": "0x3f8-0x3ff (rw)",
                    "IRQ": "4 (55234 events)",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_disk(self):
        hwinfo = textwrap.dedent(
            """
            21: SCSI 100.0: 10602 CD-ROM (DVD)
              [Created at block.249]
              Unique ID: KD9E.53N0UD4ozwD
              Parent ID: mnDB.3sKqaxiizg6
              SysFS ID: /class/block/sr0
              SysFS BusID: 1:0:0:0
              SysFS Device Link: /devices/pci0000:00/0000:00:01.1/ata2/host1/target1:0:0/1:0:0:0
              Hardware Class: cdrom
              Model: "QEMU DVD-ROM"
              Vendor: "QEMU"
              Device: "QEMU DVD-ROM"
              Revision: "2.5+"
              Driver: "ata_piix", "sr"
              Driver Modules: "ata_piix", "sr_mod"
              Device File: /dev/sr0 (/dev/sg1)
              Device Files: /dev/sr0, /dev/cdrom, /dev/dvd, /dev/disk/by-path/pci-0000:00:01.1-ata-2, /dev/disk/by-id/ata-QEMU_DVD-ROM_QM00003, /dev/disk/by-uuid/2019-08-11-11-44-39-00, /dev/disk/by-label/CDROM
              Device Number: block 11:0 (char 21:1)
              Features: DVD, MRW, MRW-W
              Config Status: cfg=new, avail=yes, need=no, active=unknown
              Attached to: #17 (IDE interface)
              Drive Speed: 4
              Volume ID: "CDROM"
              Application: "0X5228779D"
              Publisher: "SUSE LINUX GMBH"
              Preparer: "KIWI - HTTPS://GITHUB.COM/OSINSIDE/KIWI"
              Creation date: "2019081111443900"
              El Torito info: platform 0, bootable
                Boot Catalog: at sector 0x00fa
                Media: none starting at sector 0x00fb
                Load: 2048 bytes

            22: None 00.0: 10600 Disk
              [Created at block.245]
              Unique ID: kwWm.Fxp0d3BezAE
              SysFS ID: /class/block/fd0
              SysFS BusID: floppy.0
              SysFS Device Link: /devices/platform/floppy.0
              Hardware Class: disk
              Model: "Disk"
              Driver: "floppy"
              Driver Modules: "floppy"
              Device File: /dev/fd0
              Device Number: block 2:0
              Size: 8 sectors a 512 bytes
              Capacity: 0 GB (4096 bytes)
              Drive status: no medium
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            23: IDE 00.0: 10600 Disk
              [Created at block.245]
              Unique ID: 3OOL.W8iGvCekDp8
              Parent ID: mnDB.3sKqaxiizg6
              SysFS ID: /class/block/sda
              SysFS BusID: 0:0:0:0
              SysFS Device Link: /devices/pci0000:00/0000:00:01.1/ata1/host0/target0:0:0/0:0:0:0
              Hardware Class: disk
              Model: "QEMU HARDDISK"
              Vendor: "QEMU"
              Device: "HARDDISK"
              Revision: "2.5+"
              Serial ID: "QM00001"
              Driver: "ata_piix", "sd"
              Driver Modules: "ata_piix"
              Device File: /dev/sda
              Device Files: /dev/sda, /dev/disk/by-path/pci-0000:00:01.1-ata-1, /dev/disk/by-id/ata-QEMU_HARDDISK_QM00001
              Device Number: block 8:0-8:15
              Geometry (Logical): CHS 3133/255/63
              Size: 50331648 sectors a 512 bytes
              Capacity: 24 GB (25769803776 bytes)
              Config Status: cfg=new, avail=yes, need=no, active=unknown
              Attached to: #17 (IDE interface)
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "21": {
                    "SCSI 100.0": "10602 CD-ROM (DVD)",
                    "Note": "Created at block.249",
                    "Unique ID": "KD9E.53N0UD4ozwD",
                    "Parent ID": "mnDB.3sKqaxiizg6",
                    "SysFS ID": "/class/block/sr0",
                    "SysFS BusID": "1:0:0:0",
                    "SysFS Device Link": "/devices/pci0000:00/0000:00:01.1/ata2/host1/target1:0:0/1:0:0:0",
                    "Hardware Class": "cdrom",
                    "Model": "QEMU DVD-ROM",
                    "Vendor": "QEMU",
                    "Device": "QEMU DVD-ROM",
                    "Revision": "2.5+",
                    "Driver": ["ata_piix", "sr"],
                    "Driver Modules": ["ata_piix", "sr_mod"],
                    "Device File": "/dev/sr0 (/dev/sg1)",
                    "Device Files": [
                        "/dev/sr0",
                        "/dev/cdrom",
                        "/dev/dvd",
                        "/dev/disk/by-path/pci-0000:00:01.1-ata-2",
                        "/dev/disk/by-id/ata-QEMU_DVD-ROM_QM00003",
                        "/dev/disk/by-uuid/2019-08-11-11-44-39-00",
                        "/dev/disk/by-label/CDROM",
                    ],
                    "Device Number": "block 11:0 (char 21:1)",
                    "Features": ["DVD", "MRW", "MRW-W"],
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                    "Attached to": {"Handle": "#17 (IDE interface)"},
                    "Drive Speed": "4",
                    "Volume ID": "CDROM",
                    "Application": "0X5228779D",
                    "Publisher": "SUSE LINUX GMBH",
                    "Preparer": "KIWI - HTTPS://GITHUB.COM/OSINSIDE/KIWI",
                    "Creation date": "2019081111443900",
                    "El Torito info": {
                        "platform": "0",
                        "bootable": "yes",
                        "Boot Catalog": "at sector 0x00fa",
                        "Media": "none starting at sector 0x00fb",
                        "Load": "2048 bytes",
                    },
                },
                "22": {
                    "None 00.0": "10600 Disk",
                    "Note": "Created at block.245",
                    "Unique ID": "kwWm.Fxp0d3BezAE",
                    "SysFS ID": "/class/block/fd0",
                    "SysFS BusID": "floppy.0",
                    "SysFS Device Link": "/devices/platform/floppy.0",
                    "Hardware Class": "disk",
                    "Model": "Disk",
                    "Driver": ["floppy"],
                    "Driver Modules": ["floppy"],
                    "Device File": "/dev/fd0",
                    "Device Number": "block 2:0",
                    "Size": "8 sectors a 512 bytes",
                    "Capacity": "0 GB (4096 bytes)",
                    "Drive status": "no medium",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "23": {
                    "IDE 00.0": "10600 Disk",
                    "Note": "Created at block.245",
                    "Unique ID": "3OOL.W8iGvCekDp8",
                    "Parent ID": "mnDB.3sKqaxiizg6",
                    "SysFS ID": "/class/block/sda",
                    "SysFS BusID": "0:0:0:0",
                    "SysFS Device Link": "/devices/pci0000:00/0000:00:01.1/ata1/host0/target0:0:0/0:0:0:0",
                    "Hardware Class": "disk",
                    "Model": "QEMU HARDDISK",
                    "Vendor": "QEMU",
                    "Device": "HARDDISK",
                    "Revision": "2.5+",
                    "Serial ID": "QM00001",
                    "Driver": ["ata_piix", "sd"],
                    "Driver Modules": ["ata_piix"],
                    "Device File": "/dev/sda",
                    "Device Files": [
                        "/dev/sda",
                        "/dev/disk/by-path/pci-0000:00:01.1-ata-1",
                        "/dev/disk/by-id/ata-QEMU_HARDDISK_QM00001",
                    ],
                    "Device Number": "block 8:0-8:15",
                    "Geometry (Logical)": "CHS 3133/255/63",
                    "Size": "50331648 sectors a 512 bytes",
                    "Capacity": "24 GB (25769803776 bytes)",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                    "Attached to": {"Handle": "#17 (IDE interface)"},
                },
            },
        )

    def test__hwinfo_parse_full_keyboard(self):
        hwinfo = textwrap.dedent(
            """
            24: PS/2 00.0: 10800 Keyboard
              [Created at input.226]
              Unique ID: nLyy.+49ps10DtUF
              Hardware Class: keyboard
              Model: "AT Translated Set 2 keyboard"
              Vendor: 0x0001
              Device: 0x0001 "AT Translated Set 2 keyboard"
              Compatible to: int 0x0211 0x0001
              Device File: /dev/input/event0
              Device Files: /dev/input/event0, /dev/input/by-path/platform-i8042-serio-0-event-kbd
              Device Number: char 13:64
              Driver Info #0:
                XkbRules: xfree86
                XkbModel: pc104
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "24": {
                    "PS/2 00.0": "10800 Keyboard",
                    "Note": "Created at input.226",
                    "Unique ID": "nLyy.+49ps10DtUF",
                    "Hardware Class": "keyboard",
                    "Model": "AT Translated Set 2 keyboard",
                    "Vendor": "0x0001",
                    "Device": '0x0001 "AT Translated Set 2 keyboard"',
                    "Compatible to": "int 0x0211 0x0001",
                    "Device File": "/dev/input/event0",
                    "Device Files": [
                        "/dev/input/event0",
                        "/dev/input/by-path/platform-i8042-serio-0-event-kbd",
                    ],
                    "Device Number": "char 13:64",
                    "Driver Info #0": {"XkbRules": "xfree86", "XkbModel": "pc104"},
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_mouse(self):
        hwinfo = textwrap.dedent(
            """
            25: PS/2 00.0: 10500 PS/2 Mouse
              [Created at input.249]
              Unique ID: AH6Q.mYF0pYoTCW7
              Hardware Class: mouse
              Model: "VirtualPS/2 VMware VMMouse"
              Vendor: 0x0002
              Device: 0x0013 "VirtualPS/2 VMware VMMouse"
              Compatible to: int 0x0210 0x0003
              Device File: /dev/input/mice (/dev/input/mouse0)
              Device Files: /dev/input/mice, /dev/input/mouse0, /dev/input/event1, /dev/input/by-path/platform-i8042-serio-1-event-mouse, /dev/input/by-path/platform-i8042-serio-1-mouse
              Device Number: char 13:63 (char 13:32)
              Driver Info #0:
                Buttons: 3
                Wheels: 0
                XFree86 Protocol: explorerps/2
                GPM Protocol: exps2
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            26: PS/2 00.0: 10500 PS/2 Mouse
              [Created at input.249]
              Unique ID: AH6Q.++hSeDccb2F
              Hardware Class: mouse
              Model: "VirtualPS/2 VMware VMMouse"
              Vendor: 0x0002
              Device: 0x0013 "VirtualPS/2 VMware VMMouse"
              Compatible to: int 0x0210 0x0012
              Device File: /dev/input/mice (/dev/input/mouse1)
              Device Files: /dev/input/mice, /dev/input/mouse1, /dev/input/event2
              Device Number: char 13:63 (char 13:33)
              Driver Info #0:
                Buttons: 2
                Wheels: 1
                XFree86 Protocol: explorerps/2
                GPM Protocol: exps2
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "25": {
                    "PS/2 00.0": "10500 PS/2 Mouse",
                    "Note": "Created at input.249",
                    "Unique ID": "AH6Q.mYF0pYoTCW7",
                    "Hardware Class": "mouse",
                    "Model": "VirtualPS/2 VMware VMMouse",
                    "Vendor": "0x0002",
                    "Device": '0x0013 "VirtualPS/2 VMware VMMouse"',
                    "Compatible to": "int 0x0210 0x0003",
                    "Device File": "/dev/input/mice (/dev/input/mouse0)",
                    "Device Files": [
                        "/dev/input/mice",
                        "/dev/input/mouse0",
                        "/dev/input/event1",
                        "/dev/input/by-path/platform-i8042-serio-1-event-mouse",
                        "/dev/input/by-path/platform-i8042-serio-1-mouse",
                    ],
                    "Device Number": "char 13:63 (char 13:32)",
                    "Driver Info #0": {
                        "Buttons": "3",
                        "Wheels": "0",
                        "XFree86 Protocol": "explorerps/2",
                        "GPM Protocol": "exps2",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "26": {
                    "PS/2 00.0": "10500 PS/2 Mouse",
                    "Note": "Created at input.249",
                    "Unique ID": "AH6Q.++hSeDccb2F",
                    "Hardware Class": "mouse",
                    "Model": "VirtualPS/2 VMware VMMouse",
                    "Vendor": "0x0002",
                    "Device": '0x0013 "VirtualPS/2 VMware VMMouse"',
                    "Compatible to": "int 0x0210 0x0012",
                    "Device File": "/dev/input/mice (/dev/input/mouse1)",
                    "Device Files": [
                        "/dev/input/mice",
                        "/dev/input/mouse1",
                        "/dev/input/event2",
                    ],
                    "Device Number": "char 13:63 (char 13:33)",
                    "Driver Info #0": {
                        "Buttons": "2",
                        "Wheels": "1",
                        "XFree86 Protocol": "explorerps/2",
                        "GPM Protocol": "exps2",
                    },
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_cpu(self):
        hwinfo = textwrap.dedent(
            """
            27: None 00.0: 10103 CPU
              [Created at cpu.462]
              Unique ID: rdCR.j8NaKXDZtZ6
              Hardware Class: cpu
              Arch: X86-64
              Vendor: "GenuineIntel"
              Model: 6.6.3 "QEMU Virtual CPU version 2.5+"
              Features: fpu,de,pse,tsc,msr,pae,mce,cx8,apic,sep,mtrr,pge,mca,cmov,pse36,clflush,mmx,fxsr,sse,sse2,syscall,nx,lm,rep_good,nopl,xtopology,cpuid,tsc_known_freq,pni,cx16,x2apic,hypervisor,lahf_lm,cpuid_fault,pti
              Clock: 3591 MHz
              BogoMips: 7182.68
              Cache: 16384 kb
              Config Status: cfg=new, avail=yes, need=no, active=unknown
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "27": {
                    "None 00.0": "10103 CPU",
                    "Note": "Created at cpu.462",
                    "Unique ID": "rdCR.j8NaKXDZtZ6",
                    "Hardware Class": "cpu",
                    "Arch": "X86-64",
                    "Vendor": "GenuineIntel",
                    "Model": '6.6.3 "QEMU Virtual CPU version 2.5+"',
                    "Features": [
                        "fpu",
                        "de",
                        "pse",
                        "tsc",
                        "msr",
                        "pae",
                        "mce",
                        "cx8",
                        "apic",
                        "sep",
                        "mtrr",
                        "pge",
                        "mca",
                        "cmov",
                        "pse36",
                        "clflush",
                        "mmx",
                        "fxsr",
                        "sse",
                        "sse2",
                        "syscall",
                        "nx",
                        "lm",
                        "rep_good",
                        "nopl",
                        "xtopology",
                        "cpuid",
                        "tsc_known_freq",
                        "pni",
                        "cx16",
                        "x2apic",
                        "hypervisor",
                        "lahf_lm",
                        "cpuid_fault",
                        "pti",
                    ],
                    "Clock": "3591 MHz",
                    "BogoMips": "7182.68",
                    "Cache": "16384 kb",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
            },
        )

    def test__hwinfo_parse_full_nic(self):
        hwinfo = textwrap.dedent(
            """
            28: None 00.0: 10700 Loopback
              [Created at net.126]
              Unique ID: ZsBS.GQNx7L4uPNA
              SysFS ID: /class/net/lo
              Hardware Class: network interface
              Model: "Loopback network interface"
              Device File: lo
              Link detected: yes
              Config Status: cfg=new, avail=yes, need=no, active=unknown

            29: None 03.0: 10701 Ethernet
              [Created at net.126]
              Unique ID: U2Mp.ndpeucax6V1
              Parent ID: vWuh.VIRhsc57kTD
              SysFS ID: /class/net/ens3
              SysFS Device Link: /devices/pci0000:00/0000:00:03.0/virtio0
              Hardware Class: network interface
              Model: "Ethernet network interface"
              Driver: "virtio_net"
              Driver Modules: "virtio_net"
              Device File: ens3
              HW Address: 52:54:00:12:34:56
              Permanent HW Address: 52:54:00:12:34:56
              Link detected: yes
              Config Status: cfg=new, avail=yes, need=no, active=unknown
              Attached to: #19 (Ethernet controller)
        """
        )
        self.assertEqual(
            devinfo._hwinfo_parse_full(hwinfo),
            {
                "28": {
                    "None 00.0": "10700 Loopback",
                    "Note": "Created at net.126",
                    "Unique ID": "ZsBS.GQNx7L4uPNA",
                    "SysFS ID": "/class/net/lo",
                    "Hardware Class": "network interface",
                    "Model": "Loopback network interface",
                    "Device File": "lo",
                    "Link detected": "yes",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                },
                "29": {
                    "None 03.0": "10701 Ethernet",
                    "Note": "Created at net.126",
                    "Unique ID": "U2Mp.ndpeucax6V1",
                    "Parent ID": "vWuh.VIRhsc57kTD",
                    "SysFS ID": "/class/net/ens3",
                    "SysFS Device Link": "/devices/pci0000:00/0000:00:03.0/virtio0",
                    "Hardware Class": "network interface",
                    "Model": "Ethernet network interface",
                    "Driver": ["virtio_net"],
                    "Driver Modules": ["virtio_net"],
                    "Device File": "ens3",
                    "HW Address": "52:54:00:12:34:56",
                    "Permanent HW Address": "52:54:00:12:34:56",
                    "Link detected": "yes",
                    "Config Status": {
                        "cfg": "new",
                        "avail": "yes",
                        "need": "no",
                        "active": "unknown",
                    },
                    "Attached to": {"Handle": "#19 (Ethernet controller)"},
                },
            },
        )

# Expected nxos.grains / system_info structure for ``n9k_show_ver`` fixture output
n9k_grains = {
    "nxos": {
        "software": {
            "BIOS": "version 08.36",
            "NXOS": "version 9.2(1)",
            "BIOS compile time": "06/07/2019",
            "NXOS image file is": "bootflash:///nxos.9.2.1.bin",
            "NXOS compile time": "7/17/2018 16:00:00 [07/18/2018 00:21:19]",
        },
        "hardware": {"Device name": "n9k-device", "bootflash": "53298520 kB"},
        "plugins": ["Core Plugin", "Ethernet Plugin"],
    }
}

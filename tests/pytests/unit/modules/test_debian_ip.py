import salt.modules.debian_ip as debian_ip


def test_when_no_adapters_are_passed_to_filter_none_should_be_returned():
    no_adapters = {}

    actual_adapters = debian_ip._filter_malformed_interfaces(adapters=no_adapters)

    assert not actual_adapters


def test_when_adapters_only_contains_source_then_source_should_be_returned():
    souce_only_adapters = {"source": "fnord"}
    expected_adapters = souce_only_adapters.copy()

    actual_adapters = debian_ip._filter_malformed_interfaces(
        adapters=souce_only_adapters
    )

    assert actual_adapters == expected_adapters


def test_when_data_is_missing_from_adapters_they_should_not_be_in_result():
    missing_data_adapters = {"no data adapter": "no dayta is here"}
    expected_adapters = {}
    actual_adapters = debian_ip._filter_malformed_interfaces(
        adapters=missing_data_adapters
    )

    assert actual_adapters == expected_adapters


def test_when_data_in_adapters_and_no_inet_or_inet6_in_data_segment_then_original_data_should_be_returned():
    expected_adapters = {
        "some cool adapter": {"data": {}},
        "some other adapter": {"data": {}},
        "yet another neat adapter": {"data": {}},
    }

    no_inet_data_adapters = {"no data adapter": "this one should be gone"}
    no_inet_data_adapters.update(expected_adapters)

    actual_adapters = debian_ip._filter_malformed_interfaces(
        adapters=no_inet_data_adapters
    )
    assert actual_adapters == expected_adapters


def test_when_opts_are_in_data_sorted_opt_keys_should_be_added():
    comprehensive_adapters = {
        "source": "keep me here",
        "no data adapter": "lulz",
        "adapter 1": {
            "data": {
                "inet": {
                    "ethtool": {
                        "5": {},
                        "4": {},
                        "2": {},
                        "3": {},
                        "1": {},
                    },
                    "bonding": {
                        "4": {},
                        "5": {},
                        "3": {},
                        "2": {},
                        "1": {},
                    },
                    "bridging": {
                        "1": {},
                        "5": {},
                        "4": {},
                        "2": {},
                        "3": {},
                    },
                },
            },
        },
    }

    expected_adapters = {
        "source": "keep me here",
        "adapter 1": {
            "data": {
                "inet": {
                    "ethtool_keys": ["1", "2", "3", "4", "5"],
                    "bonding_keys": ["1", "2", "3", "4", "5"],
                    "bridging_keys": ["1", "2", "3", "4", "5"],
                    "ethtool": {
                        "5": {},
                        "4": {},
                        "3": {},
                        "2": {},
                        "1": {},
                    },
                    "bonding": {
                        "5": {},
                        "4": {},
                        "3": {},
                        "2": {},
                        "1": {},
                    },
                    "bridging": {
                        "5": {},
                        "4": {},
                        "3": {},
                        "2": {},
                        "1": {},
                    },
                },
            },
        },
    }
    actual_adapters = debian_ip._filter_malformed_interfaces(
        adapters=comprehensive_adapters
    )
    assert actual_adapters == expected_adapters

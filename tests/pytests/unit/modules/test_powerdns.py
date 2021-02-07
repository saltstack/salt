import pytest
import salt.modules.powerdns as powerdns
import tests.support.mock as mock
from salt.exceptions import CommandExecutionError


@pytest.fixture
def configure_loader_modules():
    return {powerdns: {}}


def _mock_response(
    status=200, content="CONTENT", json_data=None, raise_for_status=None
):
    mock_resp = mock.Mock()
    mock_resp.raise_for_status = mock.Mock()
    if raise_for_status:
        mock_resp.raise_for_status.side_effect = raise_for_status
    mock_resp.status_code = status
    mock_resp.content = content
    if json_data:
        mock_resp.json = mock.Mock(return_value=json_data)
    return mock_resp


def test__get_zone_return_correct_json():
    mock_resp = _mock_response(json_data="test_data")
    patch_request = mock.patch("requests.get", return_value=mock_resp, autospec=True)

    with patch_request:
        response = powerdns._get_zone("zone", "key", "server")
    assert response == "test_data"
    assert mock_resp.json.called


def test__get_zone_unprocessable_entity_return_none():
    mock_resp = _mock_response(status=422)
    patch_request = mock.patch("requests.get", return_value=mock_resp, autospec=True)

    with patch_request:
        response = powerdns._get_zone("zone", "key", "server")
    assert response is None


def test__check_records_equality_returns_true():
    old_record = {"name": "test_name_1", "type": "A"}
    new_record = {"name": "test_name_1", "type": "A"}
    result = powerdns._check_records_equality(old_record, new_record)
    assert result


def test__check_records_equality_returns_false():
    old_record = {"name": "test_name_1"}
    new_record = {"name": "test_name_2"}
    result = powerdns._check_records_equality(old_record, new_record)
    assert not result


def test__check_is_zone_changed_rerurns_changes():
    old_zone = {"dnssec": False}
    new_zone = {"dnssec": True}
    result = powerdns._check_is_zone_changed(old_zone, new_zone)
    assert len(result) == 1
    assert result == [{"dnssec": {"old": False, "new": True}}]


def test__check_is_zone_changed_rerurns_empty_list():
    old_zone = {"dnssec": False}
    new_zone = {"dnssec": False}
    result = powerdns._check_is_zone_changed(old_zone, new_zone)
    assert len(result) == 0
    assert result == []


def test__check_are_records_changed_returns_true():
    old_records = [{"content": "test_1"}, {"content": "test_2"}]
    new_records = [{"content": "test_3"}]
    result = powerdns._check_are_records_changed(old_records, new_records)
    assert result


def test__check_are_records_changed_returns_false():
    old_records = [{"content": "test_1"}]
    new_records = [{"content": "test_1"}]
    result = powerdns._check_are_records_changed(old_records, new_records)
    assert not result


def test__check_are_rrsets_changed_return_list_of_changes():
    old_rrset = [
        {
            "name": "test_name.com",
            "type": "A",
            "records": [{"content": "123.45.67.89"}],
            "ttl": 30,
        }
    ]
    new_rrset = [
        {
            "name": "test_name.com",
            "type": "A",
            "records": [{"content": "123.45.67.89"}],
            "ttl": 30,
        },
        {
            "name": "www.test_name.com",
            "type": "CNAME",
            "records": [{"content": "test_name.com"}],
            "ttl": 30,
        },
    ]
    result = powerdns._check_are_rrsets_changed(old_rrset, new_rrset)
    assert result == [
        {
            "www.test_name.com": {
                "new": {"content": ["test_name.com"], "ttl": 30},
                "type": "CNAME",
            }
        }
    ]


def test__check_are_rrsets_changed_return_empty_list():
    old_rrset = [
        {
            "name": "test_name.com",
            "type": "A",
            "records": [{"content": "123.45.67.89"}],
            "ttl": 30,
        }
    ]
    new_rrset = [
        {
            "name": "test_name.com",
            "type": "A",
            "records": [{"content": "123.45.67.89"}],
            "ttl": 30,
        }
    ]
    result = powerdns._check_are_rrsets_changed(old_rrset, new_rrset)
    assert len(result) == 0
    assert result == []


def test__check_are_rrsets_deleted():
    rrsets = [
        {
            "changetype": "DELETE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 300,
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 300,
        },
    ]
    result = powerdns._check_are_rrsets_deleted(rrsets)
    assert len(result) == 1
    assert result == [
        {"zone1.com": {"content": ["123.45.67.89"], "ttl": 300, "type": "A"}}
    ]


def test__check_are_rrsets_have_ns_returns_true():
    rrsets = [
        {
            "changetype": "DELETE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "NS",
            "ttl": 30,
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 30,
        },
    ]
    result = powerdns._check_are_rrsets_have_ns(rrsets)
    assert result


def test__check_are_rrsets_have_ns_returns_false():
    rrsets = [
        {
            "changetype": "DELETE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 30,
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 30,
        },
    ]
    result = powerdns._check_are_rrsets_have_ns(rrsets)
    assert not result


def test__filter_incorrect_soa_records_returns_records_wo_soa():
    rrsets = [
        {
            "changetype": "DELETE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "SOA",
            "ttl": 30,
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 30,
        },
    ]
    result = powerdns._filter_incorrect_soa_records(rrsets)
    assert len(result) == 1
    assert result == [
        {
            "changetype": "REPLACE",
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "A",
            "ttl": 30,
        }
    ]


def test__prepare_nameservers_rrsets_return_rrsets():
    name = "zone1.com"
    nameservers = ["ns.zone.org", "ns.zone.org"]

    result = powerdns._prepare_nameservers_rrsets(name, nameservers)
    assert result == [
        {
            "changetype": "REPLACE",
            "name": "zone1.com.",
            "records": [
                {"content": "ns.zone.org.", "disabled": False},
                {"content": "ns.zone.org.", "disabled": False},
            ],
            "ttl": 3600,
            "type": "NS",
        }
    ]


def test__prepare_rrset_return_rrsets():
    rrset_1 = {
        "name": "zone1.com",
        "records": [{"content": "123.45.67.89"}],
        "type": "a",
        "ttl": 3600,
    }
    rrset_2 = {
        "name": "zone2.com",
        "content": ["mx.test.com", "mx2.test.com"],
        "type": "mx",
    }
    rrset_3 = {"name": "zone3.com", "content": "test_content", "type": "txt"}
    result_1 = powerdns._prepare_rrset(rrset_1)
    result_2 = powerdns._prepare_rrset(rrset_2)
    result_3 = powerdns._prepare_rrset(rrset_3)
    assert result_1 == {
        "name": "zone1.com.",
        "records": [{"content": "123.45.67.89", "disabled": False}],
        "type": "A",
        "ttl": 3600,
        "changetype": "REPLACE",
    }

    assert result_2 == {
        "changetype": "REPLACE",
        "name": "zone2.com.",
        "records": [
            {"content": "mx.test.com.", "disabled": False},
            {"content": "mx2.test.com.", "disabled": False},
        ],
        "ttl": 300,
        "type": "MX",
    }

    assert result_3 == {
        "changetype": "REPLACE",
        "name": "zone3.com.",
        "records": [{"content": '"test_content"', "disabled": False}],
        "ttl": 300,
        "type": "TXT",
    }


def test__prepare_rrsets_new_rrsets():
    name = "zone1.com"
    drop_existing = False
    nameservers = ["ns1.zone.org", "ns2.zone.org"]
    new_rrsets = [
        {
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "a",
            "ttl": 3600,
        },
        {
            "name": "mx.zone1.com",
            "content": ["mx.test.com", "mx2.test.com"],
            "type": "mx",
        },
        {"name": "txt.zone1.com", "content": "test_content", "type": "txt"},
    ]

    result = powerdns._prepare_rrsets(name, drop_existing, nameservers, new_rrsets)
    assert len(result) == 4
    assert result == [
        {
            "name": "zone1.com.",
            "records": [{"content": "123.45.67.89", "disabled": False}],
            "type": "A",
            "ttl": 3600,
            "changetype": "REPLACE",
        },
        {
            "changetype": "REPLACE",
            "name": "mx.zone1.com.",
            "records": [
                {"content": "mx.test.com.", "disabled": False},
                {"content": "mx2.test.com.", "disabled": False},
            ],
            "ttl": 300,
            "type": "MX",
        },
        {
            "changetype": "REPLACE",
            "name": "txt.zone1.com.",
            "records": [{"content": '"test_content"', "disabled": False}],
            "ttl": 300,
            "type": "TXT",
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com.",
            "records": [
                {"content": "ns1.zone.org.", "disabled": False},
                {"content": "ns2.zone.org.", "disabled": False},
            ],
            "ttl": 3600,
            "type": "NS",
        },
    ]


def test__prepare_rrsets_new_rrsets_and_old_rrsets():
    name = "zone1.com"
    drop_existing = False
    nameservers = ["ns1.zone.org", "ns2.zone.org"]
    new_rrsets = [
        {
            "name": "zone1.com",
            "records": [{"content": "123.45.67.89"}],
            "type": "a",
            "ttl": 7200,
        }
    ]
    old_rrsets = [
        {
            "name": "zone1.com.",
            "records": [{"content": "23.45.67.1", "disabled": False}],
            "type": "A",
            "ttl": 3600,
        }
    ]

    result = powerdns._prepare_rrsets(
        name, drop_existing, nameservers, new_rrsets, old_rrsets
    )
    assert len(result) == 2
    assert result == [
        {
            "name": "zone1.com.",
            "records": [{"content": "123.45.67.89", "disabled": False}],
            "type": "A",
            "ttl": 7200,
            "changetype": "REPLACE",
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com.",
            "records": [
                {"content": "ns1.zone.org.", "disabled": False},
                {"content": "ns2.zone.org.", "disabled": False},
            ],
            "ttl": 3600,
            "type": "NS",
        },
    ]


def test__prepare_rrsets_new_rrsets_and_old_rrsets_drop_existing():
    name = "zone1.com"
    drop_existing = True
    nameservers = ["ns1.zone.org", "ns2.zone.org"]
    new_rrsets = [
        {
            "name": "www.zone1.com",
            "records": [{"content": "zone1.com"}],
            "type": "cname",
            "ttl": 7200,
        }
    ]
    old_rrsets = [
        {
            "name": "zone1.com.",
            "records": [{"content": "23.45.67.1", "disabled": False}],
            "type": "A",
            "ttl": 3600,
        }
    ]

    result = powerdns._prepare_rrsets(
        name, drop_existing, nameservers, new_rrsets, old_rrsets
    )
    assert len(result) == 3
    assert result == [
        {
            "changetype": "DELETE",
            "name": "zone1.com.",
            "records": [{"content": "23.45.67.1", "disabled": False}],
            "ttl": 3600,
            "type": "A",
        },
        {
            "name": "www.zone1.com.",
            "records": [{"content": "zone1.com.", "disabled": False}],
            "type": "CNAME",
            "ttl": 7200,
            "changetype": "REPLACE",
        },
        {
            "changetype": "REPLACE",
            "name": "zone1.com.",
            "records": [
                {"content": "ns1.zone.org.", "disabled": False},
                {"content": "ns2.zone.org.", "disabled": False},
            ],
            "ttl": 3600,
            "type": "NS",
        },
    ]


def test__prepare_new_zone_result_object():
    request = {
        "dnssec": False,
        "name": "zone1.com",
        "nameservers": ["ns1.zone.org", "ns2.zone.org"],
        "rrsets": [
            {
                "name": "www.zone1.com",
                "records": [{"content": "zone1.com"}],
                "type": "CNAME",
                "ttl": 7200,
            },
            {
                "name": "testzonezonezone1.com",
                "records": [{"content": "123.45.67.89"}],
                "type": "A",
                "ttl": 360,
            },
        ],
    }
    result = powerdns._prepare_new_zone_result_object(request)
    assert result == {
        "dnssec": False,
        "name": "zone1.com",
        "nameservers": ["ns1.zone.org", "ns2.zone.org"],
        "records": [
            {
                "www.zone1.com": {
                    "content": ["zone1.com"],
                    "ttl": 7200,
                    "type": "CNAME",
                }
            },
            {
                "testzonezonezone1.com": {
                    "content": ["123.45.67.89"],
                    "ttl": 360,
                    "type": "A",
                }
            },
        ],
    }


def test__validate_rrsets_raise_error():
    rrsets = [{"name": "zone.com", "content": {}}]
    nameservers = ["ns1.zone.org", "ns2.zone.org"]

    with pytest.raises(CommandExecutionError):
        powerdns._validate_rrsets(rrsets, nameservers)


def test__check_is_valid_ip_address_correct_ip():
    ip = "123.45.67.89"
    result = powerdns._check_is_valid_ip_address(ip)
    assert result


def test__check_is_valid_ip_address_incorrect_ip():
    ip = "1123.45.67.8139"
    result = powerdns._check_is_valid_ip_address(ip)
    assert not result


def test__add_trailing_dot_add_dot():
    content = "zone1.com"
    result = powerdns._add_trailing_dot(content)
    assert result == "zone1.com."


def test__add_trailing_dot_skip_dot():
    content = "zone1.com."
    result = powerdns._add_trailing_dot(content)
    assert result == "zone1.com."


def test__extract_content_from_records():
    records = [{"content": "test_content1"}, {"content": "test_content2"}]
    result = powerdns._extract_content_from_records(records)
    assert len(result) == 2
    assert result == ["test_content1", "test_content2"]


def test_manage_zone_creates_new_zone():

    mock_post_resp = _mock_response(status=201)
    patch_request = mock.patch(
        "requests.post", return_value=mock_post_resp, autospec=True
    )

    patch_get_zone = mock.patch("salt.modules.powerdns._get_zone", return_value=None)

    with patch_request, patch_get_zone:

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.78"}],
                "type": "A",
                "ttl": 30,
            },
            {
                "name": "www.zone1.com",
                "records": [{"content": "zone1.com"}],
                "type": "cname",
                "ttl": 7200,
            },
        ]
        nameservers = ["ns1.zone1.com", "ns2.zone2.com"]
        drop_existing = False
        dnssec = True

        result = powerdns.manage_zone(
            name, key, server, rrsets, nameservers, drop_existing, dnssec
        )

    assert result == {
        "changes": {
            "created": {
                "dnssec": True,
                "name": "zone1.com.",
                "nameservers": [],
                "records": [
                    {
                        "zone1.com.": {
                            "content": ["12.34.56.78"],
                            "ttl": 30,
                            "type": "A",
                        }
                    },
                    {
                        "www.zone1.com.": {
                            "content": ["zone1.com."],
                            "ttl": 7200,
                            "type": "CNAME",
                        }
                    },
                    {
                        "zone1.com.": {
                            "content": ["ns1.zone1.com.", "ns2.zone2.com."],
                            "ttl": 3600,
                            "type": "NS",
                        }
                    },
                ],
            }
        },
        "name": "zone1.com",
        "result": True,
    }


def test_manage_zone_fail_creates_new_zone():

    mock_post_resp = _mock_response(status=400)
    patch_request = mock.patch(
        "requests.post", return_value=mock_post_resp, autospec=True
    )

    patch_get_zone = mock.patch("salt.modules.powerdns._get_zone", return_value=None)

    with patch_request, patch_get_zone:

        with pytest.raises(CommandExecutionError):

            name = "zone1.com"
            key = "TEST_KEY"
            server = "pdns.test.com"
            rrsets = [
                {
                    "name": "zone1.com",
                    "records": [{"content": "12.34.56.78"}],
                    "type": "A",
                    "ttl": 30,
                },
                {
                    "name": "www.zone1.com",
                    "records": [{"content": "zone1.com"}],
                    "type": "cname",
                    "ttl": 7200,
                },
            ]
            nameservers = ["ns1.zone1.com", "ns2.zone2.com"]
            drop_existing = False
            dnssec = True

            powerdns.manage_zone(
                name, key, server, rrsets, nameservers, drop_existing, dnssec
            )


def test_manage_zone_updates_dnssec():

    old_zone = {
        "dnssec": False,
        "rrsets": [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.78"}],
                "type": "A",
                "ttl": 30,
            }
        ],
    }

    mock_put_resp = _mock_response(status=204)
    patch_request = mock.patch(
        "requests.put", return_value=mock_put_resp, autospec=True
    )

    patch_get_zone = mock.patch(
        "salt.modules.powerdns._get_zone", return_value=old_zone
    )

    patch_check_are_rrsets_changed = mock.patch(
        "salt.modules.powerdns._check_are_rrsets_changed", return_value=False
    )

    patch_check_are_rrsets_deleted = mock.patch(
        "salt.modules.powerdns._check_are_rrsets_deleted", return_value=False
    )

    with patch_request, patch_get_zone, patch_check_are_rrsets_changed, patch_check_are_rrsets_deleted:

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.78"}],
                "type": "A",
                "ttl": 30,
            }
        ]
        nameservers = ["ns1.zone1.com", "ns2.zone2.com"]
        drop_existing = False
        dnssec = True

        result = powerdns.manage_zone(
            name, key, server, rrsets, nameservers, drop_existing, dnssec
        )

    assert result == {
        "changes": {"zone": [{"dnssec": {"new": True, "old": False}}]},
        "name": "zone1.com",
        "result": True,
    }


def test_manage_zone_fails_update_dnssec():

    old_zone = {
        "dnssec": False,
        "rrsets": [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.78"}],
                "type": "A",
                "ttl": 30,
            }
        ],
    }

    mock_put_resp = _mock_response(status=400)
    patch_request = mock.patch(
        "requests.put", return_value=mock_put_resp, autospec=True
    )

    patch_get_zone = mock.patch(
        "salt.modules.powerdns._get_zone", return_value=old_zone
    )

    with patch_request, patch_get_zone:

        with pytest.raises(CommandExecutionError):

            name = "zone1.com"
            key = "TEST_KEY"
            server = "pdns.test.com"
            rrsets = [
                {
                    "name": "zone1.com",
                    "records": [{"content": "12.34.56.78"}],
                    "type": "A",
                    "ttl": 30,
                },
                {
                    "name": "www.zone1.com",
                    "records": [{"content": "zone1.com"}],
                    "type": "cname",
                    "ttl": 7200,
                },
            ]
            nameservers = ["ns1.zone1.com", "ns2.zone2.com"]
            drop_existing = False
            dnssec = True

            powerdns.manage_zone(
                name, key, server, rrsets, nameservers, drop_existing, dnssec
            )


def test_manage_zone_updates_rrsets():

    old_zone = {
        "dnssec": False,
        "rrsets": [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.87"}],
                "type": "A",
                "ttl": 30,
            }
        ],
    }

    mock_patch_resp = _mock_response(status=204)
    patch_request = mock.patch(
        "requests.patch", return_value=mock_patch_resp, autospec=True
    )

    patch_get_zone = mock.patch(
        "salt.modules.powerdns._get_zone", return_value=old_zone
    )

    with patch_request, patch_get_zone:

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.78"}],
                "type": "A",
                "ttl": 30,
            }
        ]
        nameservers = ["ns1.zone1.com", "ns2.zone2.com"]
        drop_existing = False
        dnssec = False

        result = powerdns.manage_zone(
            name, key, server, rrsets, nameservers, drop_existing, dnssec
        )

    assert result == {
        "changes": {
            "records": {
                "deleted": [],
                "modified": [
                    {
                        "zone1.com.": {
                            "new": {"content": ["12.34.56.78"], "ttl": 30},
                            "type": "A",
                        }
                    },
                    {
                        "zone1.com.": {
                            "new": {
                                "content": ["ns1.zone1.com.", "ns2.zone2.com."],
                                "ttl": 3600,
                            },
                            "type": "NS",
                        }
                    },
                ],
            }
        },
        "name": "zone1.com",
        "result": True,
    }


def test_manage_zone_fails_update_rrsets():

    old_zone = {
        "dnssec": False,
        "rrsets": [
            {
                "name": "zone1.com",
                "records": [{"content": "12.34.56.87"}],
                "type": "A",
                "ttl": 30,
            }
        ],
    }

    mock_patch_resp = _mock_response(status=400, json_data="Test data")
    patch_request = mock.patch(
        "requests.patch", return_value=mock_patch_resp, autospec=True
    )

    patch_get_zone = mock.patch(
        "salt.modules.powerdns._get_zone", return_value=old_zone
    )

    with patch_request, patch_get_zone:

        with pytest.raises(CommandExecutionError):

            name = "zone1.com"
            key = "TEST_KEY"
            server = "pdns.test.com"
            rrsets = [
                {
                    "name": "zone1.com",
                    "records": [{"content": "12.34.56.78"}],
                    "type": "A",
                    "ttl": 30,
                }
            ]
            nameservers = ["ns1.zone1.com", "ns2.zone2.com"]
            drop_existing = False
            dnssec = False

            powerdns.manage_zone(
                name, key, server, rrsets, nameservers, drop_existing, dnssec
            )


def test_delete_zone_no_zone():

    name = "zone1.com"
    key = "TEST_KEY"
    server = "pdns.test.com"

    patch_get_zone = mock.patch("salt.modules.powerdns._get_zone", return_value=None)
    with patch_get_zone:

        result = powerdns.delete_zone(name, key, server)

    assert result == {"changes": {}, "name": "zone1.com", "result": True}


def test_delete_zone_sucess():

    mock_patch_resp = _mock_response(status=204, json_data="Test data")
    patch_request = mock.patch(
        "requests.delete", return_value=mock_patch_resp, autospec=True
    )

    patch_get_zone = mock.patch(
        "salt.modules.powerdns._get_zone", return_value={"name": "zone1.com"}
    )

    with patch_request, patch_get_zone:

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"

        result = powerdns.delete_zone(name, key, server)

    assert result == {
        "changes": {"deleted": "zone1.com"},
        "name": "zone1.com",
        "result": True,
    }


def test_delete_zone_fails():

    mock_patch_resp = _mock_response(status=400, json_data="Test data")
    patch_request = mock.patch(
        "requests.delete", return_value=mock_patch_resp, autospec=True
    )

    patch_get_zone = mock.patch(
        "salt.modules.powerdns._get_zone", return_value={"name": "zone1.com"}
    )

    with patch_request, patch_get_zone:

        with pytest.raises(CommandExecutionError):

            name = "zone1.com"
            key = "TEST_KEY"
            server = "pdns.test.com"

            powerdns.delete_zone(name, key, server)

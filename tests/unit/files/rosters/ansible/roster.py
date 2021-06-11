#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import sys

inventory = {
    "usa": {"children": ["southeast"]},
    "southeast": {
        "children": ["atlanta", "raleigh"],
        "vars": {
            "some_server": "foo.southeast.example.com",
            "halon_system_timeout": 30,
            "self_destruct_countdown": 60,
            "escape_pods": 2,
        },
    },
    "raleigh": ["host2", "host3"],
    "atlanta": ["host1", "host2"],
}
hostvars = {"host1": {}, "host2": {}, "host3": {}}

if "--host" in sys.argv:
    print(json.dumps(hostvars.get(sys.argv[-1], {})))
if "--list" in sys.argv:
    print(json.dumps(inventory))

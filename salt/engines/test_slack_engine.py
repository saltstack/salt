def test_group_permissions():
    groups = {
        "default": {
            "users": ["*"],
            "commands": ["test.ping"],
            "aliases": {
                "list_jobs": {
                    "cmd": "jobs.list_jobs",
                },
                "list_commands": {
                    "cmd": "pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list"
                }
            }
        },
        "gods": {
            "users": ["garethgreenaway"],
            "commands": ["*"]
        }
    }
#    assert _can_user_run("pcn", "test.ping", groups), True
#    assert _can_user_run("pcn", "cmd.run", groups), False
#    assert _can_user_run("garethgreenaway", "cmd.run", groups), True

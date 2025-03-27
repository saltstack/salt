import logging
import pathlib
import time
import types

import attr
import pytest

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    monty: python
    os: {{ grains['os'] }}
    {% if grains['os'] == 'Fedora' %}
    class: redhat
    {% else %}
    class: other
    {% endif %}

    knights:
      - Lancelot
      - Galahad
      - Bedevere
      - Robin

    12345:
      code:
        - luggage
    """
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    basic_tempfile = salt_master.pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    )
    try:
        with top_tempfile, basic_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.returncode == 0
            assert ret.data is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


@pytest.mark.slow_test
def test_data(salt_call_cli, pillar_tree):
    """
    pillar.data
    """
    ret = salt_call_cli.run("grains.items")
    assert ret.returncode == 0
    assert ret.data
    grains = ret.data
    ret = salt_call_cli.run("pillar.data")
    assert ret.returncode == 0
    assert ret.data
    pillar = ret.data
    assert pillar["os"] == grains["os"]
    assert pillar["monty"] == "python"
    if grains["os"] == "Fedora":
        assert pillar["class"] == "redhat"
    else:
        assert pillar["class"] == "other"


@pytest.mark.slow_test
def test_issue_5449_report_actual_file_roots_in_pillar(
    salt_call_cli, pillar_tree, base_env_state_tree_root_dir
):
    """
    pillar['master']['file_roots'] is overwritten by the master
    in order to use the fileclient interface to read the pillar
    files. We should restore the actual file_roots when we send
    the pillar back to the minion.
    """
    ret = salt_call_cli.run("pillar.data")
    assert ret.returncode == 0
    assert ret.data
    file_roots = ret.data["master"]["file_roots"]["base"]
    assert pathlib.Path(base_env_state_tree_root_dir).resolve() in [
        pathlib.Path(p).resolve() for p in file_roots
    ]


@pytest.mark.slow_test
def test_ext_cmd_yaml(salt_call_cli, pillar_tree):
    """
    pillar.data for ext_pillar cmd.yaml
    """
    ret = salt_call_cli.run("pillar.data")
    assert ret.returncode == 0
    assert ret.data
    pillar = ret.data
    assert pillar["ext_spam"] == "eggs"


@pytest.mark.slow_test
def test_issue_5951_actual_file_roots_in_opts(
    salt_call_cli, pillar_tree, base_env_state_tree_root_dir
):
    ret = salt_call_cli.run("pillar.data")
    assert ret.returncode == 0
    assert ret.data
    pillar_data = ret.data
    file_roots = pillar_data["ext_pillar_opts"]["file_roots"]["base"]
    assert pathlib.Path(base_env_state_tree_root_dir).resolve() in [
        pathlib.Path(p).resolve() for p in file_roots
    ]


@pytest.mark.slow_test
def test_pillar_items(salt_call_cli, pillar_tree):
    """
    Test to ensure we get expected output
    from pillar.items
    """
    ret = salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    pillar_items = ret.data
    assert "monty" in pillar_items
    assert pillar_items["monty"] == "python"
    assert "knights" in pillar_items
    assert pillar_items["knights"] == ["Lancelot", "Galahad", "Bedevere", "Robin"]


@pytest.mark.slow_test
def test_pillar_command_line(salt_call_cli, pillar_tree):
    """
    Test to ensure when using pillar override
    on command line works
    """
    # test when pillar is overwriting previous pillar
    ret = salt_call_cli.run("pillar.items", pillar={"monty": "overwrite"})
    assert ret.returncode == 0
    assert ret.data
    pillar_items = ret.data
    assert "monty" in pillar_items
    assert pillar_items["monty"] == "overwrite"

    # test when using additional pillar
    ret = salt_call_cli.run("pillar.items", pillar={"new": "additional"})
    assert ret.returncode == 0
    assert ret.data
    pillar_items = ret.data
    assert "new" in pillar_items
    assert pillar_items["new"] == "additional"


def test_pillar_get_integer_key(salt_call_cli, pillar_tree):
    """
    Test to ensure we get expected output
    from pillar.items
    """
    ret = salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    pillar_items = ret.data
    assert "12345" in pillar_items
    assert pillar_items["12345"] == {"code": ["luggage"]}

    ret = salt_call_cli.run("pillar.get", key="12345")
    assert ret.returncode == 0
    assert ret.data
    pillar_get = ret.data
    assert "code" in pillar_get
    assert "luggage" in pillar_get["code"]


@attr.s
class PillarRefresh:
    master = attr.ib(repr=False)
    minion_id = attr.ib(repr=False)
    pillar_key = attr.ib()
    top_file = attr.ib(init=False, default=None)
    minion_1_pillar = attr.ib(init=False, default=None)

    def refresh_pillar(self, timeout=60):
        ret = self.master.salt_cli().run(
            "saltutil.refresh_pillar",
            wait=True,
            minion_tgt=self.minion_id,
            _timeout=timeout,
        )
        assert ret.returncode == 0
        assert ret.data is True

    def __enter__(self):
        top_file_contents = """
        base:
          {}:
            - minion-1-pillar
        """.format(
            self.minion_id
        )
        self.top_file = self.master.pillar_tree.base.temp_file(
            "top.sls", top_file_contents
        )
        self.minion_1_pillar = self.master.pillar_tree.base.temp_file(
            "minion-1-pillar.sls", f"{self.pillar_key}: true"
        )
        self.top_file.__enter__()
        self.minion_1_pillar.__enter__()
        return self

    def __exit__(self, *args):
        if self.top_file:
            self.top_file.__exit__(*args)
        if self.minion_1_pillar:
            self.minion_1_pillar.__exit__(*args)
            self.minion_1_pillar = None
        self.refresh_pillar()


@pytest.fixture
def key_pillar(salt_master, salt_minion):
    def _key_pillar(key):
        return PillarRefresh(
            master=salt_master, minion_id=salt_minion.id, pillar_key=key
        )

    return _key_pillar


@pytest.mark.slow_test
def test_pillar_refresh_pillar_raw(salt_cli, salt_minion, key_pillar):
    """
    Validate the minion's pillar.raw call behavior for new pillars
    """
    key = "issue-54941-raw"

    # We do not expect to see the pillar because it does not exist yet
    ret = salt_cli.run("pillar.raw", key, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    val = ret.data
    assert val == {}

    with key_pillar(key) as key_pillar_instance:
        # The pillar exists now but raw reads it from in-memory pillars
        ret = salt_cli.run("pillar.raw", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert val == {}

        # Calling refresh_pillar to update in-memory pillars
        key_pillar_instance.refresh_pillar()

        # The pillar can now be read from in-memory pillars
        ret = salt_cli.run("pillar.raw", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert val is True, repr(val)


@pytest.mark.slow_test
def test_pillar_refresh_pillar_get(salt_cli, salt_minion, key_pillar):
    """
    Validate the minion's pillar.get call behavior for new pillars
    """
    key = "issue-54941-get"

    # We do not expect to see the pillar because it does not exist yet
    ret = salt_cli.run("pillar.get", key, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    val = ret.data
    assert val == ""

    with key_pillar(key) as key_pillar_instance:
        # The pillar exists now but get reads it from in-memory pillars, no
        # refresh happens
        ret = salt_cli.run("pillar.get", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert val == ""

        # Calling refresh_pillar to update in-memory pillars
        key_pillar_instance.refresh_pillar()

        # The pillar can now be read from in-memory pillars
        ret = salt_cli.run("pillar.get", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert val is True, repr(val)


@pytest.mark.slow_test
def test_pillar_refresh_pillar_item(salt_cli, salt_minion, key_pillar):
    """
    Validate the minion's pillar.item call behavior for new pillars
    """
    key = "issue-54941-item"

    # We do not expect to see the pillar because it does not exist yet
    ret = salt_cli.run("pillar.item", key, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    val = ret.data
    assert key in val
    assert val[key] == ""

    with key_pillar(key) as key_pillar_instance:
        # The pillar exists now but get reads it from in-memory pillars, no
        # refresh happens
        ret = salt_cli.run("pillar.item", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert key in val
        assert val[key] == ""

        # Calling refresh_pillar to update in-memory pillars
        key_pillar_instance.refresh_pillar()

        # The pillar can now be read from in-memory pillars
        ret = salt_cli.run("pillar.item", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert key in val
        assert val[key] is True


@pytest.mark.slow_test
def test_pillar_refresh_pillar_items(salt_cli, salt_minion, key_pillar):
    """
    Validate the minion's pillar.item call behavior for new pillars
    """
    key = "issue-54941-items"

    # We do not expect to see the pillar because it does not exist yet
    ret = salt_cli.run("pillar.items", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    val = ret.data
    assert key not in val

    with key_pillar(key) as key_pillar_instance:
        # A pillar.items call sees the pillar right away because a
        # refresh_pillar event is fired.
        ret = salt_cli.run("pillar.items", minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert key in val
        assert val[key] is True


@pytest.mark.slow_test
def test_pillar_refresh_pillar_ping(salt_cli, salt_minion, key_pillar):
    """
    Validate the minion's test.ping does not update pillars

    See: https://github.com/saltstack/salt/issues/54941
    """
    key = "issue-54941-ping"

    # We do not expect to see the pillar because it does not exist yet
    ret = salt_cli.run("pillar.item", key, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    val = ret.data
    assert key in val
    assert val[key] == ""

    with key_pillar(key) as key_pillar_instance:
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert val is True

        # The pillar exists now but get reads it from in-memory pillars, no
        # refresh happens
        ret = salt_cli.run("pillar.item", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert key in val
        assert val[key] == ""

        # Calling refresh_pillar to update in-memory pillars
        key_pillar_instance.refresh_pillar()

        # The pillar can now be read from in-memory pillars
        ret = salt_cli.run("pillar.item", key, minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        val = ret.data
        assert key in val
        assert val[key] is True


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(120)
def test_pillar_refresh_pillar_scheduler(salt_master, salt_cli, salt_minion):
    """
    Ensure schedule jobs in pillar are only updated when values change.
    """

    top_sls = """
        base:
          '{}':
            - test_schedule
        """.format(
        salt_minion.id
    )

    test_schedule_sls = """
        schedule:
          first_test_ping:
            function: test.ping
            run_on_start: True
            seconds: 3600
        """

    test_schedule_sls2 = """
        schedule:
          first_test_ping:
            function: test.ping
            run_on_start: True
            seconds: 7200
        """

    with salt_master.pillar_tree.base.temp_file("top.sls", top_sls):
        with salt_master.pillar_tree.base.temp_file(
            "test_schedule.sls", test_schedule_sls
        ):
            # Calling refresh_pillar to update in-memory pillars
            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            # Give the schedule a chance to run the job
            time.sleep(5)

            # Get the status of the job
            ret = salt_cli.run(
                "schedule.job_status", name="first_test_ping", minion_tgt=salt_minion.id
            )
            assert "_next_fire_time" in ret.data
            _next_fire_time = ret.data["_next_fire_time"]

            # Refresh pillar
            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            # Ensure next_fire_time is the same, job was not replaced
            ret = salt_cli.run(
                "schedule.job_status", name="first_test_ping", minion_tgt=salt_minion.id
            )
            assert ret.data["_next_fire_time"] == _next_fire_time

        # Ensure job was replaced when seconds changes
        with salt_master.pillar_tree.base.temp_file(
            "test_schedule.sls", test_schedule_sls2
        ):
            # Calling refresh_pillar to update in-memory pillars
            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            # Give the schedule a chance to run the job
            time.sleep(5)

            ret = salt_cli.run(
                "schedule.job_status", name="first_test_ping", minion_tgt=salt_minion.id
            )
            assert "_next_fire_time" in ret.data
            _next_fire_time = ret.data["_next_fire_time"]

            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            ret = salt_cli.run(
                "schedule.job_status", name="first_test_ping", minion_tgt=salt_minion.id
            )
            assert ret.data["_next_fire_time"] == _next_fire_time

    # Refresh pillar once we're done
    salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id)


@pytest.mark.slow_test
@pytest.mark.parametrize(
    "jinja_file,app,caching,db",
    [
        ("test_jinja_sls_as_documented", True, True, False),
        ("test_jinja_sls_with_minion_id", False, False, True),
        ("test_jinja_sls_with_minion_id_regex_compound", False, False, True),
    ],
)
def test_pillar_match_filter_by_minion_id(
    salt_master, salt_cli, salt_minion, jinja_file, app, caching, db
):
    """
    Ensure "match.filter_by" used during Pillar rendering uses the Minion ID and
    returns the expected values
    """
    top_sls = """
    base:
      {}:
        - test_jinja
    """.format(
        salt_minion.id
    )

    sls_files = {
        "test_jinja_sls_as_documented": """
    # Filter the data for the current minion into a variable:
    {{% set roles = salt['match.filter_by']({{
        'web*': ['app', 'caching'],
        '{}*': ['db'],
    }}, default='web*') %}}

    # Make the filtered data available to Pillar:
    roles: {{{{ roles | yaml() }}}}
    """.format(
            salt_minion.id
        ),
        "test_jinja_sls_with_minion_id": """
    # Filter the data for the current minion into a variable:
    {{% set roles = salt['match.filter_by']({{
        'web*': ['app', 'caching'],
        '{}*': ['db'],
    }}, minion_id=grains['id'], default='web*') %}}

    # Make the filtered data available to Pillar:
    roles: {{{{ roles | yaml() }}}}
    """.format(
            salt_minion.id
        ),
        "test_jinja_sls_with_minion_id_regex_compound": """
    # Filter the data for the current minion into a variable:
    {{% set roles = salt['match.filter_by']({{
        'web*': ['app', 'caching'],
        'E@{}': ['db'],
    }}, minion_id=grains['id'], default='web*') %}}

    # Make the filtered data available to Pillar:
    roles: {{{{ roles | yaml() }}}}
    """.format(
            salt_minion.id
        ),
    }

    # test the brokenness of the currently documented example
    # it lacks the "minion_id" argument for "match.filter_by" and thereby
    # assigns the wrong roles
    with salt_master.pillar_tree.base.temp_file("top.sls", top_sls):
        with salt_master.pillar_tree.base.temp_file(
            "test_jinja.sls", sls_files[jinja_file]
        ):
            # Calling refresh_pillar to update in-memory pillars
            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            # Get the Minion's Pillar
            ret = salt_cli.run("pillar.get", "roles", minion_tgt=salt_minion.id)
            if app:
                assert "app" in ret.data
            else:
                assert "app" not in ret.data

            if caching:
                assert "caching" in ret.data
            else:
                assert "caching" not in ret.data

            if db:
                assert "db" in ret.data
            else:
                assert "db" not in ret.data

    # Refresh pillar once we're done
    salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id)


@pytest.mark.slow_test
def test_pillar_ext_59975(salt_call_cli):
    """
    pillar.ext returns result. Issue #59975
    """
    ret = salt_call_cli.run("pillar.ext", '{"libvert": _}')
    assert "ext_pillar_opts" in ret.data


@pytest.fixture
def event_listerner_timeout(grains):
    if grains["os"] == "Windows":
        if grains["osrelease"].startswith("2019"):
            return types.SimpleNamespace(catch=120, miss=30)
        return types.SimpleNamespace(catch=90, miss=10)
    return types.SimpleNamespace(catch=60, miss=10)


@pytest.mark.slow_test
def test_pillar_refresh_pillar_beacons(
    base_env_pillar_tree_root_dir,
    salt_cli,
    salt_minion,
    salt_master,
    event_listener,
    event_listerner_timeout,
):
    """
    Ensure beacons jobs in pillar are started after
    a pillar refresh and then not running when pillar
    is cleared.
    """

    top_sls = """
        base:
          '{}':
            - test_beacons
        """.format(
        salt_minion.id
    )

    test_beacons_sls_empty = ""

    test_beacons_sls = """
        beacons:
          status:
            - loadavg:
              - 1-min
        """

    assert salt_minion.is_running()

    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_sls, base_env_pillar_tree_root_dir
    )
    beacon_tempfile = pytest.helpers.temp_file(
        "test_beacons.sls", test_beacons_sls_empty, base_env_pillar_tree_root_dir
    )

    with top_tempfile, beacon_tempfile:
        # Calling refresh_pillar to update in-memory pillars
        salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id)

        # Ensure beacons start when pillar is refreshed
        with salt_master.pillar_tree.base.temp_file(
            "test_beacons.sls", test_beacons_sls
        ):
            # Calling refresh_pillar to update in-memory pillars
            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            # Give the beacons a chance to start
            time.sleep(5)

            event_tag = "salt/beacon/*/status/*"
            start_time = time.time()

            event_pattern = (salt_master.id, event_tag)
            matched_events = event_listener.wait_for_events(
                [event_pattern],
                after_time=start_time,
                timeout=event_listerner_timeout.catch,
            )

            assert matched_events.found_all_events

        # Ensure beacons sttop when pillar is refreshed
        with salt_master.pillar_tree.base.temp_file(
            "test_beacons.sls", test_beacons_sls_empty
        ):
            # Calling refresh_pillar to update in-memory pillars
            salt_cli.run(
                "saltutil.refresh_pillar", wait=True, minion_tgt=salt_minion.id
            )

            # Give the beacons a chance to stop
            time.sleep(5)

            event_tag = "salt/beacon/*/status/*"
            start_time = time.time()

            event_pattern = (salt_master.id, event_tag)
            matched_events = event_listener.wait_for_events(
                [event_pattern],
                after_time=start_time,
                timeout=event_listerner_timeout.miss,
            )

            assert not matched_events.found_all_events

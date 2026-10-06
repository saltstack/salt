import textwrap

import pytest


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {
        "file_client": "local",
        "master_type": "disable",
        "state_aggregate": True,
    }


@pytest.fixture(scope="module", autouse=True)
def nop_aggregate_mod(loaders, state_tree):
    mod_contents = textwrap.dedent(
        """
        __virtualname__ = "aggr"


        def __virtual__():
            return __virtualname__


        def test(name, aggrs=None, **kwargs):
            return {
                "name": name,
                "result": True,
                "comment": "",
                "changes": {
                    "aggrs": aggrs or [name]
                },
            }


        def mod_aggregate(low, chunks, running):
            # modeled after the pkg state module
            aggrs = []
            for chunk in chunks:
                tag = __utils__["state.gen_tag"](chunk)
                if tag in running:
                    # Already ran
                    continue
                if chunk.get("state") == "aggr":
                    if "__agg__" in chunk:
                        continue
                    # Check for the same function
                    if chunk.get("fun") != low.get("fun"):
                        continue

                    if "aggrs" in chunk:
                        aggrs.extend(chunk["aggrs"])
                        chunk["__agg__"] = True
                    elif "name" in chunk:
                        aggrs.append(chunk["name"])
                        chunk["__agg__"] = True
            if aggrs:
                if "aggrs" in low:
                    low["aggrs"].extend(aggrs)
                else:
                    low["aggrs"] = aggrs
            return low
    """
    )
    with pytest.helpers.temp_file("aggrs.py", mod_contents, state_tree / "_states"):
        res = loaders.modules.saltutil.sync_all()
        assert "states" in res
        assert "states.aggrs" in res["states"]
        loaders.reload_all()
        assert hasattr(loaders.states, "aggr")
        yield
    loaders.modules.saltutil.sync_all()
    loaders.reload_all()


def test_aggregate_requisites(state_tree, modules):
    """Test to ensure that aggregated states honor requisites"""
    sls_name = "requisite_aggregate_test"
    sls_contents = """
    "packages 1":
      aggr.test:
        - aggrs:
          - hello
    "listen to packages 2":
      test.succeed_with_changes:
        - listen:
          - "packages 2"
    "packages 2":
      aggr:
        - test
        - aggrs:
          - cowsay
          - fortune-mod
        - require:
          - "requirement"
    "packages 3":
      aggr.test:
        - name: cowsay
        - require:
          - "test": "requirement"
    "requirement":
      test.nop:
        - name: "requirement_name"
    """
    sls_tempfile = pytest.helpers.temp_file(f"{sls_name}.sls", sls_contents, state_tree)
    with sls_tempfile:
        # Apply the state file
        ret = modules.state.apply(sls_name)

        # Check the results
        assert not ret.failed
        expected_order = [
            "aggr_|-packages 1_|-packages 1_|-test",
            "test_|-listen to packages 2_|-listen to packages 2_|-succeed_with_changes",
            "test_|-requirement_|-requirement_name_|-nop",
            "aggr_|-packages 2_|-packages 2_|-test",
            "aggr_|-packages 3_|-cowsay_|-test",
            "test_|-listener_listen to packages 2_|-listen to packages 2_|-mod_watch",
        ]
        for index, state_run in enumerate(ret):
            assert state_run.result is True
            assert expected_order[index] in state_run.raw

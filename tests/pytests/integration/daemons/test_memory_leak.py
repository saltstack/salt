import time

import pytest

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

pytestmark = [
    pytest.mark.skipif(not HAS_PSUTIL, reason="Need psutil to test memory leak"),
    pytest.mark.slow_test,
]


@pytest.fixture
def testfile_path(tmp_path):
    return tmp_path / "testfile"


@pytest.fixture
def file_add_sls(testfile_path, base_env_state_tree_root_dir):
    sls_name = "file_add"
    sls_contents = """
    {}:
      file.managed:
        - source: salt://testfile
        - makedirs: true
    """.format(
        testfile_path
    )
    with pytest.helpers.temp_file(
        "{}.sls".format(sls_name), sls_contents, base_env_state_tree_root_dir
    ):
        yield sls_name


@pytest.fixture
def file_delete_sls(testfile_path, base_env_state_tree_root_dir):
    sls_name = "file_delete"
    sls_contents = """
    delete_file:
      file.absent:
        - name: {}
    """.format(
        testfile_path
    )
    with pytest.helpers.temp_file(
        "{}.sls".format(sls_name), sls_contents, base_env_state_tree_root_dir
    ):
        yield sls_name


@pytest.mark.flaky(max_runs=4)
def test_memory_leak(salt_cli, salt_minion, file_add_sls, file_delete_sls):
    usage_ts_data = []
    max_ts_points = 100

    # Try to drive up memory usage
    for i in range(4):
        salt_cli.run("state.sls", file_add_sls, minion_tgt=salt_minion.id)
        salt_cli.run("state.sls", file_delete_sls, minion_tgt=salt_minion.id)

    while len(usage_ts_data) < max_ts_points:
        usg = psutil.virtual_memory()
        usage_ts_data.append((time.time(), usg.total - usg.available))
        time.sleep(0.05)

    # find the slope of the simple SSE linear regression
    y_bar = sum(y for y, y in usage_ts_data) / len(usage_ts_data)
    x_bar = sum(x for x, y in usage_ts_data) / len(usage_ts_data)
    numerator = sum(x * y - y_bar * x for x, y in usage_ts_data)
    denominator = sum(x * x - x_bar * x for x, y in usage_ts_data)
    slope = numerator / denominator
    assert slope <= 0

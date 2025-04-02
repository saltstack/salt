import multiprocessing
import time

import psutil
import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(360),
    pytest.mark.skip_on_fips_enabled_platform,
    pytest.mark.skip_on_windows(reason="Windows is a spawning platform, won't work"),
    pytest.mark.skip_on_darwin(reason="MacOS is a spawning platform, won't work"),
    pytest.mark.skipif(
        True,
        reason="Test has become too unstable to test",
    ),
    pytest.mark.skipif(
        'grains["osfinger"] == "Fedora Linux-39"',
        reason="vim package not available for this distribution",
    ),
]


@pytest.fixture
def file_add_delete_sls(tmp_path, salt_master):
    path = tmp_path / "testfile"
    sls_name = "file_add"
    sls_contents = f"""
    add_file:
      file.managed:
        - name: {path}
        - source: salt://testfile
        - makedirs: true
        - require:
          - cmd: echo

    delete_file:
      file.absent:
        - name: {path}
        - require:
          - file: add_file

    echo:
      cmd.run:
        - name: \"echo 'This is a test!'\"
    """
    with salt_master.state_tree.base.temp_file(f"{sls_name}.sls", sls_contents):
        yield sls_name


# This test is fundimentally flawed. Needs to be re-factored to test the memory
# consuption of the minoin process not system wide memory.
@pytest.mark.skip(reason="Flawed test")
def test_memory_leak(salt_cli, salt_minion, file_add_delete_sls):
    max_usg = None

    # Using shared variables to be able to send a stop flag to the process
    with multiprocessing.Manager() as manager:
        done_flag = manager.list()
        during_run_data = manager.list()

        def _func(data, flag):
            while len(flag) == 0:
                time.sleep(0.05)
                usg = psutil.virtual_memory()
                data.append(usg.total - usg.available)

        proc = multiprocessing.Process(target=_func, args=(during_run_data, done_flag))
        proc.start()

        # Try to drive up memory usage
        for _ in range(50):
            salt_cli.run("state.sls", file_add_delete_sls, minion_tgt=salt_minion.id)

        done_flag.append(1)
        proc.join()

        start_usg = during_run_data[0]
        max_usg = during_run_data[0]
        for row in during_run_data[1:]:
            max_usg = row if row >= max_usg else max_usg

    # This would be weird, but should account for it
    if max_usg > start_usg:
        max_tries = 50
        # The maximum that the current usage can be in order to pass the test
        threshold = (max_usg - start_usg) * 0.25 + start_usg
        for _ in range(max_tries):
            usg = psutil.virtual_memory()
            current_usg = usg.total - usg.available
            if current_usg <= start_usg:
                break
            # Get percent difference between max and start usg that current usg is at
            if current_usg <= threshold:
                break

            time.sleep(2)
        else:
            pytest.fail("Memory usage did not drop off appropriately")

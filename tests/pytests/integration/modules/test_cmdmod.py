import pytest
import tempfile
import os


@pytest.fixture(scope="module")
def non_root_account():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.mark.skip_if_not_root
def test_exec_code_all(salt_call_cli, non_root_account):
    ret = salt_call_cli.run(
        "cmd.exec_code_all", "bash", "echo good", runas=non_root_account.username
    )
    assert ret.returncode == 0


def test_long_stdout(salt_cli, salt_minion):
    echo_str = "salt" * 1000
    ret = salt_cli.run(
        "cmd.run", f"echo {echo_str}", use_vt=True, minion_tgt=salt_minion.id
    )
    assert ret.returncode == 0
    assert len(ret.data.strip()) == len(echo_str)


@pytest.fixture()
def test_script_path():
    """
    Create a temporary shell script that echoes its arguments.
    
    This fixture sets up a temporary shell script, makes it executable,
    and yields the path to the script for use in tests. After the test
    completes, the temporary file is automatically removed.
    
    Yields:
        str: The path to the temporary shell script.
    """
    script_content = "#!/bin/bash\necho $*"

    with tempfile.NamedTemporaryFile(mode='w', suffix='-salt_echo_num.sh') as temp_script:
        temp_script.write(script_content)
        temp_script_path = temp_script.name
    
        # Make the script executable
        os.chmod(temp_script_path, 0o755)  
        

        yield temp_script_path


def test_script_with_falsey_args(subtests, salt_call_cli, test_script_path):
    """
    Test `cmd.script` with various falsey arguments to ensure correct handling.
    
    This test runs the temporary shell script with a variety of arguments
    that evaluate to false in Python. It uses subtests to individually test
    each falsey argument and checks that the script outputs the argument correctly.
    
    Args:
        subtests (SubTests): The subtests fixture for running parameterized tests.
        salt_call_cli (SaltCallCLI): The salt CLI fixture for running salt commands.
        test_script_path (str): The path to the temporary shell script.
    """
    # List of values to test that evaluate to `False` when used in python conditionals
    falsey_values = ["0", "", "''", "\"\"", "()", "[]", "{}", "False", "None"]

    for value in falsey_values:
        expected_output = str(value).strip('"').strip("'")
        with subtests.test(f"The script should print '{expected_output}' for input '{value}'", value=value):
            # Run the script with the current falsey value as an argument
            ret = salt_call_cli.run("--local", "cmd.script", f"file://{test_script_path}", str(value))

            # Check that the script ran successfully and printed the expected output
            assert ret.returncode == 0, f"The script failed to run with argument: {value}"

            # Verify that the script's output matches the expected output
            assert expected_output in ret.json["stdout"]
            
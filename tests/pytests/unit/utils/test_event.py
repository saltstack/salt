import pytest
import salt.utils.event


@pytest.mark.parametrize("keep_loop", [True, False])
def test_keep_loop_should_be_passed_correctly_when_getting_a_MasterEvent(keep_loop):
    # This is a very basic test that is *almost* meaningless. It would be much
    # better to test the actual behavior of the MasterEvent both with & without
    # providing keep_loop. However, that would require more investment in
    # testing than could currently be spared.
    #
    # When migrating the exiting unit tests to pytest, that's when this should
    # be replaced with something more meaningful.
    event = salt.utils.event.get_master_event(
        {"transport": "tcp"}, None, None, None, None, keep_loop=keep_loop
    )

    assert event.keep_loop == keep_loop

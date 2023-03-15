import pytest
from pytestshellutils.utils.processes import terminate_process

import salt.ext.tornado.ioloop
import salt.utils.event
import salt.utils.stringutils


@pytest.mark.slow_test
def test_event_return(master_opts):
    evt = None
    try:
        evt = salt.utils.event.EventReturn(master_opts)
        evt.start()
    except TypeError as exc:
        if "object" in str(exc):
            pytest.fail("'{}' TypeError should have not been raised".format(exc))
    finally:
        if evt is not None:
            terminate_process(evt.pid, kill_children=True)

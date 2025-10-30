import asyncio

import salt.utils.asynchronous as asynchronous


class HelperA:

    async_methods = [
        "sleep",
    ]

    def __init__(self, io_loop=None):
        pass

    async def sleep(self):
        await asyncio.sleep(0.1)
        return True


class HelperB:

    async_methods = [
        "sleep",
    ]

    def __init__(self, a=None, io_loop=None):
        if a is None:
            a = asynchronous.SyncWrapper(HelperA)
        self.a = a

    async def sleep(self):
        await asyncio.sleep(0.1)
        self.a.sleep()
        return False


def test_helpers():
    """
    Test that the helper classes do what we expect within a regular asynchronous env
    """
    loop = asyncio.new_event_loop()
    try:
        ret = loop.run_until_complete(HelperA().sleep())
    finally:
        loop.close()
    assert ret is True

    loop = asyncio.new_event_loop()
    try:
        ret = loop.run_until_complete(HelperB().sleep())
    finally:
        loop.close()
    assert ret is False


def test_basic_wrap():
    """
    Test that we can wrap an asynchronous caller.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    ret = sync.sleep()
    assert ret is True


def test_basic_wrap_series():
    """
    Test that we can wrap an asynchronous caller and call the method in series.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    ret = sync.sleep()
    assert ret is True
    ret = sync.sleep()
    assert ret is True


def test_double():
    """
    Test when the asynchronous wrapper object itself creates a wrap of another thing

    This works fine since the second wrap is based on the first's IOLoop so we
    don't have to worry about complex start/stop mechanics
    """
    sync = asynchronous.SyncWrapper(HelperB)
    ret = sync.sleep()
    assert ret is False


def test_double_sameloop():
    """
    Test asynchronous wrappers initiated from the same IOLoop, to ensure that
    we don't wire up both to the same IOLoop (since it causes MANY problems).
    """
    a = asynchronous.SyncWrapper(HelperA)
    sync = asynchronous.SyncWrapper(HelperB, (a,))
    ret = sync.sleep()
    assert ret is False

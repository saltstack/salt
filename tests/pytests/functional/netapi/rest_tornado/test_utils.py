import tornado.concurrent

from salt.netapi.rest_tornado import saltnado


async def test_any_future():
    """
    Test that the Any Future does what we think it does
    """
    # create a few futures
    futures = []
    for _ in range(3):
        future = tornado.concurrent.Future()
        futures.append(future)

    # create an any future, make sure it isn't immediately done
    any_ = saltnado.Any(futures)
    assert any_.done() is False

    # finish one, lets see who finishes
    futures[0].set_result("foo")

    await futures[0]
    await any_

    assert any_.done() is True
    assert futures[0].done() is True
    assert futures[1].done() is False
    assert futures[2].done() is False

    # make sure it returned the one that finished
    assert any_.result() == futures[0]

    futures = futures[1:]
    # re-wait on some other futures
    any_ = saltnado.Any(futures)
    futures[0].set_result("foo")
    await futures[0]
    await any_

    assert any_.done() is True
    assert futures[0].done() is True
    assert futures[1].done() is False

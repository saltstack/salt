import salt.ext.tornado.gen


def run_loop_in_thread(loop, evt):
    """
    Run the provided loop until an event is set
    """
    loop.make_current()

    @salt.ext.tornado.gen.coroutine
    def stopper():
        while True:
            if evt.is_set():
                loop.stop()
                break
            yield salt.ext.tornado.gen.sleep(0.3)

    loop.add_callback(stopper)
    try:
        loop.start()
    finally:
        loop.close()

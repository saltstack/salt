import tornado.gen


def run_loop_in_thread(loop, evt):
    """
    Run the provided loop until an event is set
    """
    loop.make_current()

    @tornado.gen.coroutine
    def stopper():
        while True:
            if evt.is_set():
                loop.stop()
                break
            yield tornado.gen.sleep(0.3)

    loop.add_callback(stopper)
    try:
        loop.start()
    finally:
        loop.close()

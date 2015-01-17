#

class LoggingHandler(object):
    def __init__(self, level):
        pass

    def setLevel(self, x):
        pass

    def setFormatter(self, x):
        pass

class TemporaryLoggingHandler(LoggingHandler):
    def __init__(self, level):
        pass


class StreamHandler(LoggingHandler):
    pass

class SysLogHandler(LoggingHandler):
    pass

class WatchedFileHandler(LoggingHandler):
    def __init__(self, log_path, mode, encoding, delay):
        pass

class FileHandler(LoggingHandler):
    pass

class MemoryHandler(LoggingHandler):
    pass

class DatagramHandler(LoggingHandler):
    pass

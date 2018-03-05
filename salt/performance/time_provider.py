import time


class TimestampProvider(object):
    @staticmethod
    def get_now():
        return time.time() * 1e3  # seconds -> milliseconds

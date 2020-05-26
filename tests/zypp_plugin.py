# -*- coding: utf-8 -*-
"""
Related to zypp_plugins_test.py module.
"""


class Plugin(object):
    """
    Bogus module for Zypp Plugins tests.
    """

    def ack(self):
        """
        Acknowledge that the plugin had finished the transaction
        Returns:

        """

    def main(self):
        """
        Register plugin
        Returns:

        """


class BogusIO(object):
    """
    Read/write logger.
    """

    def __init__(self):
        self.content = list()
        self.closed = False

    def __str__(self):
        return "\n".join(self.content)

    def __call__(self, *args, **kwargs):
        self.path, self.mode = args
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __enter__(self):
        return self

    def write(self, data):
        """
        Simulate writing data
        Args:
            data:

        Returns:

        """
        self.content.append(data)

    def close(self):
        """
        Simulate closing the IO object.
        Returns:

        """
        self.closed = True

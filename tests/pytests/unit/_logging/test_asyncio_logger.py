"""
Tests to ensure asyncio logger uses SaltLoggingClass
"""

import logging


def test_asyncio_logger_saltloggingclass():
    """
    Test that the asyncio logger is an instance of SaltLoggingClass

    It is imported before salt._logging so we need to ensure it is overridden
    """

    asyncio_logger = logging.getLogger("asyncio")

    import salt._logging.impl

    assert isinstance(asyncio_logger, salt._logging.impl.SaltLoggingClass)

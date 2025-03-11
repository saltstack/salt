import salt.channel.client


def test_async_methods():
    "Validate all defined async_methods and close_methods are present"
    async_classes = [
        salt.channel.client.AsyncReqChannel,
        salt.channel.client.AsyncPubChannel,
    ]
    method_attrs = [
        "async_methods",
        "close_methods",
    ]
    for cls in async_classes:
        for attr in method_attrs:
            assert hasattr(cls, attr)
            assert isinstance(getattr(cls, attr), list)
            for name in getattr(cls, attr):
                assert hasattr(cls, name)

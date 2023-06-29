import warnings

from salt.utils.decorators.extension_deprecation import extension_deprecation_message


@extension_deprecation_message(3009, "salt_mod", "http://www.example.com")
def salt_func():
    return True


@extension_deprecation_message(3009, "salt_mod", "http://www.example.com")
def get_configured_provider():
    return True


def test_extension_deprecation():
    """
    this tests the extension_deprecation_message decorator to
    ensure that the warning is raised when a decorated function
    is called.
    """
    expected_deprecation_message = (
        "The 'salt_mod' functionality in Salt has been deprecated and "
        "its functionality will be removed in version 3009.0 (Potassium) "
        "in favor of the saltext.salt_mod Salt Extension. (http://www.example.com)"
    )
    with warnings.catch_warnings(record=True) as catch_warnings:
        ret = salt_func()
        assert ret
        assert len(catch_warnings) == 1
        assert issubclass(catch_warnings[-1].category, DeprecationWarning)
        assert str(catch_warnings[-1].message) == expected_deprecation_message

    with warnings.catch_warnings(record=True) as catch_warnings:
        ret = get_configured_provider()
        assert ret
        assert len(catch_warnings) == 0

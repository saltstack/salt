"""
Verify that the kwargs documented in the ``http.query`` execution module
docstring are real keyword arguments of :func:`salt.utils.http.query`.

If a kwarg is renamed, removed, or replaced, this test fails and the
documentation must be updated to match.
"""

import inspect

import pytest

import salt.utils.http

# Names that ``salt/modules/http.py``'s docstring promises to forward to
# salt.utils.http.query. Grouped only for readability.
DOCUMENTED_KWARGS = [
    # request
    "method",
    "params",
    "data",
    "data_file",
    "data_render",
    "data_renderer",
    "template_dict",
    # headers
    "header_dict",
    "header_list",
    "header_file",
    "header_render",
    "header_renderer",
    # authentication
    "username",
    "password",
    "auth",
    "cert",
    # tls
    "verify_ssl",
    "ca_bundle",
    # cookies and sessions
    "cookies",
    "cookie_jar",
    "cookie_format",
    "persist_session",
    "session_cookie_jar",
    # response decoding
    "decode",
    "decode_type",
    "decode_body",
    "text",
    "status",
    "headers",
    # streaming
    "stream",
    "streaming_callback",
    "header_callback",
    # output capture
    "text_out",
    "headers_out",
    "decode_out",
    # form data
    "formdata",
    "formdata_fieldname",
    "formdata_filename",
    # transport
    "backend",
    "agent",
    "port",
    "handle",
    # error handling
    "raise_error",
    # sensitive data
    "hide_fields",
    # test mode
    "test",
    "test_url",
]


@pytest.mark.parametrize("kwarg", DOCUMENTED_KWARGS)
def test_documented_http_query_kwarg_is_real(kwarg):
    """Each documented kwarg name must appear in salt.utils.http.query()."""
    sig = inspect.signature(salt.utils.http.query)
    assert kwarg in sig.parameters, (
        f"http.query docstring references {kwarg!r} but it is not a real "
        f"parameter of salt.utils.http.query"
    )

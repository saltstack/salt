.. _tutorial-http:

HTTP Modules
============

This tutorial demonstrates using the various HTTP modules available in Salt.
These modules wrap the Python ``tornado``, ``urllib2``, and ``requests``
libraries, extending them in a manner that is more consistent with Salt
workflows.

The ``salt.utils.http`` Library
-------------------------------

This library forms the core of the HTTP modules. Since it is designed to be used
from the minion as an execution module, in addition to the master as a runner,
it was abstracted into this multi-use library. This library can also be imported
by 3rd-party programs wishing to take advantage of its extended functionality.

Core functionality of the execution, state, and runner modules is derived from
this library, so common usages between them are described here. Documentation
specific to each module is described below.

This library can be imported with:

.. code-block:: python

    import salt.utils.http

Configuring Libraries
~~~~~~~~~~~~~~~~~~~~~

This library can make use of either ``tornado``, which is required by Salt,
``urllib2``, which ships with Python, or ``requests``, which can be installed
separately. By default, ``tornado`` will be used. In order to switch to
``urllib2``, set the following variable:

.. code-block:: yaml

    backend: urllib2

In order to switch to ``requests``, set the following variable:

.. code-block:: yaml

    backend: requests

This can be set in the master or minion configuration file, or passed as an
option directly to any ``http.query()`` functions.


``salt.utils.http.query()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function forms a basic query, but with some add-ons not present in the
``tornado``, ``urllib2``, and ``requests`` libraries. Not all functionality
currently available in these libraries has been added, but can be in future
iterations.

HTTPS Request Methods
`````````````````````

A basic query can be performed by calling this function with no more than a
single URL:

.. code-block:: python

    salt.utils.http.query("http://example.com")

By default the query will be performed with a ``GET`` method. The method can
be overridden with the ``method`` argument:

.. code-block:: python

    salt.utils.http.query("http://example.com/delete/url", "DELETE")

When using the ``POST`` method (and others, such as ``PUT``), extra data is usually
sent as well. This data can be sent directly (would be URL encoded when necessary),
or in whatever format is required by the remote server (XML, JSON, plain text, etc).

.. code-block:: python

    salt.utils.http.query(
        "http://example.com/post/url", method="POST", data=json.dumps(mydict)
    )

Data Formatting and Templating
``````````````````````````````

Bear in mind that the data must be sent pre-formatted; this function will not
format it for you. However, a templated file stored on the local system may be
passed through, along with variables to populate it with. To pass through only
the file (untemplated):

.. code-block:: python

    salt.utils.http.query(
        "http://example.com/post/url", method="POST", data_file="/srv/salt/somefile.xml"
    )

To pass through a file that contains jinja + yaml templating (the default):

.. code-block:: python

    salt.utils.http.query(
        "http://example.com/post/url",
        method="POST",
        data_file="/srv/salt/somefile.jinja",
        data_render=True,
        template_dict={"key1": "value1", "key2": "value2"},
    )

To pass through a file that contains mako templating:

.. code-block:: python

    salt.utils.http.query(
        "http://example.com/post/url",
        method="POST",
        data_file="/srv/salt/somefile.mako",
        data_render=True,
        data_renderer="mako",
        template_dict={"key1": "value1", "key2": "value2"},
    )

Because this function uses Salt's own rendering system, any Salt renderer can
be used. Because Salt's renderer requires ``__opts__`` to be set, an ``opts``
dictionary should be passed in. If it is not, then the default ``__opts__``
values for the node type (master or minion) will be used. Because this library
is intended primarily for use by minions, the default node type is ``minion``.
However, this can be changed to ``master`` if necessary.

.. code-block:: python

    salt.utils.http.query(
        "http://example.com/post/url",
        method="POST",
        data_file="/srv/salt/somefile.jinja",
        data_render=True,
        template_dict={"key1": "value1", "key2": "value2"},
        opts=__opts__,
    )

    salt.utils.http.query(
        "http://example.com/post/url",
        method="POST",
        data_file="/srv/salt/somefile.jinja",
        data_render=True,
        template_dict={"key1": "value1", "key2": "value2"},
        node="master",
    )

Headers
```````

Headers may also be passed through, either as a ``header_list``, a
``header_dict``, or as a ``header_file``. As with the ``data_file``, the
``header_file`` may also be templated. Take note that because HTTP headers are
normally syntactically-correct YAML, they will automatically be imported as an
a Python dict.

.. code-block:: python

    salt.utils.http.query(
        "http://example.com/delete/url",
        method="POST",
        header_file="/srv/salt/headers.jinja",
        header_render=True,
        header_renderer="jinja",
        template_dict={"key1": "value1", "key2": "value2"},
    )

Because much of the data that would be templated between headers and data may be
the same, the ``template_dict`` is the same for both. Correcting possible
variable name collisions is up to the user.

Authentication
``````````````

The ``query()`` function supports basic HTTP authentication. A username and
password may be passed in as ``username`` and ``password``, respectively.

.. code-block:: python

    salt.utils.http.query("http://example.com", username="larry", password="5700g3543v4r")

Cookies and Sessions
````````````````````

Cookies are also supported, using Python's built-in ``cookielib``. However, they
are turned off by default. To turn cookies on, set ``cookies`` to True.

.. code-block:: python

    salt.utils.http.query("http://example.com", cookies=True)

By default cookies are stored in Salt's cache directory, normally
``/var/cache/salt``, as a file called ``cookies.txt``. However, this location
may be changed with the ``cookie_jar`` argument:

.. code-block:: python

    salt.utils.http.query(
        "http://example.com", cookies=True, cookie_jar="/path/to/cookie_jar.txt"
    )

By default, the format of the cookie jar is LWP (aka, lib-www-perl). This
default was chosen because it is a human-readable text file. If desired, the
format of the cookie jar can be set to Mozilla:

.. code-block:: python

    salt.utils.http.query(
        "http://example.com",
        cookies=True,
        cookie_jar="/path/to/cookie_jar.txt",
        cookie_format="mozilla",
    )

Because Salt commands are normally one-off commands that are piped together,
this library cannot normally behave as a normal browser, with session cookies
that persist across multiple HTTP requests. However, the session can be
persisted in a separate cookie jar. The default filename for this file, inside
Salt's cache directory, is ``cookies.session.p``. This can also be changed.

.. code-block:: python

    salt.utils.http.query(
        "http://example.com", persist_session=True, session_cookie_jar="/path/to/jar.p"
    )

The format of this file is msgpack, which is consistent with much of the rest
of Salt's internal structure. Historically, the extension for this file is
``.p``. There are no current plans to make this configurable.

Proxy
`````

If the ``tornado`` backend is used (``tornado`` is the default), proxy
information configured in ``proxy_host``, ``proxy_port``, ``proxy_username``,
``proxy_password`` and ``no_proxy`` from the ``__opts__`` dictionary will be used.  Normally
these are set in the minion configuration file.

.. code-block:: yaml

    proxy_host: proxy.my-domain
    proxy_port: 31337
    proxy_username: charon
    proxy_password: obolus
    no_proxy: ['127.0.0.1', 'localhost']

.. code-block:: python

    salt.utils.http.query("http://example.com", opts=__opts__, backend="tornado")

Return Data
~~~~~~~~~~~

.. note:: Return data encoding

    If ``decode`` is set to ``True``, ``query()`` will attempt to decode the
    return data. ``decode_type`` defaults to ``auto``.  Set it to a specific
    encoding, ``xml``, for example, to override autodetection.

Because Salt's http library was designed to be used with REST interfaces,
``query()`` will attempt to decode the data received from the remote server
when ``decode`` is set to ``True``.  First it will check the ``Content-type``
header to try and find references to XML. If it does not find any, it will look
for references to JSON. If it does not find any, it will fall back to plain
text, which will not be decoded.

JSON data is translated into a dict using Python's built-in ``json`` library.
XML is translated using ``salt.utils.xml_util``, which will use Python's
built-in XML libraries to attempt to convert the XML into a dict. In order to
force either JSON or XML decoding, the ``decode_type`` may be set:

.. code-block:: python

    salt.utils.http.query("http://example.com", decode_type="xml")

Once translated, the return dict from ``query()`` will include a dict called
``dict``.

If the data is not to be translated using one of these methods, decoding may be
turned off.

.. code-block:: python

    salt.utils.http.query("http://example.com", decode=False)

If decoding is turned on, and references to JSON or XML cannot be found, then
this module will default to plain text, and return the undecoded data as
``text`` (even if text is set to ``False``; see below).

The ``query()`` function can return the HTTP status code, headers, and/or text
as required. However, each must individually be turned on.

.. code-block:: python

    salt.utils.http.query("http://example.com", status=True, headers=True, text=True)

The return from these will be found in the return dict as ``status``,
``headers`` and ``text``, respectively.

Writing Return Data to Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
It is possible to write either the return data or headers to files, as soon as
the response is received from the server, but specifying file locations via the
``text_out`` or ``headers_out`` arguments. ``text`` and ``headers`` do not need
to be returned to the user in order to do this.

.. code-block:: python

    salt.utils.http.query(
        "http://example.com",
        text=False,
        headers=False,
        text_out="/path/to/url_download.txt",
        headers_out="/path/to/headers_download.txt",
    )

SSL Verification
~~~~~~~~~~~~~~~~
By default, this function will verify SSL certificates. However, for testing or
debugging purposes, SSL verification can be turned off.

.. code-block:: python

    salt.utils.http.query("https://example.com", verify_ssl=False)

CA Bundles
~~~~~~~~~~
The ``requests`` library has its own method of detecting which CA (certificate
authority) bundle file to use. Usually this is implemented by the packager for
the specific operating system distribution that you are using. However,
``urllib2`` requires a little more work under the hood. By default, Salt will
try to auto-detect the location of this file. However, if it is not in an
expected location, or a different path needs to be specified, it may be done so
using the ``ca_bundle`` variable.

.. code-block:: python

    salt.utils.http.query("https://example.com", ca_bundle="/path/to/ca_bundle.pem")

Updating CA Bundles
```````````````````

The ``update_ca_bundle()`` function can be used to update the bundle file at a
specified location. If the target location is not specified, then it will
attempt to auto-detect the location of the bundle file. If the URL to download
the bundle from does not exist, a bundle will be downloaded from the cURL
website.

CAUTION: The ``target`` and the ``source`` should always be specified! Failure
to specify the ``target`` may result in the file being written to the wrong
location on the local system. Failure to specify the ``source`` may cause the
upstream URL to receive excess unnecessary traffic, and may cause a file to be
download which is hazardous or does not meet the needs of the user.

.. code-block:: python

    salt.utils.http.update_ca_bundle(
        target="/path/to/ca-bundle.crt",
        source="https://example.com/path/to/ca-bundle.crt",
        opts=__opts__,
    )

The ``opts`` parameter should also always be specified. If it is, then the
``target`` and the ``source`` may be specified in the relevant configuration
file (master or minion) as ``ca_bundle`` and ``ca_bundle_url``, respectively.

.. code-block:: yaml

    ca_bundle: /path/to/ca-bundle.crt
    ca_bundle_url: https://example.com/path/to/ca-bundle.crt

If Salt is unable to auto-detect the location of the CA bundle, it will raise
an error.

The ``update_ca_bundle()`` function can also be passed a string or a list of
strings which represent files on the local system, which should be appended (in
the specified order) to the end of the CA bundle file. This is useful in
environments where private certs need to be made available, and are not
otherwise reasonable to add to the bundle file.

.. code-block:: python

    salt.utils.http.update_ca_bundle(
        opts=__opts__,
        merge_files=[
            "/etc/ssl/private_cert_1.pem",
            "/etc/ssl/private_cert_2.pem",
            "/etc/ssl/private_cert_3.pem",
        ],
    )


Test Mode
~~~~~~~~~

This function may be run in test mode. This mode will perform all work up until
the actual HTTP request. By default, instead of performing the request, an empty
dict will be returned. Using this function with ``TRACE`` logging turned on will
reveal the contents of the headers and POST data to be sent.

Rather than returning an empty dict, an alternate ``test_url`` may be passed in.
If this is detected, then test mode will replace the ``url`` with the
``test_url``, set ``test`` to ``True`` in the return data, and perform the rest
of the requested operations as usual. This allows a custom, non-destructive URL
to be used for testing when necessary.


Execution Module
----------------

The ``http`` execution module is a very thin wrapper around the
``salt.utils.http`` library. The ``opts`` can be passed through as well, but if
they are not specified, the minion defaults will be used as necessary.

Because passing complete data structures from the command line can be tricky at
best and dangerous (in terms of execution injection attacks) at worse, the
``data_file``, and ``header_file`` are likely to see more use here.

All methods for the library are available in the execution module, as kwargs.

.. code-block:: bash

    salt myminion http.query http://example.com/restapi method=POST \
        username='larry' password='5700g3543v4r' headers=True text=True \
        status=True decode_type=xml data_render=True \
        header_file=/tmp/headers.txt data_file=/tmp/data.txt \
        header_render=True cookies=True persist_session=True


Runner Module
-------------

Like the execution module, the ``http`` runner module is a very thin wrapper
around the ``salt.utils.http`` library. The only significant difference is that
because runners execute on the master instead of a minion, a target is not
required, and default opts will be derived from the master config, rather than
the minion config.

All methods for the library are available in the runner module, as kwargs.

.. code-block:: bash

    salt-run http.query http://example.com/restapi method=POST \
        username='larry' password='5700g3543v4r' headers=True text=True \
        status=True decode_type=xml data_render=True \
        header_file=/tmp/headers.txt data_file=/tmp/data.txt \
        header_render=True cookies=True persist_session=True


State Module
------------

The state module is a wrapper around the runner module, which applies stateful
logic to a query. All kwargs as listed above are specified as usual in state
files, but two more kwargs are available to apply stateful logic. A required
parameter is ``match``, which specifies a pattern to look for in the return
text. By default, this will perform a string comparison of looking for the
value of match in the return text. In Python terms this looks like:

.. code-block:: python

   def myfunc():
       if match in html_text:
           return True

If more complex pattern matching is required, a regular expression can be used
by specifying a ``match_type``. By default this is set to ``string``, but it
can be manually set to ``pcre`` instead. Please note that despite the name, this
will use Python's ``re.search()`` rather than ``re.match()``.

Therefore, the following states are valid:

.. code-block:: yaml

    http://example.com/restapi:
      http.query:
        - match: 'SUCCESS'
        - username: 'larry'
        - password: '5700g3543v4r'
        - data_render: True
        - header_file: /tmp/headers.txt
        - data_file: /tmp/data.txt
        - header_render: True
        - cookies: True
        - persist_session: True

    http://example.com/restapi:
      http.query:
        - match_type: pcre
        - match: '(?i)succe[ss|ed]'
        - username: 'larry'
        - password: '5700g3543v4r'
        - data_render: True
        - header_file: /tmp/headers.txt
        - data_file: /tmp/data.txt
        - header_render: True
        - cookies: True
        - persist_session: True

In addition to, or instead of a match pattern, the status code for a URL can be
checked. This is done using the ``status`` argument:

.. code-block:: yaml

    http://example.com/:
      http.query:
        - status: 200

If both are specified, both will be checked, but if only one is ``True`` and the
other is ``False``, then ``False`` will be returned. In this case, the comments
in the return data will contain information for troubleshooting.

Because this is a monitoring state, it will return extra data to code that
expects it. This data will always include ``text`` and ``status``. Optionally,
``headers`` and ``dict`` may also be requested by setting the ``headers`` and
``decode`` arguments to True, respectively.

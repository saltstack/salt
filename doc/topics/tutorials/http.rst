HTTP Modules
============

This tutorial demonstrates using the various HTTP modules available in Salt.
These modules wrap the Python ``requests`` library, extending it in a manner
that is more consistent with Salt workflows.

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

``salt.utils.http.query()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function forms a basic query, but with some add-ons not present in the
``requests`` library. Not all functionality currently available in ``requests``
has been added, but can be in future iterations.

A basic query can be performed by calling this function with no more than a
single URL:

.. code-block:: python

    salt.utils.http.query('http://example.com')

By default the query will be performed with a ``GET`` method. The method can
be overridden with the ``method`` argument:

.. code-block:: python

    salt.utils.http.query('http://example.com/delete/url', 'DELETE')

When using the ``POST`` method (and others, such ``PUT``), extra data is usually
sent as well. This data can be either sent directly, in whatever format is
required by the remote server (XML, JSON, plain text, etc).

.. code-block:: python

    salt.utils.http.query(
        'http://example.com/delete/url',
        method='POST',
        data=json.loads(mydict)
    )

Bear in mind that this data must be sent pre-formatted; this function will not
format it for you. However, a templated file stored on the local system may be
passed through, along with variables to populate it with. To pass through only
the file (untemplated):

.. code-block:: python

    salt.utils.http.query(
        'http://example.com/post/url',
        method='POST',
        data_file='/srv/salt/somefile.xml'
    )

To pass through a file that contains jinja + yaml templating (the default):

.. code-block:: python

    salt.utils.http.query(
        'http://example.com/post/url',
        method='POST',
        data_file='/srv/salt/somefile.jinja',
        data_render=True,
        template_data={'key1': 'value1', 'key2': 'value2'}
    )

To pass through a file that contains mako templating:

.. code-block:: python

    salt.utils.http.query(
        'http://example.com/post/url',
        method='POST',
        data_file='/srv/salt/somefile.mako',
        data_render=True,
        data_renderer='mako',
        template_data={'key1': 'value1', 'key2': 'value2'}
    )

Because this function uses Salt's own rendering system, any Salt renderer can
be used. Because Salt's renderer requires ``__opts__`` to be set, an ``opts``
dictionary should be passed in. If it is not, then the default ``__opts__``
values for the node type (master or minion) will be used. Because this library
is intended primarily for use by minions, the default node type is ``minion``.
However, this can be changed to ``master`` if necessary.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com/post/url',
        method='POST',
        data_file='/srv/salt/somefile.jinja',
        data_render=True,
        template_data={'key1': 'value1', 'key2': 'value2'},
        opts=__opts__
    )

    salt.utils.http.query(
        'http://example.com/post/url',
        method='POST',
        data_file='/srv/salt/somefile.jinja',
        data_render=True,
        template_data={'key1': 'value1', 'key2': 'value2'},
        node='master'
    )

Headers may also be passed through, either as a ``header_list``, a
``header_dict`` or as a ``header_file``. As with the ``data_file``, the
``header_file`` may also  be templated. Take note that because HTTP headers are
normally syntactically-correct YAML, they will automatically be imported as an
a Python dict.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com/delete/url',
        method='POST',
        header_file='/srv/salt/headers.jinja',
        header_render=True,
        header_renderer='jinja',
        template_data={'key1': 'value1', 'key2': 'value2'}
    )

Because much of the data that would be templated between headers and data may be
the same, the ``template_data`` is the same for both. Correcting possible
variable name collisions is up to the user.

The ``query()`` function supports basic HTTP authentication. A username and
password may be passed in as ``username`` and ``password``, respectively.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        username='larry',
        password=`5700g3543v4r`,
    )

Cookies are also supported, using Python's built-in ``cookielib``. However, they
are turned off by default. To turn cookies on, set ``cookies`` to True.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        cookies=True
    )

By default cookies are stored in Salt's cache directory, normally
``/var/cache/salt``, as a file called ``cookies.txt``. However, this location
may be changed with the ``cookie_jar`` argument:

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        cookies=True,
        cookie_jar='/path/to/cookie_jar.txt'
    )

By default, the format of the cookie jar is LWP (aka, lib-www-perl). This
default was chosen because it is a human-readable text file. If desired, the
format of the cookie jar can be set to Mozilla:

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        cookies=True,
        cookie_jar='/path/to/cookie_jar.txt',
        cookie_format='mozilla'
    )

Because Salt commands are normally one-off commands that are piped together,
this library cannot normally behave as a normal browser, with session cookies
that persist across multiple HTTP requests. However, the session can be
persisted in a separate cookie jar. The default filename for this file, inside
Salt's cache directory, is ``cookies.session.p``. This can also be changed.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        persist_session=True,
        session_cookie_jar='/path/to/jar.p'
    )

The format of this file is msgpack, which is consistent with much of the rest
of Salt's internal structure. Historically, the extension for this file is
``.p``. There are no current plans to make this configurable.

Return Data
~~~~~~~~~~~

By default, ``query()`` will attempt to decode the return data. Because it was
designed to be used with REST interfaces, it will attempt to decode the data
received from the remote server. First it will check the ``Content-type`` header
to try and find references to XML. If it does not find any, it will look for
references to JSON. If it does not find any, it will fall back to plain text,
which will not be decoded.

JSON data is translated into a dict using Python's built-in ``json`` library.
XML is translated using ``salt.utils.xml_util``, which will use Python's
built-in XML libraries to attempt to convert the XML into a dict. In order to
force either JSON or XML decoding, the ``decode_type`` may be set:

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        decode_type='xml'
    )

Once translated, the return dict from ``query()`` will include a dict called
``dict``.

If the data is not to be translated using one of these methods, decoding may be
turned off.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        decode=False
    )

If decoding is turned on, and references to JSON or XML cannot be found, then
this module will default to plain text, and return the undecoded data as
``text`` (even if text is set to ``False``; see below).

The ``query()`` function can return the HTTP status code, headers, and/or text
as required. However, each must individually be turned on.

.. code-block:: python

    salt.utils.http.query(
        'http://example.com',
        status=True,
        headers=True,
        text=True
    )

The return from these will be found in the return dict as ``status``,
``headers`` and ``text``, respectively.

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
        - status: '200'

If both are specified, both will be checked, but if only one is ``True`` and the
other is ``False``, then ``False`` will be returned. In this case, the comments
in the return data will contain information for troubleshooting.

Because this is a monitoring state, it will return extra data to code that
expects it. This data will always include ``text`` and ``status``. Optionally,
``headers`` and ``dict`` may also be requested by setting the ``headers`` and
``decode`` arguments to True, respectively.

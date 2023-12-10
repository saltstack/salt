Output Options
--------------

.. option:: --out

    Pass in an alternative outputter to display the return of data. This
    outputter can be any of the available outputters:

        ``highstate``, ``json``, ``key``, ``overstatestage``, ``pprint``, ``raw``, ``txt``, ``yaml``, and :ref:`many others <all-salt.output>`.

    Some outputters are formatted only for data returned from specific functions.
    If an outputter is used that does not support the data passed into it, then
    Salt will fall back on the ``pprint`` outputter and display the return data
    using the Python ``pprint`` standard library module.

.. option:: --out-indent OUTPUT_INDENT, --output-indent OUTPUT_INDENT

    Print the output indented by the provided value in spaces. Negative values
    disable indentation. Only applicable in outputters that support
    indentation.

.. option:: --out-file=OUTPUT_FILE, --output-file=OUTPUT_FILE

    Write the output to the specified file.

.. option:: --out-file-append, --output-file-append

    Append the output to the specified file.

.. option:: --no-color

    Disable all colored output

.. option:: --force-color

    Force colored output

    .. note::
        When using colored output the color codes are as follows:

        ``green`` denotes success, ``red`` denotes failure, ``blue`` denotes
        changes and success and ``yellow`` denotes a expected future change in configuration.

.. option:: --state-output=STATE_OUTPUT, --state_output=STATE_OUTPUT

    Override the configured state_output value for minion
    output. One of 'full', 'terse', 'mixed', 'changes' or
    'filter'. Default: 'none'.

.. option:: --state-verbose=STATE_VERBOSE, --state_verbose=STATE_VERBOSE

    Override the configured state_verbose value for minion
    output. Set to True or False. Default: none.

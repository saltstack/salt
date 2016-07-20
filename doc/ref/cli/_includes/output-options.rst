Output Options
--------------

.. option:: --out

    Pass in an alternative outputter to display the return of data. This
    outputter can be any of the available outputters:

        ``grains``, ``highstate``, ``json``, ``key``, ``overstatestage``, ``pprint``, ``raw``, ``txt``, ``yaml``

    Some outputters are formatted only for data returned from specific
    functions; for instance, the ``grains`` outputter will not work for non-grains
    data.

    If an outputter is used that does not support the data passed into it, then
    Salt will fall back on the ``pprint`` outputter and display the return data
    using the Python ``pprint`` standard library module.

    .. note::
        If using ``--out=json``, you will probably want ``--static`` as well.
        Without the static option, you will get a separate JSON string per minion
        which makes JSON output invalid as a whole.
        This is due to using an iterative outputter. So if you want to feed it
        to a JSON parser, use ``--static`` as well.

.. option:: --out-indent OUTPUT_INDENT, --output-indent OUTPUT_INDENT

    Print the output indented by the provided value in spaces. Negative values
    disable indentation. Only applicable in outputters that support
    indentation.

.. option:: --out-file=OUTPUT_FILE, --output-file=OUTPUT_FILE

    Write the output to the specified file.

.. option:: --no-color

    Disable all colored output

.. option:: --force-color

    Force colored output

    .. note::
        When using colored output the color codes are as follows:

        ``green`` denotes success, ``red`` denotes failure, ``blue`` denotes
        changes and success and ``yellow`` denotes a expected future change in configuration.

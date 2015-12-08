.. admonition:: Do not use dots in SLS file names or their directories

    The initial implementation of :conf_master:`top.sls <state_top>` and
    :ref:`include-declaration` followed the python import model where a slash
    is represented as a period.  This means that a SLS file with a period in
    the name ( besides the suffix period) can not be referenced.  For example,
    webserver_1.0.sls is not referenceable because webserver_1.0 would refer
    to the directory/file webserver_1/0.sls

    The same applies for any subdirecortories, this is especially 'tricky' when
    git repos are created.  Another command that typically can't render it's
    output is ```state.show_sls``` of a file in a path that contains a dot.

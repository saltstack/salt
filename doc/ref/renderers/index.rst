.. _renderers:

=========
Renderers
=========

The Salt state system operates by gathering information from common data types
such as lists, dictionaries, and strings that would be familiar to any
developer.

Salt Renderers translate input from the format in which it is written into
Python data structures.

The default renderer is set in the master/minion configuration file using the
:conf_master:`renderer` config option, which defaults to ``jinja|yaml``.


Two Kinds of Renderers
----------------------

Renderers fall into one of two categories, based on what they output: text or
data. Some exceptions to this would be the :mod:`pure python
<salt.renderers.py>` and :mod:`gpg <salt.renderers.gpg>` renderers which could be used in either capacity.

Text Renderers
**************

.. include:: ../../_incl/jinja_security.rst

A text renderer returns text. These include templating engines such as
:mod:`jinja <salt.renderers.jinja>`, :mod:`mako <salt.renderers.mako>`, and
:mod:`genshi <salt.renderers.genshi>`, as well as the :mod:`gpg
<salt.renderers.gpg>` renderer. The following are all text renderers:

- :mod:`aws_kms <salt.renderers.aws_kms>`
- :mod:`cheetah <salt.renderers.cheetah>`
- :mod:`genshi <salt.renderers.genshi>`
- :mod:`gpg <salt.renderers.gpg>`
- :mod:`jinja <salt.renderers.jinja>`
- :mod:`mako <salt.renderers.mako>`
- :mod:`nacl <salt.renderers.nacl>`
- :mod:`pass <salt.renderers.pass>`
- :mod:`py <salt.renderers.py>`
- :mod:`wempy <salt.renderers.wempy>`

Data Renderers
**************

A data renderer returns a Python data structure (typically a dictionary). The
following are all data renderers:

- :mod:`dson <salt.renderers.dson>`
- :mod:`hjson <salt.renderers.hjson>`
- :mod:`json5 <salt.renderers.json5>`
- :mod:`json <salt.renderers.json>`
- :mod:`pydsl <salt.renderers.pydsl>`
- :mod:`pyobjects <salt.renderers.pyobjects>`
- :mod:`py <salt.renderers.py>`
- :mod:`stateconf <salt.renderers.stateconf>`
- :mod:`yamlex <salt.renderers.yamlex>`
- :mod:`yaml <salt.renderers.yaml>`
- :mod:`gpg <salt.renderers.gpg>`

Overriding the Default Renderer
-------------------------------

It can sometimes be beneficial to write an SLS file using a renderer other than
the default one. This can be done by using a "shebang"-like syntax on the first
line of the SLS file:

Here is an example of using the :mod:`pure python <salt.renderers.py>` renderer
to install a package:

.. code-block:: python

    #!py


    def run():
        """
        Install version 1.5-1.el7 of package "python-foo"
        """
        return {
            "include": ["python"],
            "python-foo": {"pkg.installed": [{"version": "1.5-1.el7"}]},
        }

This would be equivalent to the following:

.. code-block:: yaml

    include:
      - python

    python-foo:
      pkg.installed:
        - version: '1.5-1.el7'

.. _renderers-composing:

Composing Renderers (a.k.a. The "Render Pipeline")
--------------------------------------------------

A render pipeline can be composed from other renderers by connecting them in a
series of "pipes" (i.e. ``|``). The renderers will be evaluated from left to
right, with each renderer receiving the result of the previous renderer's
execution.

Take for example the default renderer (``jinja|yaml``). The file is evaluated
first a jinja template, and the result of that template is evaluated as a YAML
document.

Other render pipeline combinations include:

  ``yaml``
      Just YAML, no templating.

  ``mako|yaml``
      This passes the input to the ``mako`` renderer, with its output fed into
      the ``yaml`` renderer.

  ``jinja|mako|yaml``
      This one allows you to use both jinja and mako templating syntax in the
      input and then parse the final rendered output as YAML.

The following is a contrived example SLS file using the ``jinja|mako|yaml``
render pipeline:

.. code-block:: text

    #!jinja|mako|yaml

    An_Example:
      cmd.run:
        - name: |
            echo "Using Salt ${grains['saltversion']}" \
                 "from path {{grains['saltpath']}}."
        - cwd: /

    <%doc> ${...} is Mako's notation, and so is this comment. </%doc>
    {#     Similarly, {{...}} is Jinja's notation, and so is this comment. #}

.. important::
    Keep in mind that not all renderers can be used alone or with any other
    renderers. For example, text renderers shouldn't be used alone as their
    outputs are just strings, which still need to be parsed by another renderer
    to turn them into Python data structures.

    For example, it would not make sense to use ``yaml|jinja`` because the
    output of the :mod:`yaml <salt.renderers.yaml>` renderer is a Python data
    structure, and the :mod:`jinja <salt.renderers.jinja>` renderer only
    accepts text as input.

    Therefore, when combining renderers, you should know what each renderer
    accepts as input and what it returns as output. One way of thinking about
    it is that you can chain together multiple text renderers, but the pipeline
    *must* end in a data renderer. Similarly, since the text renderers in Salt
    don't accept data structures as input, a text renderer should usually not
    come after a data renderer. It's technically *possible* to write a renderer
    that takes a data structure as input and returns a string, but no such
    renderer is distributed with Salt.


Writing Renderers
-----------------

A custom renderer must be a Python module which implements a ``render``
function. This function must implement three positional arguments:

1. ``data`` - Can be called whatever you like. This is the input to be
   rendered.
2. ``saltenv``
3. ``sls``

The first is the important one, and the 2nd and 3rd must be included since Salt
needs to pass this info to each render, even though it is only used by template
renderers.

Renderers should be written so that the ``data`` argument can accept either
strings or file-like objects as input. For example:

.. code-block:: python

    import mycoolmodule
    from salt.ext import six


    def render(data, saltenv="base", sls="", **kwargs):
        if not isinstance(data, six.string_types):
            # Read from file-like object
            data = data.read()

        return mycoolmodule.do_something(data)

Custom renderers should be placed within ``salt://_renderers/``, so that they
can be synced to minions. They are synced when any of the following are run:

- :py:func:`state.apply <salt.modules.state.apply_>`
- :py:func:`saltutil.sync_renderers <salt.modules.saltutil.sync_renderers>`
- :py:func:`saltutil.sync_all <salt.modules.saltutil.sync_all>`

Any custom renderers which have been synced to a minion, that are named the
same as one of Salt's default set of renderers, will take the place of the
default renderer with the same name.

.. note::
    Renderers can also be synced from ``salt://_renderers/`` to the Master
    using either the :py:func:`saltutil.sync_renderers
    <salt.runners.saltutil.sync_renderers>` or :py:func:`saltutil.sync_all
    <salt.runners.saltutil.sync_all>` runner function.


Examples
--------

The best place to find examples of renderers is in the Salt source code.

Documentation for renderers included with Salt can be found here:

:blob:`salt/renderers`

Here is a simple YAML renderer example:

.. code-block:: python

    import salt.utils.yaml
    from salt.utils.yamlloader import SaltYamlSafeLoader
    from salt.ext import six


    def render(yaml_data, saltenv="", sls="", **kws):
        if not isinstance(yaml_data, six.string_types):
            yaml_data = yaml_data.read()
        data = salt.utils.yaml.safe_load(yaml_data)
        return data if data else {}

Full List of Renderers
----------------------
.. toctree::

    all/index

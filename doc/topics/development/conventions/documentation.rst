.. _salt-docs:

==========================
Writing Salt Documentation
==========================

Salt's documentation is built using the `Sphinx`_ documentation system. It can
be built in a large variety of output formats including HTML, PDF, ePub, and
manpage.

All the documentation is contained in the main Salt repository. Speaking
broadly, most of the narrative documentation is contained within the
:blob:`doc` subdirectory and most of the reference and API documentation is
written inline with Salt's Python code and extracted using a Sphinx extension.

.. _`Sphinx`: http://sphinx-doc.org/


.. _docs-style:

Style
=====

The Salt project recommends the `IEEE style guide`_ as a general reference for
writing guidelines. Those guidelines are not strictly enforced but rather serve
as an excellent resource for technical writing questions. The `NCBI style
guide`_ is another very approachable resource.

.. _`IEEE style guide`: https://development.standards.ieee.org/myproject/Public/mytools/draft/styleman.pdf
.. _`NCBI style guide`: http://www.ncbi.nlm.nih.gov/books/NBK993/

Point-of-view
-------------

Use third-person perspective and avoid "I", "we", "you" forms of address.
Identify the addressee specifically e.g., "users should", "the compiler does",
etc.

Active voice
------------

Use active voice and present-tense. Avoid filler words.

Title capitalization
--------------------

Document titles and section titles within a page should follow normal sentence
capitalization rules. Words that are capitalized as part of a regular sentence
should be capitalized in a title and otherwise left as lowercase. Punctuation
can be omitted unless it aids the intent of the title (e.g., exclamation points
or question marks).

For example:

.. code-block:: restructuredtext

    This is a main heading
    ======================

    Paragraph.

    This is an exciting sub-heading!
    --------------------------------

    Paragraph.


.. _docs-modules:

Serial Commas
-------------

According to Wikipedia: In English punctuation, a serial comma or series comma
(also called Oxford comma and Harvard comma) is a comma placed immediately
before the coordinating conjunction (usually "and", "or", or "nor") in a series of
three or more terms. For example, a list of three countries might be punctuated
either as "France, Italy, and Spain" (with the serial comma), or as "France,
Italy and Spain" (without the serial comma)."

When writing a list that includes three or more items, the serial comma should
always be used.

Documenting modules
===================

Documentation for Salt's various module types is inline in the code. During the
documentation build process it is extracted and formatted into the final HTML,
PDF, etc format.

Inline documentation
--------------------

Python has special multi-line strings called docstrings as the first element in
a function or class. These strings allow documentation to live alongside the
code and can contain special formatting. For example:

.. code-block:: python

    def my_function(value):
        '''
        Upper-case the given value

        Usage:

        .. code-block:: python

            val = 'a string'
            new_val = myfunction(val)
            print(new_val) # 'A STRING'

        :param value: a string
        :return: a copy of ``value`` that has been upper-cased
        '''
        return value.upper()

Specify a release for additions or changes
------------------------------------------

New functions or changes to existing functions should include a marker that
denotes what Salt release will be affected. For example:

.. code-block:: python

    def my_function(value):
        '''
        Upper-case the given value

        .. versionadded:: 2014.7.0

        <...snip...>
        '''
        return value.upper()

For changes to a function:

.. code-block:: python

    def my_function(value, strip=False):
        '''
        Upper-case the given value

        .. versionchanged:: Boron
            Added a flag to also strip whitespace from the string.

        <...snip...>
        '''
        if strip:
            return value.upper().strip()
        return value.upper()

Adding module documentation to the index
----------------------------------------

Each module type has an index listing all modules of that type. For example:
:ref:`all-salt.modules`, :ref:`all-salt.states`, :ref:`all-salt.renderers`.
New modules must be added to the index manually.

1.  Edit the file for the module type:
    :blob:`execution modules <doc/ref/modules/all/index.rst>`,
    :blob:`state modules<doc/ref/states/all/index.rst>`,
    :blob:`renderer modules <doc/ref/renderers/all/index.rst>`, etc.

2.  Add the new module to the alphebetized list.

3.  :ref:`Build the documentation <docs-building>` which will generate an ``.rst``
    file for the new module in the same directory as the ``index.rst``.

4.  Commit the changes to ``index.rst`` and the new ``.rst`` file and send a
    pull request.


.. _docs-ref:

Cross-references
================

The Sphinx documentation system contains a wide variety of cross-referencing
capabilities.


.. _docs-ref-glossary:

Glossary entries
----------------

Link to :ref:`glossary entries <glossary>` using the `term role`_. A
cross-reference should be added the first time a Salt-specific term is used in
a document.

.. _`term role`: http://sphinx-doc.org/markup/inline.html#role-term

.. code-block:: restructuredtext

    A common way to encapsulate master-side functionality is by writing a
    custom :term:`Runner Function`. Custom Runner Functions are easy to write.


.. _docs-ref-index:

Index entries
-------------

Sphinx automatically generates many kinds of index entries, but it is
occasionally useful to manually add items to the index.

One method is to use the `index directive`_ above the document or section that
should appear in the index.

.. _`index directive`: http://sphinx-doc.org/markup/misc.html#directive-index

.. code-block:: restructuredtext

    .. index:: ! Event, event bus, event system
        see: Reactor; Event

Another method is to use the `index role`_ inline with the text that should
appear in the index. The index entry is created and the target text is left
otherwise intact.

.. _`index role`: http://sphinx-doc.org/markup/misc.html#role-index

.. code-block:: restructuredtext

    Information about the :index:`Salt Reactor`
    -------------------------------------------

    Paragraph.


.. _docs-ref-docs:

Documents and sections
----------------------

Each document should contain a unique top-level label of the form:

.. code-block:: restructuredtext

    .. _my-page:

    My page
    =======

    Paragraph.

Unique labels can be linked using the `ref role`_. This allows cross-references
to survive document renames or movement.

.. code-block:: restructuredtext

    For more information see :ref:`my-page`.

Note, the ``:doc:`` role should *not* be used to link documents together.

.. _`ref role`: http://sphinx-doc.org/markup/inline.html#role-ref


.. _docs-ref-modules:

Modules
-------

Cross-references to Salt modules can be added using Sphinx's Python domain
roles. For example, to create a link to the :py:func:`test.ping
<salt.modules.test.ping>` function:

.. code-block:: restructuredtext

    A useful execution module to test active communication with a minion is the
    :py:func:`test.ping <salt.modules.test.ping>` function.

Salt modules can be referenced as well:

.. code-block:: restructuredtext

    The :py:mod:`test module <salt.modules.test>` contains many useful
    functions for inspecting an active Salt connection.

The same syntax works for all modules types:

.. code-block:: restructuredtext

    One of the workhorse state module functions in Salt is the
    :py:func:`file.managed <salt.states.file.managed>` function.


.. _docs-ref-settings:

Settings
--------

Individual settings in the Salt Master or Salt Minion configuration files are
cross-referenced using two custom roles, ``conf_master``, and ``conf_minion``.

.. code-block:: restructuredtext

    The :conf_minion:`minion ID <id>` setting is a unique identifier for a
    single minion.


.. _docs-ref-fixes:

Documentation Changes and Fixes
===============================

Documentation changes and fixes should be made against the earliest supported
release branch that the update applies to. The practice of updating a release
branch instead of making all documentation changes against Salt's main, default
branch, ``develop``, is necessary in order for the docs to be as up-to-date as
possible when the docs are built.

The workflow mentioned above is also in line with the recommendations outlined
in Salt's :ref:`contributing` page. You can read more about how to choose where
to submit documentation fixes by reading the :ref:`which-salt-branch` section.

For an explanation of how to submit changes against various branches, see the
:ref:`github-pull-request` section. Specifically, see the section describing
how to ``Create a new branch`` and the steps that follow.


.. _docs-building:

Building the documentation
==========================

1.  Install Sphinx using a system package manager or pip. The package name is
    often of the form ``python-sphinx``. There are no other dependencies.

2.  Build the documentation using the provided Makefile or ``.bat`` file on
    Windows.

    .. code-block:: bash

        cd /path/to/salt/doc
        make html

3.  The generated documentation will be written to the ``doc/_build/<format>``
    directory.

4.  A useful method of viewing the HTML documentation locally is to start
    Python's built-in HTTP server:

    .. code-block:: bash

        cd /path/to/salt/doc/_build/html
        python -m SimpleHTTPServer

    Then pull up the documentation in a web browser at http://localhost:8000/.

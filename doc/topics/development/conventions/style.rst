.. _coding-style:

=================
Salt Coding Style
=================

To make it easier to contribute and read Salt code, SaltStack has `adopted
Black <SEP 15_>`_ as its code formatter. There are a few places where Black is
silent, and this guide should be used in those cases.

Coding style is NEVER grounds to reject code contributions, and is never
grounds to talk down to another member of the community (There are no grounds
to treat others without respect, especially people working to improve Salt)!


.. _pylint-instructions:

Linting
=======

Most Salt style conventions are codified in Salt's ``.pylintrc`` file.
Salt's linting has two major dependencies: pylint_ and saltpylint_, the full lint
requirements can be found under ``requirements/static/ci/lint.in`` and the pinned
requirements at ``requirements/static/ci/py3.<minor-version>/lint.txt``, however,
linting should be done using :ref:`nox <getting_set_up_for_tests>`, which is how
pull requests are checked.

.. code-block:: bash

   nox -e lint

One can target either salt's source code or the test suite(different pylint rules apply):

.. code-block:: bash

   nox -e lint-salt
   nox -e lint-tests


.. _pylint: https://www.pylint.org/
.. _saltpylint: https://github.com/saltstack/salt-pylint

Variables
=========

Variables should be a minimum of three characters and should provide an
easy-to-understand name of the object being represented.

When keys and values are iterated over, descriptive names should be used
to represent the temporary variables.

Multi-word variables should be separated by an underscore.

Variables which are two-letter words should have an underscore appended
to them to pad them to three characters.

Formatting Strings
------------------

All strings which require formatting should use the `.format` string method:

Please do NOT use printf formatting, unless it's a log message.

Good:

.. code-block:: python

    data = "some text"
    more = "{} and then some".format(data)
    log.debug("%s and then some", data)

Bad:

.. code-block:: python

    data = "some text"
    log.debug("{} and then some".format(data))


Docstring Conventions
---------------------

When adding a new function or state, where possible try to use a
``versionadded`` directive to denote when the function, state, or parameter was added.

.. code-block:: python

    def new_func(msg=""):
        """
        .. versionadded:: 0.16.0

        Prints what was passed to the function.

        msg : None
            The string to be printed.
        """
        print(msg)

If you are uncertain what version should be used, either consult a core
developer in IRC or bring this up when opening your :ref:`pull request
<installing-for-development>` and a core developer will let you know what
version to add. Typically this will be the next element in the `periodic table
<https://en.wikipedia.org/wiki/List_of_chemical_elements>`_.

Similar to the above, when an existing function or state is modified (for
example, when an argument is added), then under the explanation of that new
argument a ``versionadded`` directive should be used to note the version in
which the new argument was added. If an argument's function changes
significantly, the ``versionchanged`` directive can be used to clarify this:

.. code-block:: python

    def new_func(msg="", signature=""):
        """
        .. versionadded:: 0.16.0

        Prints what was passed to the function.

        msg : None
            The string to be printed. Will be prepended with 'Greetings! '.

        .. versionchanged:: 0.17.1

        signature : None
            An optional signature.

        .. versionadded:: 0.17.0
        """
        print("Greetings! {0}\n\n{1}".format(msg, signature))


Dictionaries
============

Dictionaries should be initialized using `{}` instead of `dict()`.

See here_ for an in-depth discussion of this topic.

.. _here: https://doughellmann.com/posts/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/


Imports
=======

Salt code prefers importing modules and not explicit functions. This is both a
style and functional preference. The functional preference originates around
the fact that the module import system used by pluggable modules will include
callable objects (functions) that exist in the direct module namespace. This
is not only messy, but may unintentionally expose code python libs to the Salt
interface and pose a security problem.

To say this more directly with an example, this is `GOOD`:

.. code-block:: python

    import os


    def minion_path():
        path = os.path.join(self.opts["cachedir"], "minions")
        return path

This on the other hand is `DISCOURAGED`:

.. code-block:: python

    from os.path import join


    def minion_path():
        path = join(self.opts["cachedir"], "minions")
        return path

The time when this is changed is for importing exceptions, generally directly
importing exceptions is preferred:

This is a good way to import exceptions:

.. code-block:: python

    from salt.exceptions import CommandExecutionError


Absolute Imports
----------------

Although `absolute imports`_ seems like an awesome idea, please do not use it.
Extra care would be necessary all over salt's code in order for absolute
imports to work as supposed. Believe it, it has been tried before and, as a
tried example, by renaming ``salt.modules.sysmod`` to ``salt.modules.sys``, all
other salt modules which needed to import :mod:`sys<python2:sys>` would have to
also import :mod:`absolute_import<python2:__future__>`, which should be
avoided.

.. note::

    An exception to this rule is the ``absolute_import`` from ``__future__`` at
    the top of each file within the Salt project. This import is necessary for
    Py3 compatibility. This particular import looks like this:

    .. code-block:: python

        from __future__ import absolute_import

    This import is required for all new Salt files and is a good idea to add to
    any custom states or modules. However, the practice of avoiding absolute
    imports still applies to all other cases as to avoid a name conflict.

.. _`absolute imports`: https://legacy.python.org/dev/peps/pep-0328/#rationale-for-absolute-imports


Code Churn
==========

Many pull requests have been submitted that only churn code in the name of
PEP 8. Code churn is a leading source of bugs and is **strongly discouraged**.
While style fixes are encouraged they should be isolated to a single file per
commit, and the changes should be legitimate, if there are any questions about
whether a style change is legitimate please reference this document and the
official PEP 8 (https://legacy.python.org/dev/peps/pep-0008/) document before
changing code. Many claims that a change is PEP 8 have been invalid, please
double check before committing fixes.

.. _`SEP 15`: https://github.com/saltstack/salt-enhancement-proposals/pull/21

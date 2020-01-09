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

Most Salt style conventions are codified in Salt's ``.testing.pylintrc`` file.
Salt's pylint file has two dependencies: pylint_ and saltpylint_. You can
install these dependencies with ``pip``:

.. code-block:: bash

    pip install pylint
    pip install saltpylint

The ``.testing.pylintrc`` file is found in the root of the Salt project and can
be passed as an argument to the pylint_ program as follows:

.. code-block:: bash

    pylint --rcfile=/path/to/salt/.testing.pylintrc salt/dir/to/lint

.. note::

    There are two pylint files in the ``salt`` directory. One is the
    ``.pylintrc`` file and the other is the ``.testing.pylintrc`` file. The
    tests that run in Jenkins against GitHub Pull Requests use
    ``.testing.pylintrc``. The ``testing.pylintrc`` file is a little less
    strict than the ``.pylintrc`` and is used to make it easier for contributors
    to submit changes. The ``.pylintrc`` file can be used for linting, but the
    ``testing.pylintrc`` is the source of truth when submitting pull requests.

.. _pylint: http://www.pylint.org
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

.. code-block:: python

    data = 'some text'
    more = '{0} and then some'.format(data)

Make sure to use indices or identifiers in the format brackets, since empty
brackets are not supported by python 2.6.

Please do NOT use printf formatting.

Docstring Conventions
---------------------

When adding a new function or state, where possible try to use a
``versionadded`` directive to denote when the function, state, or parameter was added.

.. code-block:: python

    def new_func(msg=''):
        '''
        .. versionadded:: 0.16.0

        Prints what was passed to the function.

        msg : None
            The string to be printed.
        '''
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

    def new_func(msg='', signature=''):
        '''
        .. versionadded:: 0.16.0

        Prints what was passed to the function.

        msg : None
            The string to be printed. Will be prepended with 'Greetings! '.

        .. versionchanged:: 0.17.1

        signature : None
            An optional signature.

        .. versionadded 0.17.0
        '''
        print('Greetings! {0}\n\n{1}'.format(msg, signature))


Dictionaries
============

Dictionaries should be initialized using `{}` instead of `dict()`.

See here_ for an in-depth discussion of this topic.

.. _here: http://doughellmann.com/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2.html


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
        path = os.path.join(self.opts['cachedir'], 'minions')
        return path

This on the other hand is `DISCOURAGED`:

.. code-block:: python

    from os.path import join

    def minion_path():
        path = join(self.opts['cachedir'], 'minions')
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

.. _`absolute imports`: http://legacy.python.org/dev/peps/pep-0328/#rationale-for-absolute-imports


Code Churn
==========

Many pull requests have been submitted that only churn code in the name of
PEP 8. Code churn is a leading source of bugs and is **strongly discouraged**.
While style fixes are encouraged they should be isolated to a single file per
commit, and the changes should be legitimate, if there are any questions about
whether a style change is legitimate please reference this document and the
official PEP 8 (http://legacy.python.org/dev/peps/pep-0008/) document before
changing code. Many claims that a change is PEP 8 have been invalid, please
double check before committing fixes.

.. _`SEP 15`: https://github.com/saltstack/salt-enhancement-proposals/pull/21

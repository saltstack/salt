.. _coding-style:

=================
Salt Coding Style
=================

Salt is developed with a certain coding style, while the style is dominantly
PEP 8 it is not completely PEP 8. It is also noteworthy that a few
development techniques are also employed which should be adhered to. In the
end, the code is made to be "Salty".

Most importantly though, we will accept code that violates the coding style and
KINDLY ask the contributor to fix it, or go ahead and fix the code on behalf of
the contributor. Coding style is NEVER grounds to reject code contributions,
and is never grounds to talk down to another member of the community (There are
no grounds to treat others without respect, especially people working to
improve Salt)!!


.. _pylint-instructions:

Linting
=======

Most Salt style conventions are codified in Salt's ``.pylintrc`` file. Salt's
pylint file has two dependencies: pylint_ and saltpylint_. You can install
these dependencies with ``pip``:

.. code-block:: bash

    pip install pylint
    pip install saltpylint

The ``.pylintrc`` file is found in the root of the Salt project and can be passed
as an argument to the pylint_ program as follows:

.. code-block:: bash

    pylint --rcfile=/path/to/salt/.pylintrc salt/dir/to/lint

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

Strings
=======

Salt follows a few rules when formatting strings:

Single Quotes
-------------

In Salt, all strings use single quotes unless there is a good reason not to.
This means that docstrings use single quotes, standard strings use single
quotes etc.:

.. code-block:: python

    def foo():
        '''
        A function that does things
        '''
        name = 'A name'
        return name

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

Docstrings should always add a newline, docutils takes care of the new line and
it makes the code cleaner and more vertical:

`GOOD`:

.. code-block:: python

    def bar():
        '''
        Here lies a docstring with a newline after the quotes and is the salty
        way to handle it! Vertical code is the way to go!
        '''
        return

`BAD`:

.. code-block:: python

    def baz():
        '''This is not ok!'''
        return


When adding a new function or state, where possible try to use a
``versionadded`` directive to denote when the function or state was added.

.. code-block:: python

    def new_func(msg=''):
        '''
        .. versionadded:: 0.16.0

        Prints what was passed to the function.

        msg : None
            The string to be printed.
        '''
        print msg

If you are uncertain what version should be used, either consult a core
developer in IRC or bring this up when opening your
:doc:`pull request </topics/development/hacking>` and a core developer will add the proper
version once your pull request has been merged. Bugfixes will be available in a
bugfix release (i.e. 0.17.1, the first bugfix release for 0.17.0), while new
features are held for feature releases, and this will affect what version
number should be used in the ``versionadded`` directive.


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
        print 'Greetings! {0}\n\n{1}'.format(msg, signature)


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

.. _`absolute imports`: http://legacy.python.org/dev/peps/pep-0328/#rationale-for-absolute-imports


Vertical is Better
==================

When writing Salt code, vertical code is generally preferred. This is not a hard
rule but more of a guideline. As PEP 8 specifies, Salt code should not exceed 79
characters on a line, but it is preferred to separate code out into more
newlines in some cases for better readability:

.. code-block:: python

    import os

    os.chmod(
            os.path.join(self.opts['sock_dir'],
                'minion_event_pub.ipc'),
            448
            )

Where there are more line breaks, this is also apparent when constructing a
function with many arguments, something very common in state functions for
instance:

.. code-block:: python

    def managed(name,
            source=None,
            source_hash='',
            user=None,
            group=None,
            mode=None,
            template=None,
            makedirs=False,
            context=None,
            replace=True,
            defaults=None,
            saltenv=None,
            backup='',
            **kwargs):

.. note::

    Making function and class definitions vertical is only required if the
    arguments are longer then 80 characters. Otherwise, the formatting is
    optional and both are acceptable.



Line Length
-----------

For function definitions and function calls, Salt adheres to the PEP-8
specification of at most 80 characters per line.

Non function definitions or function calls, please adopt a soft limit of 120
characters per line. If breaking the line reduces the code readability, don't
break it. Still, try to avoid passing that 120 characters limit and remember,
**vertical is better...  unless it isn't**


Indenting
=========

Some confusion exists in the python world about indenting things like function
calls, the above examples use 8 spaces when indenting comma-delimited
constructs.

The confusion arises because the pep8 program INCORRECTLY flags this as wrong,
where PEP 8, the document, cites only using 4 spaces here as wrong, as it
doesn't differentiate from a new indent level.

Right:

.. code-block:: python

    def managed(name,
            source=None,
            source_hash='',
            user=None)

WRONG:

.. code-block:: python

    def managed(name,
        source=None,
        source_hash='',
        user=None)

Lining up the indent is also correct:

.. code-block:: python

    def managed(name,
                source=None,
                source_hash='',
                user=None)

This also applies to function calls and other hanging indents.

pep8 and Flake8 (and, by extension, the vim plugin Syntastic) will complain
about the double indent for hanging indents.  This is a `known conflict
<https://github.com/jcrocholl/pep8/issues/167#issuecomment-15936564>`_ between
pep8 (the script) and the actual PEP 8 standard.  It is recommended that this
particular warning be ignored with the following lines in
``~/.config/flake8``:

.. code-block:: ini

    [flake8]
    ignore = E226,E241,E242,E126

Make sure your Flake8/pep8 are up to date.  The first three errors are ignored
by default and are present here to keep the behavior the same.  This will also
work for pep8 without the Flake8 wrapper -- just replace all instances of
'flake8' with 'pep8', including the filename.

Code Churn
==========

Many pull requests have been submitted that only churn code in the name of
PEP 8. Code churn is a leading source of bugs and is strongly discouraged.
While style fixes are encouraged they should be isolated to a single file per
commit, and the changes should be legitimate, if there are any questions about
whether a style change is legitimate please reference this document and the
official PEP 8 (http://legacy.python.org/dev/peps/pep-0008/) document before
changing code. Many claims that a change is PEP 8 have been invalid, please
double check before committing fixes.

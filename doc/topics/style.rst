=================
Salt Coding Style
=================

Salt is developed with a certain coding style, while the style is dominantly
PEP-08 it is not completely PEP-08. It is also noteworthy that a few
development techniques are also employed which should be adhered to. In the
end, the code is made to be "Salty".

Most importantly though, we will accept code that violates the coding style and
KINDLY ask the contributor to fix it, or go ahead and fix the code on behalf of
the contributor. Coding style is NEVER grounds to reject code contributions,
and is never grounds to talk down to another member of the community (There are
no grounds to treat others without respect, especially people working to
improve Salt)!!


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

Vertical is Better
==================

When writing Salt code, vertical code is generally preferred. This is not a hard
rule but more of a guideline. As PEP-08 specifies Salt code should not exceed 79
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
            env=None,
            backup='',
            **kwargs):

Code Churn
==========

Many pull requests have been submitted that only churn code in the name of
PEP-08. Code churn is a leading source of bugs and is strongly discouraged.
While style fixes are encouraged they should be isolated to a single file per
commit, and the changes should be legitimate, if there are any questions about
whether a style change is legitimate please reference this document and the
official PEP-08 (http://www.python.org/dev/peps/pep-0008/) document before
changing code. Many claims that a change is PEP-08 have been invalid, please
double check before committing fixes.

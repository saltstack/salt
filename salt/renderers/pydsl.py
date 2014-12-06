# -*- coding: utf-8 -*-
'''
A Python-based DSL

:maintainer: Jack Kuan <kjkuan@gmail.com>
:maturity: new
:platform: all

The `pydsl` renderer allows one to author salt formulas (.sls files) in pure
Python using a DSL that's easy to write and easy to read. Here's an example:

.. code-block:: python
    :linenos:

    #!pydsl

    apache = state('apache')
    apache.pkg.installed()
    apache.service.running()
    state('/var/www/index.html') \\
        .file('managed',
              source='salt://webserver/index.html') \\
        .require(pkg='apache')

Notice that any Python code is allow in the file as it's really a Python
module, so you have the full power of Python at your disposal. In this module,
a few objects are defined for you, including the usual (with ``__`` added)
``__salt__`` dictionary, ``__grains__``, ``__pillar__``, ``__opts__``,
``__env__``, and ``__sls__``, plus a few more:

  ``__file__``

    local file system path to the sls module.

  ``__pydsl__``

    Salt PyDSL object, useful for configuring DSL behavior per sls rendering.

  ``include``

    Salt PyDSL function for creating :ref:`include-declaration`'s.

  ``extend``

    Salt PyDSL function for creating :ref:`extend-declaration`'s.

  ``state``

    Salt PyDSL function for creating :ref:`ID-declaration`'s.


A state :ref:`ID-declaration` is created with a ``state(id)`` function call.
Subsequent ``state(id)`` call with the same id returns the same object. This
singleton access pattern applies to all declaration objects created with the
DSL.

.. code-block:: python

    state('example')
    assert state('example') is state('example')
    assert state('example').cmd is state('example').cmd
    assert state('example').cmd.running is state('example').cmd.running

The `id` argument is optional. If omitted, an UUID will be generated and used as
the `id`.

``state(id)`` returns an object under which you can create a
:ref:`state-declaration` object by accessing an attribute named after *any*
state module available in Salt.

.. code-block:: python

    state('example').cmd
    state('example').file
    state('example').pkg
    ...

Then, a :ref:`function-declaration` object can be created from a
:ref:`state-declaration` object by one of the following two ways:

1. by calling a method named after the state function on the :ref:`state-declaration` object.

.. code-block:: python

       state('example').file.managed(...)

2. by directly calling the attribute named for the :ref:`state-declaration`, and
   supplying the state function name as the first argument.

.. code-block:: python

       state('example').file('managed', ...)

With either way of creating a :ref:`function-declaration` object, any
:ref:`function-arg-declaration`'s can be passed as keyword arguments to the
call. Subsequent calls of a :ref:`function-declaration` will update the arg
declarations.

.. code-block:: python

    state('example').file('managed', source='salt://webserver/index.html')
    state('example').file.managed(source='salt://webserver/index.html')

As a shortcut, the special `name` argument can also be passed as the
first or second positional argument depending on the first or second
way of calling the :ref:`state-declaration` object. In the following
two examples `ls -la` is the `name` argument.

.. code-block:: python

    state('example').cmd.run('ls -la', cwd='/')
    state('example').cmd('run', 'ls -la', cwd='/')

Finally, a :ref:`requisite-declaration` object with its
:ref:`requisite-reference`'s can be created by invoking one of the
requisite methods (see :doc:`State Requisites
</ref/states/requisites>`) on either a :ref:`function-declaration`
object or a :ref:`state-declaration` object. The return value of a
requisite call is also a :ref:`function-declaration` object, so you
can chain several requisite calls together.

Arguments to a requisite call can be a list of :ref:`state-declaration` objects
and/or a set of keyword arguments whose names are state modules and values are
IDs of :ref:`ID-declaration`'s or names of :ref:`name-declaration`'s.

.. code-block:: python

    apache2 = state('apache2')
    apache2.pkg.installed()
    state('libapache2-mod-wsgi').pkg.installed()

    # you can call requisites on function declaration
    apache2.service.running() \\
                   .require(apache2.pkg,
                            pkg='libapache2-mod-wsgi') \\
                   .watch(file='/etc/apache2/httpd.conf')

    # or you can call requisites on state declaration.
    # this actually creates an anonymous function declaration object
    # to add the requisites.
    apache2.service.require(state('libapache2-mod-wsgi').pkg,
                            pkg='apache2') \\
                   .watch(file='/etc/apache2/httpd.conf')

    # we still need to set the name of the function declaration.
    apache2.service.running()

:ref:`include-declaration` objects can be created with the ``include`` function,
while :ref:`extend-declaration` objects can be created with the ``extend`` function,
whose arguments are just :ref:`function-declaration` objects.

.. code-block:: python

    include('edit.vim', 'http.server')
    extend(state('apache2').service.watch(file='/etc/httpd/httpd.conf')

The ``include`` function, by default, causes the included sls file to be rendered
as soon as the ``include`` function is called. It returns a list of rendered module
objects; sls files not rendered with the pydsl renderer return ``None``'s.
This behavior creates no :ref:`include-declaration`'s in the resulting high state
data structure.

.. code-block:: python

    import types

    # including multiple sls returns a list.
    _, mod = include('a-non-pydsl-sls', 'a-pydsl-sls')

    assert _ is None
    assert isinstance(slsmods[1], types.ModuleType)

    # including a single sls returns a single object
    mod = include('a-pydsl-sls')

    # myfunc is a function that calls state(...) to create more states.
    mod.myfunc(1, 2, "three")

Notice how you can define a reusable function in your pydsl sls module and then
call it via the module returned by ``include``.

It's still possible to do late includes by passing the ``delayed=True`` keyword
argument to ``include``.

.. code-block:: python

    include('edit.vim', 'http.server', delayed=True)

Above will just create a :ref:`include-declaration` in the rendered result, and
such call always returns ``None``.


Special integration with the `cmd` state
-----------------------------------------
Taking advantage of rendering a Python module, PyDSL allows you to declare a
state that calls a pre-defined Python function when the state is executed.

.. code-block:: python

    greeting = "hello world"
    def helper(something, *args, **kws):
        print greeting                # hello world
        print something, args, kws    # test123 ['a', 'b', 'c'] {'x': 1, 'y': 2}

    state().cmd.call(helper, "test123", 'a', 'b', 'c', x=1, y=2)

The `cmd.call` state function takes care of calling our ``helper`` function
with the arguments we specified in the states, and translates the return value
of our function into a structure expected by the state system.
See :func:`salt.states.cmd.call` for more information.


Implicit ordering of states
----------------------------
Salt states are explicitly ordered via :ref:`requisite-declaration`'s.
However, with `pydsl` it's possible to let the renderer track the order
of creation for :ref:`function-declaration` objects, and implicitly add
``require`` requisites for your states to enforce the ordering. This feature
is enabled by setting the ``ordered`` option on ``__pydsl__``.

.. note::
   this feature is only available if your minions are using Python >= 2.7.

.. code-block:: python

    include('some.sls.file')

    A = state('A').cmd.run(cwd='/var/tmp')
    extend(A)

    __pydsl__.set(ordered=True)

    for i in range(10):
        i = str(i)
        state(i).cmd.run('echo '+i, cwd='/')
    state('1').cmd.run('echo one')
    state('2').cmd.run(name='echo two')


Notice that the ``ordered`` option needs to be set after any ``extend`` calls.
This is to prevent `pydsl` from tracking the creation of a state function that's
passed to an ``extend`` call.

Above example should create states from ``0`` to ``9`` that will output ``0``,
``one``, ``two``, ``3``, ... ``9``, in that order.

It's important to know that `pydsl` tracks the *creations* of
:ref:`function-declaration` objects, and automatically adds a ``require`` requisite
to a :ref:`function-declaration` object that requires the last
:ref:`function-declaration` object created before it in the sls file.

This means later calls (perhaps to update the function's :ref:`function-arg-declaration`) to a previously created function declaration will not change the
order.


Render time state execution
-------------------------------------

When Salt processes a salt formula file, the file is rendered to salt's
high state data representation by a renderer before the states can be executed.
In the case of the `pydsl` renderer, the .sls file is executed as a python module
as it is being rendered which makes it easy to execute a state at render time.
In `pydsl`, executing one or more states at render time can be done by calling a
configured :ref:`ID-declaration` object.

.. code-block:: python

    #!pydsl

    s = state() # save for later invocation

    # configure it
    s.cmd.run('echo at render time', cwd='/')
    s.file.managed('target.txt', source='salt://source.txt')

    s() # execute the two states now

Once an :ref:`ID-declaration` is called at render time it is detached from the
sls module as if it was never defined.

.. note::
    If `implicit ordering` is enabled (i.e., via ``__pydsl__.set(ordered=True)``) then
    the *first* invocation of a :ref:`ID-declaration` object must be done before a
    new :ref:`function-declaration` is created.


Integration with the stateconf renderer
-----------------------------------------
The :doc:`salt.renderers.stateconf` renderer offers a few interesting features that
can be leveraged by the `pydsl` renderer. In particular, when using with the `pydsl`
renderer, we are interested in `stateconf`'s sls namespacing feature (via dot-prefixed
id declarations), as well as, the automatic `start` and `goal` states generation.

Now you can use `pydsl` with `stateconf` like this:

.. code-block:: python

    #!pydsl|stateconf -ps

    include('xxx', 'yyy')

    # ensure that states in xxx run BEFORE states in this file.
    extend(state('.start').stateconf.require(stateconf='xxx::goal'))

    # ensure that states in yyy run AFTER states in this file.
    extend(state('.goal').stateconf.require_in(stateconf='yyy::start'))

    __pydsl__.set(ordered=True)

    ...

``-s`` enables the generation of a stateconf `start` state, and ``-p`` lets us pipe
high state data rendered by `pydsl` to `stateconf`. This example shows that by
``require``-ing or ``require_in``-ing the included sls' `start` or `goal` states,
it's possible to ensure that the included sls files can be made to execute before
or after a state in the including sls file.

Importing custom Python modules
-------------------------------
To use a custom Python module inside a PyDSL state, place the module somewhere that
it can be loaded by the Salt loader, such as `_modules` in the `/srv/salt` directory.

Then, copy it to any minions as necessary by using `saltutil.sync_modules`.

To import into a PyDSL SLS, one must bypass the Python importer and insert it manually
by getting a reference from Python's `sys.modules` dictionary.

For example:

.. code-block:: python

    #!pydsl|stateconf -ps

    def main():
        my_mod = sys.modules['salt.loaded.ext.module.my_mod']

'''
from __future__ import absolute_import

import imp
from salt.ext.six import exec_
from salt.utils import pydsl
from salt.utils.pydsl import PyDslError
from salt.exceptions import SaltRenderError

__all__ = ['render']


def render(template, saltenv='base', sls='', tmplpath=None, rendered_sls=None, **kws):
    mod = imp.new_module(sls)
    # Note: mod object is transient. It's existence only lasts as long as
    #       the lowstate data structure that the highstate in the sls file
    #       is compiled to.

    mod.__name__ = sls

    # to workaround state.py's use of copy.deepcopy(chunk)
    mod.__deepcopy__ = lambda x: mod

    dsl_sls = pydsl.Sls(sls, saltenv, rendered_sls)
    mod.__dict__.update(
        __pydsl__=dsl_sls,
        include=_wrap_sls(dsl_sls.include),
        extend=_wrap_sls(dsl_sls.extend),
        state=_wrap_sls(dsl_sls.state),
        __salt__=__salt__,
        __grains__=__grains__,
        __opts__=__opts__,
        __pillar__=__pillar__,
        __env__=saltenv,
        __sls__=sls,
        __file__=tmplpath,
        **kws)

    dsl_sls.get_render_stack().append(dsl_sls)
    exec_(template.read(), mod.__dict__)
    highstate = dsl_sls.to_highstate(mod)
    dsl_sls.get_render_stack().pop()
    return highstate


def _wrap_sls(method):
    def _sls_method(*args, **kws):
        sls = pydsl.Sls.get_render_stack()[-1]
        try:
            return getattr(sls, method.__name__)(*args, **kws)
        except PyDslError as exc:
            raise SaltRenderError(exc)
    return _sls_method

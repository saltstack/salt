- Feature Name: Batch mode SLS syntax
- Start Date: November 17, 2018.

# Summary
[summary]: #summary

Enhance SLS syntax with simpler way of writing "things".

# Motivation
[motivation]: #motivation

Writing SLS can be not always easy and friendly. Especially when you
want to do various operations on the same object. Main complain is
heard that in order to do something _again_ or run the same function
e.g. on the same file, one would need to create another ID for it.

The following example will get content of `/etc/<something>-release`,
based on `os_family` grain, if it is e.g. `RedHat`:

```yaml
rhelrelease:
  cmd.run:
    - name: cat /etc/redhat-release
    - onlyif: test -f /etc/redhat-release

centosrelease:
  cmd.run:
    - name: cat /etc/centos-release
    - onlyif: test -f /etc/centos-release
```

This will return a structure with an empty `rhelrelease` and content
of the release file under `centosrelease`. From API point of view, one
would need to check both keys in the structure.

Of course, it is possible to write it a bit better then that,
something like:

```jinja
{% if grains['os_family'] == 'RedHat' %}
{% set releasefile = 'centos' if grains['os'] == 'CentOS' else 'redhat' %}

release:
  cmd.run:
    - name: cat /etc/{{ releasefile }}-release
    - onlyif: test -f /etc/{{ releasefile }}-release
{%endif%}
```

It is still gets more complicated if older opensuse or SLES machines
also needs to be looked up. And yet this SLS is not finished as even
more careful logic needed to be added in order to handle cases where
no OS is detected. At this point SLS is no longer simple and
declarative, but looks more like programming.

We can make it simpler. For example as follows:


```jinja
release:
  cmd:
    {% for releasefile in ['redhat', 'centos', 'SuSE', 'sles'] %}
    - run:
      - name: cat /etc/{{releasefile}}-release
      - onlyif: test -f /etc/{{releasefile}}-release
    {% endfor %}
```

In the example above, the for-loop will just generate four times same
statement to call `cmd.run` function, reusing already built-in check
on `onlyif`. That said, no more need to figure out what OS name
belongs to what family etc.

The example above only made for show-case to let you get the idea.

# Design
[design]: #detailed-design

## How batch-mode syntax is used?

As simple as _not_ specifying particular function. Typically, in Salt
it is done this way:

```yaml
/etc/some.conf:
  somemodule.some_function:  # <--- here!
    - params...
```

The simple syntax will be invoked as so:

```yaml
/etc/some.conf:
  somemodule:  # <--- just like that, no function
    - some_function:
      - params ...
```

Of course, in single call this dosn't make much sense and is actually
one line more to write. However, if there is more one operation that
needed to be done, this makes a big difference. Since it is impossible
to have more than one same ID, you will be required to write different
IDs for the _same group_ of tasks, if we grouping them by the targeted
object. This results into something like this:


```yaml
do_something_with_my_config:
  somemodule.some_function:
    - name: /etc/some.conf
    - params ....

do_something_with_my_config_again:
  somemodule.some_other_function:
    - name: /etc/some.conf
    - params ....

do_something_with_my_config_and_over_again:
  somemodule.some_third_function:
    - name: /etc/some.conf
    - params ....
```

With the batch-mode, the same above can be re-written in much more
efficient way as follows:

```yaml
/etc/some.conf:
  somemodule:
    - some_function
      - params ....
    - some_other_function
      - params ....
    - some_third_function
      - params ....
```

## How does it work?

It works in three steps:

1. During state compile, compiler finds that there is no end function
   defined, then it injects `__call__` function name into the
   state. Essentially, referring to the example above, state will be
   simply altered to `somemodule.__call__`, but transparently for the
   user. LazyLoader does not allow any functions that starts with `_`
   as they are considered private/hidden. The `__call__` is an
   exception but it should be still impossible to invoke it from the
   module directly.

2. When LazyLoader loads a module, it will inject a generic function
   named `__call__` at the module level. If such function is already
   defined inside the module, LazyLoader will not inject that function
   therefore.

3. The `__call__` function takes a list of sets structure, as shown above,
   assuming that the key of the set is the function name of the parent
   element `somemodule`, which is a module name, and essentially
   performs the following:

```python
ret = []
for function_name in functions:
    args, kwargs = functions[function_name]['args'], functions[function_name]['kwargs']
    ret.append(getattr(this_module_instance, function_name)(*args, **kwargs))
```

## What needs to be changed in existing modules?

Nothing. Also no changes to any future modules, yet to be written. If
module has non-traditional way of exposing methods, e.g. implemented
as class or functions made dynamically, in this case `__call__` should
be made separately for that. However, since this is advanced way of
making modules, developer already knows what he is doing in this case.

Or "lazy" implementation, if one wants to just turn this feature off:

```python

__call__ = lambda (*a, **k): raise SaltNotSupportedError()
```

## Impact on existing ecosystem

No impact. Performance and default syntax should stay unchanged.

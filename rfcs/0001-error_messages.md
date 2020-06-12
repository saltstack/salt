- Feature Name: Allow packagers to have custom error/suggestion messages
- Start Date: Tue 12 Jun, 2018
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

Extract error messages in separate files to allow packagers to customize them

# Motivation
[motivation]: #motivation

Having the errors spread everywhere makes it harder to maintain and document them.
In addition to the above, sometimes the packagers need a way to have custom error/suggestions messages in order to point to the right package names depending on the context (eg: OS)
An example of packge suggestion could be with salt-ssh cross-version (SUSE has own package names) and/or modules dependencies.
(when some module needs a package to be installed in order to work it could point to the right name and make user's life easy)

# Design
[design]: #detailed-design

### Current Design

At the moment, the errors are spread within the code.

Examples:

- state.py:
    - https://github.com/saltstack/salt/blob/713ae1dca7f100e6ce19a7a2b714e0b2e168d0c1/salt/state.py#L443
    - https://github.com/saltstack/salt/blob/713ae1dca7f100e6ce19a7a2b714e0b2e168d0c1/salt/state.py#L478

- salt-ssh:
    - https://github.com/saltstack/salt/blob/develop/salt/client/ssh/__init__.py#L1396-L1457

### Proposed Design

The propasal is to use gettext.
This would not also allow for overriding error messages with vendor specific ones but also allow for translations.

Using gettext to override an error message would require the following:

1. Change the source files to use gettext

`salt/client/ssh/__init__.py`
```python
import gettext

t = gettext.translation('salt-ssh', '/usr/share/salt/locale')
_ = t.ugettext

# this could be converted to
# from salt.utils.gettext import gt
# t = gt.translation('salt-ssh', '/usr/share/salt/locale')
# _gt = t.ugettext
# See also: https://docs.python.org/3/library/gettext.html#class-based-api to maybe avoid installing on every file

...

                2: {
                    6: 'Install Python 2.7 / Python 3 Salt dependencies on the Salt SSH master \n'
                       'to interact with Python 2.7 / Python 3 targets',
                    7: _('Install Python {0} / Python 3 Salt dependencies on the Salt SSH master \n'
                       'to interact with Python {0} / Python 3 targets').format('2.6'),
                },

...
```

2. Use `xgettext` to gather the strings and generate the .pot file

```
xgettext ./salt/client/ssh/__init__.py -o /usr/share/salt/locale/salt-ssh.pot
```

```
# SOME DESCRIPTIVE TITLE.
# Copyright (C) YEAR THE PACKAGE'S COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2018-07-23 15:42+0000\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=CHARSET\n"
"Content-Transfer-Encoding: 8bit\n"

#: /usr/lib/python2.7/site-packages/salt/client/ssh/__init__.py:1399
#, python-brace-format
msgid ""
"Install Python {0} / Python 3 Salt dependencies on the Salt SSH master \n"
"to interact with Python {0} / Python 3 targets"
msgstr ""
```

3. Use `msginit` to generate the .po file:

```
msginit -i /usr/share/salt/locale/salt-ssh.pot -o /usr/share/salt/locale/salt-ssh.po
```

4. Edit the salt-ssh.po file:

```
# English translations for PACKAGE package.
# Copyright (C) 2018 THE PACKAGE'S COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# root <root@ef310f8b9f70>, 2018.
#
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2018-07-23 15:42+0000\n"
"PO-Revision-Date: 2018-07-23 15:42+0000\n"
"Last-Translator: root <root@ef310f8b9f70>\n"
"Language-Team: English\n"
"Language: en_US\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: /usr/lib/python2.7/site-packages/salt/client/ssh/__init__.py:1399
#, python-brace-format
msgid ""
"Install Python {0} / Python 3 Salt dependencies on the Salt SSH master \n"
"to interact with Python {0} / Python 3 targets"
msgstr ""
"My message: {0}"
```

5. Use `msgfmt' to generate the .mo file:

```
msgfmt /usr/share/salt/locale/salt-ssh.po -o /usr/share/salt/locale/en_US/LC_MESSAGES/salt-ssh.mo
```

See the new message:

```
bash-4.3# salt-ssh -l quiet -i --out json --key-deploy --passwd admin123 container__HjUVR test.ping
{
    "container__HjUVR": {
        "retcode": 10,
        "stderr": "",
        "stdout": "ERROR: Python version error. Recommendation(s) follow:\nMy message: 2.6"
    }
}
```

The .mo files can be provided in packages by different vendors.


### Notes

There might be cases where the messages need to contain some dynamic parts in which case we could store them as string templates and populate them before displaying or find a better solution if needed.

## Alternatives
[alternatives]: #alternatives

Open for suggestions.

## Unresolved questions
[unresolved]: #unresolved-questions

- how to allow modules to implement their own error messages?
- how to handle the unique identifiers? should we have different scopes?

# Drawbacks
[drawbacks]: #drawbacks


# Trade-offs

- maintaining an index of unique error messages is not ~desired~ easy in a modular system


"""
Custom configparser classes
"""

import re
from configparser import *  # pylint: disable=no-name-in-module,wildcard-import,unused-wildcard-import

import salt.utils.stringutils

try:
    from collections import OrderedDict as _default_dict
except ImportError:
    # fallback for setup.py which hasn't yet built _collections
    _default_dict = dict


# pylint: disable=string-substitution-usage-error
class GitConfigParser(RawConfigParser):
    """
    Custom ConfigParser which reads and writes git config files.

    READ A GIT CONFIG FILE INTO THE PARSER OBJECT

    >>> import salt.utils.configparser
    >>> conf = salt.utils.configparser.GitConfigParser()
    >>> conf.read('/home/user/.git/config')

    MAKE SOME CHANGES

    >>> # Change user.email
    >>> conf.set('user', 'email', 'myaddress@mydomain.tld')
    >>> # Add another refspec to the "origin" remote's "fetch" multivar
    >>> conf.set_multivar('remote "origin"', 'fetch', '+refs/tags/*:refs/tags/*')

    WRITE THE CONFIG TO A FILEHANDLE

    >>> import salt.utils.files
    >>> with salt.utils.files.fopen('/home/user/.git/config', 'w') as fh:
    ...     conf.write(fh)
    >>>
    """

    DEFAULTSECT = "DEFAULT"
    SPACEINDENT = " " * 8

    # pylint: disable=useless-super-delegation
    def __init__(
        self,
        defaults=None,
        dict_type=_default_dict,
        allow_no_value=True,
    ):
        """
        Changes default value for allow_no_value from False to True
        """
        super().__init__(defaults, dict_type, allow_no_value)

    # pylint: enable=useless-super-delegation

    def _read(self, fp, fpname):
        """
        Makes the following changes from the RawConfigParser:

        1. Strip leading tabs from non-section-header lines.
        2. Treat 8 spaces at the beginning of a line as a tab.
        3. Treat lines beginning with a tab as options.
        4. Drops support for continuation lines.
        5. Multiple values for a given option are stored as a list.
        6. Keys and values are decoded to the system encoding.
        """
        cursect = None  # None, or a dictionary
        optname = None
        lineno = 0
        e = None  # None, or an exception
        while True:
            line = salt.utils.stringutils.to_unicode(fp.readline())
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if line.strip() == "" or line[0] in "#;":
                continue
            if line.split(None, 1)[0].lower() == "rem" and line[0] in "rR":
                # no leading whitespace
                continue
            # Replace space indentation with a tab. Allows parser to work
            # properly in cases where someone has edited the git config by hand
            # and indented using spaces instead of tabs.
            if line.startswith(self.SPACEINDENT):
                line = "\t" + line[len(self.SPACEINDENT) :]
            # is it a section header?
            mo = self.SECTCRE.match(line)
            if mo:
                sectname = mo.group("header")
                if sectname in self._sections:
                    cursect = self._sections[sectname]
                elif sectname == self.DEFAULTSECT:
                    cursect = self._defaults
                else:
                    cursect = self._dict()
                    self._sections[sectname] = cursect
                # So sections can't start with a continuation line
                optname = None
            # no section header in the file?
            elif cursect is None:
                raise MissingSectionHeaderError(  # pylint: disable=undefined-variable
                    salt.utils.stringutils.to_str(fpname),
                    lineno,
                    salt.utils.stringutils.to_str(line),
                )
            # an option line?
            else:
                mo = self._optcre.match(line.lstrip())
                if mo:
                    optname, vi, optval = mo.group("option", "vi", "value")
                    optname = self.optionxform(optname.rstrip())
                    if optval is None:
                        optval = ""
                    if optval:
                        if vi in ("=", ":") and ";" in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(";")
                            if pos != -1 and optval[pos - 1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # Empty strings should be considered as blank strings
                        if optval in ('""', "''"):
                            optval = ""
                    self._add_option(cursect, optname, optval)
                else:
                    # a non-fatal parsing error occurred.  set up the
                    # exception but keep going. the exception will be
                    # raised at the end of the file and will contain a
                    # list of all bogus lines
                    if not e:
                        e = ParsingError(fpname)  # pylint: disable=undefined-variable
                    e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e  # pylint: disable=raising-bad-type

    def _string_check(self, value, allow_list=False):
        """
        Based on the string-checking code from the SafeConfigParser's set()
        function, this enforces string values for config options.
        """
        if self._optcre is self.OPTCRE or value:
            is_list = isinstance(value, list)
            if is_list and not allow_list:
                raise TypeError(
                    "option value cannot be a list unless allow_list is True"
                )
            elif not is_list:
                value = [value]
            if not all(isinstance(x, str) for x in value):
                raise TypeError("option values must be strings")

    def get(self, section, option, as_list=False):  # pylint: disable=arguments-differ
        """
        Adds an optional "as_list" argument to ensure a list is returned. This
        is helpful when iterating over an option which may or may not be a
        multivar.
        """
        ret = super().get(section, option)
        if as_list and not isinstance(ret, list):
            ret = [ret]
        return ret

    def set(self, section, option, value=""):
        """
        This is overridden from the RawConfigParser merely to change the
        default value for the 'value' argument.
        """
        self._string_check(value)
        super().set(section, option, value)

    def _add_option(self, sectdict, key, value):
        if isinstance(value, list):
            sectdict[key] = value
        elif isinstance(value, str):
            try:
                sectdict[key].append(value)
            except KeyError:
                # Key not present, set it
                sectdict[key] = value
            except AttributeError:
                # Key is present but the value is not a list. Make it into a list
                # and then append to it.
                sectdict[key] = [sectdict[key]]
                sectdict[key].append(value)
        else:
            raise TypeError(
                "Expected str or list for option value, got %s" % type(value).__name__
            )

    def set_multivar(self, section, option, value=""):
        """
        This function is unique to the GitConfigParser. It will add another
        value for the option if it already exists, converting the option's
        value to a list if applicable.

        If "value" is a list, then any existing values for the specified
        section and option will be replaced with the list being passed.
        """
        self._string_check(value, allow_list=True)
        if not section or section == self.DEFAULTSECT:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise NoSectionError(  # pylint: disable=undefined-variable
                    salt.utils.stringutils.to_str(section)
                )
        key = self.optionxform(option)
        self._add_option(sectdict, key, value)

    def remove_option_regexp(self, section, option, expr):
        """
        Remove an option with a value matching the expression. Works on single
        values and multivars.
        """
        if not section or section == self.DEFAULTSECT:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise NoSectionError(  # pylint: disable=undefined-variable
                    salt.utils.stringutils.to_str(section)
                )
        option = self.optionxform(option)
        if option not in sectdict:
            return False
        regexp = re.compile(expr)
        if isinstance(sectdict[option], list):
            new_list = [x for x in sectdict[option] if not regexp.search(x)]
            # Revert back to a list if we removed all but one item
            if len(new_list) == 1:
                new_list = new_list[0]
            existed = new_list != sectdict[option]
            if existed:
                del sectdict[option]
                sectdict[option] = new_list
            del new_list
        else:
            existed = bool(regexp.search(sectdict[option]))
            if existed:
                del sectdict[option]
        return existed

    def write(self, fp_):  # pylint: disable=arguments-differ
        """
        Makes the following changes from the RawConfigParser:

        1. Prepends options with a tab character.
        2. Does not write a blank line between sections.
        3. When an option's value is a list, a line for each option is written.
           This allows us to support multivars like a remote's "fetch" option.
        4. Drops support for continuation lines.
        """
        convert = (
            salt.utils.stringutils.to_bytes
            if "b" in fp_.mode
            else salt.utils.stringutils.to_str
        )
        if self._defaults:
            fp_.write(convert("[%s]\n" % self.DEFAULTSECT))
            for (key, value) in self._defaults.items():
                value = salt.utils.stringutils.to_unicode(value).replace("\n", "\n\t")
                fp_.write(convert("{} = {}\n".format(key, value)))
        for section in self._sections:
            fp_.write(convert("[%s]\n" % section))
            for (key, value) in self._sections[section].items():
                if (value is not None) or (self._optcre == self.OPTCRE):
                    if not isinstance(value, list):
                        value = [value]
                    for item in value:
                        fp_.write(convert("\t%s\n" % " = ".join((key, item)).rstrip()))

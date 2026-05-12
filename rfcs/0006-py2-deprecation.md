- Feature Name: End of Python 2 support in SaltStack
- Start Date: 2019-01-30
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

In light of Python 2.7 reaching its end of life (EOL) on Jan 1st 2020, Python 2 will be deprecated from SaltStack no earlier then the Sodium release, that is either the Sodium release or a later release.

# Motivation
[motivation]: #motivation

Python 2.7 will reach it’s official end of life (EOL) on [January 1st, 2020](https://devguide.python.org/#branchstatus) and post that, it will no longer be supported by its maintainers. Consequently, SaltStack team will retire Python 2.7 support in SaltStack.

The end of Python 2.7 support will enable SaltStack to focus its effort on better supporting Python 3.4+.

[Python 2.x is legacy, Python 3.x is the present and future of the language](https://wiki.python.org/moin/Python2orPython3)


# Design
[design]: #detailed-design

Python 2 will be deprecated from SaltStack no earlier than the Sodium release (tentative release date is Feb 2020), that is either the Sodium release or a later release. Keeping in mind SaltStack’s policy of announcing ‘end of support’ at least 2 major releases before the intended changes takes place, Sodium or a later release has been chosen as a suitable deadline for Python 2 deprecation.

**Migration:**
After carefully evaluating the list of Python 3 versions supported by different operating systems and by also considering the EOL for all these operating systems [1]* (as denoted in below grid) and [EOL of Python branches](https://devguide.python.org/#branchstatus)[2]*, SaltStack team proposes to support Python 3.6 from Sodium or a later release. If the Sodium release is delayed by 3 months more than its tentative release date of Feb 2020, Python 3.6 support release can instead fallback to the estimated date of Feb 2020. Below grid also lowers the motivation to support Python 3.5 at any given time as the oldest supported version due to the fact that most distributions have moved from 3.4 directly to 3.6. Versions of SaltStack released before the cutoff release will continue to support python 2.7 until they reach end of life.

[![Grid.png](https://i.postimg.cc/V62Wh9nY/Grid.png)](https://postimg.cc/xJymJz67)

By migrating completely to Python 3.6, SaltStack can then utilize asynchronous programming which in turn gives performance benefits to the end users of SaltStack.

Note 1: SaltStack currently supports master and minions running on different versions of Python such as salt master running on Python 2, minion running on Python 3 and vice versa. This support will not change in this transition as a change in Python interpreter does not mandate a change in network protocol.

Note 2: The version of OpenSSL that SaltStack will support will be determined by the Python version supported by SaltStack. Check [pyOpenSSL release page](https://pypi.org/project/pyOpenSSL/#history) to identify the which versions of Python are supported by pyOpenSSL.

Note 3: Python 3.6 has announced [deprecation for OpenSSL versions](https://docs.python.org/3/library/ssl.html) before 1.0.2, while Python 3.6 will build against OpenSSL 1.0.1 Python 3.7 will not. As such we need to be careful not to mandate use of any features of OpenSSL 1.0.2 until 1.0.1 is also fully deprecated by upstream vendors.

## Alternatives
[alternatives]: #alternatives

- SaltStack drops support for Python 2.7 in **Neon** (tentative release date is August 2019) and continues supporting **Python 3.4. Python 3.6** then becomes the oldest supported version in **Sodium**.
- SaltStack drops support for Python 2.7 in **Neon** (tentative release date is August 2019) and continues supporting **Python 3.4. Python 3.6** then becomes the oldest supported version in **Magnesium**.
- SaltStack drops support for Python 2.7 and starts supporting **Python 3.4** in **Sodium** and drops support for Python 3.4 in favor of **Python 3.6** in **Magnesium**.


## Packaging Considerations
[Packaging]: #Packaging-Considerations

Which Python packaging solutions to use - EPEL (Extra Packages for Enterprise Linux)/SC (Software Collections) repository or monolithic packaging?

While the exact nature of packages delivered by SaltStack is not being laid out in this RFC, SaltStack team guarantees that package updates will be made available for smoother transition.


# Actions
[Actions]: #Actions

SaltStack users will see the Python 2 deprecation implemented in the next few releases as follows:
1. Future releases of SaltStack will have a Python 2 deprecation warning.
2. SaltStack will create packages that will allow for a smooth transition for users.
3. In accordance with the schedule which is decided upon testing for Python 2 will be turned off.
4. The six library will be removed from SaltStack slowly over time as well as all compat library use.
5. Existing monolithic installers will move solely to Python 3 only for the cutoff release, such as the Windows installer.


# References
[References]: #References

[1]* Below is the list of all the sources from which EOL for the below Operating system versions were retrieved

|Operating Systems                          |Sources                         |
|-------------------------------|-----------------------------|
|RHEL 6              |https://access.redhat.com/support/policy/updates/errata ‘End of Maintenance Support 2 (Product retirement)’ |
|RHEL 7              | https://access.redhat.com/support/policy/updates/errata ‘End of Maintenance Support 2 (Product retirement)’ |
|Amazon Linux 2      | https://aws.amazon.com/amazon-linux-2/faqs/ |
|SLES 11             | https://www.suse.com/lifecycle/ |
|SLES 12             | https://www.suse.com/lifecycle/ |
|SLES 15             | https://www.suse.com/lifecycle/ |
|OpenSUSE 15         | https://en.opensuse.org/Lifetime |
|Debian 9 (Stretch)  | https://wiki.debian.org/LTS/ |
|Debian 8 (Jesse)    | https://wiki.debian.org/LTS/ |
|Ubuntu 18.04        | https://wiki.ubuntu.com/Releases |
|Ubuntu 16.04        | https://wiki.ubuntu.com/Releases |
|Ubuntu 14.04        | https://wiki.ubuntu.com/Releases |
|FreeBSD 11          | https://lists.freebsd.org/pipermail/freebsd-announce/2018-September/001842.html |

[2]*  Excerpt from EOL of Python branches

[![States-of-python-branches.png](https://i.postimg.cc/sXrxxvYV/States-of-python-branches.png)](https://postimg.cc/Mc9qrZ34)

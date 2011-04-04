# Copyright 1999-2011 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: $
#
# http://devmanual.gentoo.org/index.html
#

PYTHON_DEPEND="2"
RESTRICT_PYTHON_ABIS="3.*"

inherit python

DESCRIPTION="remote execution manager"
HOMEPAGE="https://github.com/thatch45/salt"
SRC_URI="https://github.com/downloads/thatch45/salt/salt-0.7.0.tar.gz"

#LICENSE="GPL-2"
SLOT="0"
KEYWORDS="-* amd64 x86"
IUSE=""

RDEPEND="dev-lang/python
	dev-ruby/facter
	dev-python/pycrypto
	dev-python/m2crypto
	dev-python/pyyaml
	dev-python/pyzmq"
DEPEND="${RDEPEND}"

src_install() {
	./setup.py install --root=${D} --optimize=1 || die 
}


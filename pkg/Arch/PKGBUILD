# Maintainer: Thomas S Hatch <thatch45@gmail.com>

pkgname=salt
pkgver=0.6.0
pkgrel=1
pkgdesc="A remote execution and communication system built on zeromq"
arch=(any)
url="https://github.com/thatch45/salt"
license=("APACHE")
depends=('python2'
         'pyzmq'
         'python-m2crypto'
         'python-yaml'
         'pycrypto'
         'facter')
backup=('etc/salt/master' 
        'etc/salt/minion')
makedepends=()
optdepends=()
options=()
source=("$pkgname-$pkgver.tar.gz")
md5sums=('923fe5de8ec88900e70b6996ae3a2ff1')

package() {
  cd $srcdir/$pkgname-$pkgver

  python2 setup.py install --root=$pkgdir/ --optimize=1
  chmod +x $pkgdir/etc/rc.d/*
}

# Maintainer: Thomas S Hatch <thatch45@gmail.com>

pkgname=salt
pkgver=0.1
pkgrel=1
pkgdesc="A distributed remote execution system"
arch=(any)
url="https://github.com/thatch45/salt"
license=("APACHE")
depends=('python2'
         'pyzmq'
         'python-m2crypto'
         'python-yaml'
         'pycrypto')
makedepends=()
optdepends=()
options=()
source=("$pkgname-$pkgver.tar.gz")
md5sums=('923fe5de8ec88900e70b6996ae3a2ff1')

package() {
  cd $srcdir/$pkgname-$pkgver

  python2 setup.py install --root=$pkgdir/ --optimize=1
}

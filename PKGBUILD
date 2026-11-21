# Maintainer: NotAProton <git@notaproton.me>

pkgname=boxes-dev-bin
pkgver=1.0.1135
pkgrel=1
_debver=1.0.1135-362
_deb_x86_64='pool/main/b/boxes-dev/boxes-dev_1.0.1135_amd64.deb'
_deb_aarch64='pool/main/b/boxes-dev/boxes-dev_1.0.1135_arm64.deb'
pkgdesc='Cloud dev environments for agentic coding (boxes.dev desktop app)'
arch=('x86_64' 'aarch64')
url='https://boxes.dev'
license=('LicenseRef-proprietary')
depends=(
  'alsa-lib'
  'at-spi2-core'
  'gcc-libs'
  'gtk3'
  'hicolor-icon-theme'
  'libcups'
  'libglvnd'
  'libnotify'
  'libsecret'
  'libx11'
  'libxkbcommon'
  'libxss'
  'libxtst'
  'mesa'
  'nss'
  'util-linux-libs'
  'xdg-utils'
)
optdepends=(
  'org.freedesktop.secrets: store credentials in a system keyring'
)
provides=('boxes-dev')
conflicts=('boxes-dev')
options=('!strip' '!debug')
source_x86_64=("${pkgname}-${pkgver}-${pkgrel}-x86_64.deb::https://deploy.boxes.dev/desktop/linux/apt/${_deb_x86_64}")
source_aarch64=("${pkgname}-${pkgver}-${pkgrel}-aarch64.deb::https://deploy.boxes.dev/desktop/linux/apt/${_deb_aarch64}")
noextract=(
  "${pkgname}-${pkgver}-${pkgrel}-x86_64.deb"
  "${pkgname}-${pkgver}-${pkgrel}-aarch64.deb"
)
sha512sums_x86_64=('46c1b0fca83123cd3d7fb08d6db872b0be27eb46be1180a483175d08cd21723c6d573d9879d54770b196f13d31304a45e692608c35b637b9deb672aa36c8929d')
sha512sums_aarch64=('8de3d8a30ddeb1ae3976d732f8014ab49105105e2adde9ee5a99b1876201688d625190b70a458f6087cd3dc7200f6c79d315d78e9e6610f3f1c666680188ea58')

prepare() {
  rm -rf "${srcdir}/deb-extract"
  mkdir -p "${srcdir}/deb-extract"
  bsdtar -xf "${srcdir}/${pkgname}-${pkgver}-${pkgrel}-${CARCH}.deb" -C "${srcdir}/deb-extract"
}

package() {
  local data_tar=("${srcdir}"/deb-extract/data.tar.*)
  bsdtar --no-same-owner -xf "${data_tar[0]}" -C "${pkgdir}"

  rm -rf "${pkgdir}/usr/share/doc"

  install -d "${pkgdir}/usr/bin"
  ln -s "/opt/Boxes.dev/boxes-dev" "${pkgdir}/usr/bin/boxes-dev"

  install -Dm644 "${pkgdir}/opt/Boxes.dev/LICENSE.electron.txt" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE.electron.txt"
  install -Dm644 "${pkgdir}/opt/Boxes.dev/LICENSES.chromium.html" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSES.chromium.html"
}

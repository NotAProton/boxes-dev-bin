# Maintainer: NotAProton <git@notaproton.me>

pkgname=boxes-dev-bin
pkgver=1.0.1138
pkgrel=1
_debver=1.0.1138-365
_deb_x86_64='pool/main/b/boxes-dev/boxes-dev_1.0.1138_amd64.deb'
_deb_aarch64='pool/main/b/boxes-dev/boxes-dev_1.0.1138_arm64.deb'
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
sha512sums_x86_64=('7ffbecb6e031314a7a4f81f4e03555d7bcdbc54efc75f0e9d16c1a646eeae69f7c689d4ef3788e8d920535002c5297673bb9c462976813e06672f92d61c65250')
sha512sums_aarch64=('1fd3b540d693b51c8a8208040a18e3c0ff56c744f333677ed088509dcb43951a15493dd06f5bb40a6bddd3d72d30ce595c128e257ff496e5a82ec39ff69e3858')

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

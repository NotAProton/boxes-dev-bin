boxes-dev-bin
=============

Arch Linux PKGBUILD for the boxes.dev desktop app (x86_64 and aarch64),
repacking the upstream .deb from deploy.boxes.dev.

This lives on GitHub for now because new AUR account registrations are
paused.


Install with paru (automatic updates)
-------------------------------------

Add this repo to ~/.config/paru/paru.conf (or /etc/paru.conf):

    [boxes-dev]
    Url = https://github.com/NotAProton/boxes-dev-bin

Sync the repo and install the package:

    paru -Sy --pkgbuilds
    paru -S boxes-dev-bin

After that, normal "paru" or "paru -Syu" runs pull updates from this
repo, show the PKGBUILD diff for review, and rebuild from the new
upstream .deb when boxes.dev releases a new version.

If you do not want to confirm diffs from the update bot, add SkipReview
under [boxes-dev] in paru.conf.


Install manually with makepkg
-----------------------------

    git clone https://github.com/NotAProton/boxes-dev-bin.git
    cd boxes-dev-bin
    makepkg -si

To update later, run "git pull" and "makepkg -si" in that directory.


How updates work
----------------

A GitHub Actions workflow (.github/workflows/update.yml) checks the
upstream APT repository every 6 hours:

    https://deploy.boxes.dev/desktop/linux/apt/dists/stable/InRelease

The script verifies InRelease against the pinned upstream GPG key
(boxes-dev-linux-packages.asc, fingerprint
5FDFB9AA42D91A97E05F962197982567A1FEC954), checks the SHA512 hashes of
the amd64 and arm64 Packages files, and updates PKGBUILD and .SRCINFO
when both architectures are on a newer release.

This repository holds no binaries. makepkg downloads the .deb directly
from deploy.boxes.dev and verifies its SHA512 locally.


What the package installs
-------------------------

    /opt/Boxes.dev/                     Upstream Electron application
    /usr/bin/boxes-dev                  Symlink to /opt/Boxes.dev/boxes-dev
    /usr/share/applications/boxes-dev.desktop
    /usr/share/icons/hicolor/*/apps/boxes-dev.png
    /usr/share/licenses/boxes-dev-bin/  Bundled Electron and Chromium licenses

Packaging extracts only data.tar.* and ignores Debian maintainer scripts
(control.tar.*), so nothing under /etc/apt is modified.


Notes
-----

This is an unofficial package. boxes.dev is proprietary software from
Boxes, Inc. (https://boxes.dev).

Because the bundle is around 140 MB, setting PKGEXT='.pkg.tar' in
~/.makepkg.conf skips recompressing the package locally before pacman
installs it.

Once AUR registrations reopen, this PKGBUILD is intended to move to the
AUR as boxes-dev-bin.

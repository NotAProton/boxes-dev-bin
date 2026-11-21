#!/usr/bin/env python3
"""Check the upstream boxes.dev APT repo and update PKGBUILD when needed."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APT_BASE = "https://deploy.boxes.dev/desktop/linux/apt"
EXPECTED_FPR = "5FDFB9AA42D91A97E05F962197982567A1FEC954"
USER_AGENT = "boxes-dev-bin-pkgbuild-updater/1.0 (+https://github.com/NotAProton/boxes-dev-bin)"
TIMEOUT_SEC = 30
MAX_RETRIES = 3


def _request_with_retry(url: str, *, method: str = "GET") -> tuple[bytes, http.client.HTTPMessage]:
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(
            url, method=method, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"{method} {url} returned HTTP {resp.status}")
                body = b"" if method == "HEAD" else resp.read()
                return body, resp.headers
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == MAX_RETRIES:
                raise
        except (urllib.error.URLError, OSError, http.client.HTTPException):
            if attempt == MAX_RETRIES:
                raise
        time.sleep(attempt)
    raise AssertionError("unreachable")


def fetch_bytes(url: str) -> bytes:
    body, _ = _request_with_retry(url, method="GET")
    return body


def head_check(url: str, expected_size: int) -> None:
    _, headers = _request_with_retry(url, method="HEAD")
    cl = headers.get("Content-Length")
    if cl is not None and int(cl) != expected_size:
        raise RuntimeError(
            f"HEAD {url} Content-Length {cl} != expected {expected_size}"
        )


def verify_inrelease(inrelease_bytes: bytes, key_path: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="boxes-gpg-") as tmpdir:
        gpghome = Path(tmpdir) / "gnupg"
        gpghome.mkdir(mode=0o700)
        env = {**os.environ, "GNUPGHOME": str(gpghome)}

        subprocess.run(
            ["gpg", "--batch", "--quiet", "--import", str(key_path)],
            env=env,
            check=True,
        )

        fpr_out = subprocess.check_output(
            ["gpg", "--batch", "--with-colons", "--fingerprint"],
            env=env,
            text=True,
        )
        found_fprs = {
            line.split(":")[9]
            for line in fpr_out.splitlines()
            if line.startswith("fpr:") and len(line.split(":")) > 9
        }
        if EXPECTED_FPR not in found_fprs:
            raise RuntimeError(
                f"Expected GPG fingerprint {EXPECTED_FPR} missing from {key_path}"
            )

        inrelease_path = Path(tmpdir) / "InRelease"
        payload_path = Path(tmpdir) / "Release"
        inrelease_path.write_bytes(inrelease_bytes)

        proc = subprocess.run(
            [
                "gpg",
                "--batch",
                "--status-fd",
                "1",
                "--verify",
                "--output",
                str(payload_path),
                str(inrelease_path),
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"GPG verification of InRelease failed:\n{proc.stderr.strip()}"
            )

        validsig_ok = False
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "[GNUPG:]" and parts[1] == "VALIDSIG":
                signing_fpr = parts[2]
                primary_fpr = parts[11] if len(parts) > 11 else parts[-1]
                if EXPECTED_FPR in (signing_fpr, primary_fpr):
                    validsig_ok = True
                    break

        if not validsig_ok:
            raise RuntimeError(
                f"InRelease VALIDSIG did not match expected fingerprint {EXPECTED_FPR}:\n"
                f"{proc.stdout.strip()}"
            )

        return payload_path.read_text(encoding="utf-8")


def parse_inrelease_sha512(release_text: str) -> dict[str, tuple[str, int]]:
    entries: dict[str, tuple[str, int]] = {}
    in_sha512 = False
    for line in release_text.splitlines():
        if line == "SHA512:":
            in_sha512 = True
            continue
        if in_sha512:
            if not line.startswith((" ", "\t")):
                break
            parts = line.split()
            if len(parts) == 3:
                digest, size_str, rel_path = parts
                entries[rel_path] = (digest.lower(), int(size_str))
    if not entries:
        raise RuntimeError("No SHA512 entries found in verified InRelease")
    return entries


def parse_packages_stanzas(packages_text: str) -> list[dict[str, str]]:
    stanzas: list[dict[str, str]] = []
    current: dict[str, str] = {}
    last_key: str | None = None

    for line in packages_text.splitlines():
        if not line.strip():
            if current:
                stanzas.append(current)
                current = {}
                last_key = None
            continue
        if line[0] in (" ", "\t"):
            if last_key is not None:
                current[last_key] = f"{current[last_key]}\n{line.strip()}"
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            current[key] = val.strip()
            last_key = key

    if current:
        stanzas.append(current)
    return stanzas


def _deb_part_key(part: str) -> list[tuple[int, int | str]]:
    """Convert a Debian version component into comparable tokens."""
    tokens: list[tuple[int, int | str]] = []
    i = 0
    n = len(part)
    while i < n:
        non_digits: list[int] = []
        while i < n and not part[i].isdigit():
            ch = part[i]
            if ch == "~":
                non_digits.append(-1)
            elif ch.isalpha():
                non_digits.append(ord(ch))
            else:
                non_digits.append(ord(ch) + 256)
            i += 1
        if non_digits:
            tokens.append((0, tuple(non_digits)))  # type: ignore[arg-type]
        j = i
        while j < n and part[j].isdigit():
            j += 1
        if j > i:
            tokens.append((1, int(part[i:j])))
            i = j
    return tokens


def compare_deb_versions(a: str, b: str) -> int:
    """Return >0 if a > b, <0 if a < b, 0 if equal."""
    if a == b:
        return 0
    if shutil.which("dpkg"):
        if subprocess.run(["dpkg", "--compare-versions", a, "gt", b]).returncode == 0:
            return 1
        if subprocess.run(["dpkg", "--compare-versions", a, "lt", b]).returncode == 0:
            return -1
        return 0

    def split_evr(ver: str) -> tuple[int, str, str]:
        epoch = 0
        if ":" in ver:
            ep, ver = ver.split(":", 1)
            epoch = int(ep)
        if "-" in ver:
            up, rev = ver.rsplit("-", 1)
        else:
            up, rev = ver, "0"
        return epoch, up, rev

    ea, ua, ra = split_evr(a)
    eb, ub, rb = split_evr(b)
    if ea != eb:
        return 1 if ea > eb else -1
    ka, kb = (_deb_part_key(ua), _deb_part_key(ra)), (_deb_part_key(ub), _deb_part_key(rb))
    return 1 if ka > kb else (-1 if ka < kb else 0)


def fetch_latest_pkg(
    index_rel_path: str, release_hashes: dict[str, tuple[str, int]]
) -> dict[str, str]:
    if index_rel_path not in release_hashes:
        raise RuntimeError(f"{index_rel_path} missing from InRelease SHA512 list")
    expected_sha512, expected_size = release_hashes[index_rel_path]
    raw = fetch_bytes(f"{APT_BASE}/dists/stable/{index_rel_path}")
    if len(raw) != expected_size:
        raise RuntimeError(
            f"{index_rel_path} size {len(raw)} != InRelease size {expected_size}"
        )
    actual_sha512 = hashlib.sha512(raw).hexdigest()
    if actual_sha512 != expected_sha512:
        raise RuntimeError(
            f"{index_rel_path} SHA512 {actual_sha512} != InRelease {expected_sha512}"
        )

    matches = [
        stanza
        for stanza in parse_packages_stanzas(raw.decode("utf-8"))
        if stanza.get("Package") == "boxes-dev"
    ]
    if not matches:
        raise RuntimeError(f"Package 'boxes-dev' not found in {index_rel_path}")

    best = matches[0]
    for candidate in matches[1:]:
        if compare_deb_versions(candidate["Version"], best["Version"]) > 0:
            best = candidate

    for field in ("Version", "Filename", "Size", "SHA512"):
        if field not in best:
            raise RuntimeError(f"Missing {field} in {index_rel_path} stanza")
    return best


def deb_to_pkgver(debver: str) -> str:
    upstream = debver.rsplit("-", 1)[0] if "-" in debver else debver
    return upstream.replace("-", ".")


def extract_field(text: str, pattern: str, name: str) -> str:
    m = re.search(pattern, text, flags=re.MULTILINE)
    if not m:
        raise RuntimeError(f"Could not find {name} in PKGBUILD")
    return m.group(1)


def replace_field(text: str, pattern: str, replacement: str, name: str) -> str:
    updated, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(
            f"Expected 1 match for {name} in PKGBUILD, matched {count}"
        )
    return updated


def write_github_outputs(path_str: str | None, values: dict[str, str]) -> None:
    if not path_str:
        return
    out_path = Path(path_str)
    with out_path.open("a", encoding="utf-8") as fh:
        for key, val in values.items():
            fh.write(f"{key}={val}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pkgbuild", default="PKGBUILD", type=Path)
    parser.add_argument("--key", default="boxes-dev-linux-packages.asc", type=Path)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    inrelease_bytes = fetch_bytes(f"{APT_BASE}/dists/stable/InRelease")
    release_text = verify_inrelease(inrelease_bytes, args.key)
    release_hashes = parse_inrelease_sha512(release_text)

    amd64 = fetch_latest_pkg("main/binary-amd64/Packages", release_hashes)
    arm64 = fetch_latest_pkg("main/binary-arm64/Packages", release_hashes)

    if amd64["Version"] != arm64["Version"]:
        print(
            f"Architecture versions differ (amd64={amd64['Version']}, "
            f"arm64={arm64['Version']}); skipping update."
        )
        write_github_outputs(args.github_output, {"updated": "false"})
        return 0

    debver = amd64["Version"]
    new_pkgver = deb_to_pkgver(debver)
    deb_x86_64 = amd64["Filename"]
    deb_aarch64 = arm64["Filename"]
    sha_x86_64 = amd64["SHA512"].lower()
    sha_aarch64 = arm64["SHA512"].lower()

    pkgbuild_text = args.pkgbuild.read_text(encoding="utf-8")
    cur_pkgver = extract_field(pkgbuild_text, r"^pkgver=([^\s]+)$", "pkgver")
    cur_pkgrel = extract_field(pkgbuild_text, r"^pkgrel=(\d+)$", "pkgrel")
    cur_debver = extract_field(pkgbuild_text, r"^_debver=([^\s]+)$", "_debver")
    cur_deb_x86_64 = extract_field(
        pkgbuild_text, r"^_deb_x86_64='([^']+)'$", "_deb_x86_64"
    )
    cur_deb_aarch64 = extract_field(
        pkgbuild_text, r"^_deb_aarch64='([^']+)'$", "_deb_aarch64"
    )
    cur_sha_x86_64 = extract_field(
        pkgbuild_text,
        r"^sha512sums_x86_64=\('([0-9a-fA-F]+)'\)$",
        "sha512sums_x86_64",
    ).lower()
    cur_sha_aarch64 = extract_field(
        pkgbuild_text,
        r"^sha512sums_aarch64=\('([0-9a-fA-F]+)'\)$",
        "sha512sums_aarch64",
    ).lower()

    if (
        cur_debver == debver
        and cur_deb_x86_64 == deb_x86_64
        and cur_deb_aarch64 == deb_aarch64
        and cur_sha_x86_64 == sha_x86_64
        and cur_sha_aarch64 == sha_aarch64
    ):
        print(f"Already up to date ({debver})")
        write_github_outputs(args.github_output, {"updated": "false"})
        return 0

    head_check(f"{APT_BASE}/{deb_x86_64}", int(amd64["Size"]))
    head_check(f"{APT_BASE}/{deb_aarch64}", int(arm64["Size"]))

    new_pkgrel = "1" if new_pkgver != cur_pkgver else str(int(cur_pkgrel) + 1)

    pkgbuild_text = replace_field(
        pkgbuild_text, r"^pkgver=[^\s]+$", f"pkgver={new_pkgver}", "pkgver"
    )
    pkgbuild_text = replace_field(
        pkgbuild_text, r"^pkgrel=\d+$", f"pkgrel={new_pkgrel}", "pkgrel"
    )
    pkgbuild_text = replace_field(
        pkgbuild_text, r"^_debver=[^\s]+$", f"_debver={debver}", "_debver"
    )
    pkgbuild_text = replace_field(
        pkgbuild_text,
        r"^_deb_x86_64='[^']+'$",
        f"_deb_x86_64='{deb_x86_64}'",
        "_deb_x86_64",
    )
    pkgbuild_text = replace_field(
        pkgbuild_text,
        r"^_deb_aarch64='[^']+'$",
        f"_deb_aarch64='{deb_aarch64}'",
        "_deb_aarch64",
    )
    pkgbuild_text = replace_field(
        pkgbuild_text,
        r"^sha512sums_x86_64=\('[0-9a-fA-F]+'\)$",
        f"sha512sums_x86_64=('{sha_x86_64}')",
        "sha512sums_x86_64",
    )
    pkgbuild_text = replace_field(
        pkgbuild_text,
        r"^sha512sums_aarch64=\('[0-9a-fA-F]+'\)$",
        f"sha512sums_aarch64=('{sha_aarch64}')",
        "sha512sums_aarch64",
    )

    args.pkgbuild.write_text(pkgbuild_text, encoding="utf-8")
    print(f"Updated PKGBUILD to {new_pkgver}-{new_pkgrel} (deb {debver})")
    write_github_outputs(
        args.github_output,
        {
            "updated": "true",
            "pkgver": new_pkgver,
            "pkgrel": new_pkgrel,
            "debver": debver,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

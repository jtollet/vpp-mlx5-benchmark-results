#!/usr/bin/env python3
"""Reject lab identifiers while allowing exact public patch metadata."""

from __future__ import annotations

import ipaddress
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
MESSAGE_IDS = {
    "cover.1787347981.git.jtollet@cisco.com",
}
ALLOWED_PUBLIC_DOMAINS = {
    "creativecommons.org",
    "gerrit.fd.io",
    "kernel.googlesource.com",
    "lore.kernel.org",
    "matplotlib.org",
    "medium.com",
    "purl.org",
    "www.w3.org",
}
PATTERNS = {
    "IPv4 address": re.compile(
        r"(?<![0-9.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![0-9.])"
    ),
    "MAC address": re.compile(
        r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])"
    ),
    "PCI BDF": re.compile(
        r"(?i)(?<![0-9a-f])(?:[0-9a-f]{4}:)?[0-9a-f]{2}:[0-9a-f]{2}\.[0-7](?![0-9a-f])"
    ),
    "lab host/topology name": re.compile(
        r"(?i)\b(?:vpp|vmm)-\d+(?:-\d+)+\b|\bs\d+-t\d+-(?:sut|tg)\d*\b"
    ),
    "absolute home path": re.compile(r"(?:/home/|/Users/)[^\s`'\"]+"),
    "known hardware serial form": re.compile(r"(?i)\b(?:WZP\d{6,}|MT\d{6,}[A-Z0-9]*)\b"),
}
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL = re.compile(r"https?://[^\s)\]>]+")


def text_files():
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == SELF
            or ".git" in path.parts
            or path.suffix == ".png"
        ):
            continue
        yield path


def has_ipv6(line: str) -> bool:
    for token in re.findall(r"[0-9A-Fa-f:]{2,}", line):
        if ":" not in token:
            continue
        try:
            if isinstance(ipaddress.ip_address(token.strip("[](),;")), ipaddress.IPv6Address):
                return True
        except ValueError:
            pass
    return False


def main() -> int:
    findings: list[str] = []
    for path in text_files():
        relative = path.relative_to(ROOT)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            findings.append(f"{relative}: undecodable non-PNG file")
            continue
        for lineno, line in enumerate(lines, 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{relative}:{lineno}: {label}")
            if has_ipv6(line):
                findings.append(f"{relative}:{lineno}: IPv6 address")
            for match in EMAIL.finditer(line):
                exact_public_message_id = any(
                    match.group(0) in message_id and message_id in line
                    for message_id in MESSAGE_IDS
                )
                if not exact_public_message_id:
                    findings.append(f"{relative}:{lineno}: email outside public patch metadata")
            for match in URL.finditer(line):
                domain = (urlparse(match.group(0)).hostname or "").lower()
                if domain not in ALLOWED_PUBLIC_DOMAINS:
                    findings.append(f"{relative}:{lineno}: non-allow-listed URL domain {domain}")

    if findings:
        print("Public-data anonymization audit failed:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1

    print(
        "Anonymization audit passed: no lab IP/MAC/BDF/host/path/serial, "
        "and email/URL exceptions are limited to explicit public metadata."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""URL validation to limit server-side request forgery (SSRF) risks."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata"}


def _ip_is_unsafe(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def validate_url(url: str, allow_private: bool = False) -> tuple[bool, str]:
    """Return (ok, reason). Only public http and https destinations are allowed.

    Every hostname is resolved and each returned address is checked, so a public
    name that points at a private address is rejected. Redirect targets must be
    validated again by the caller on every hop.
    """
    if not url or not isinstance(url, str):
        return False, "The URL is empty."
    if len(url) > 2048:
        return False, "The URL is too long."
    try:
        p = urlparse(url)
    except ValueError:
        return False, "The URL could not be parsed."
    if p.scheme not in ("http", "https"):
        return False, "Only http and https URLs are supported."
    if not p.hostname:
        return False, "The URL has no hostname."
    if p.username or p.password:
        return False, "URLs containing credentials are not allowed."
    if p.port and p.port not in (80, 443, 8080, 8443):
        return False, "Unusual ports are blocked."
    host = p.hostname.lower()
    if allow_private:
        return True, "ok"
    if host in BLOCKED_HOSTNAMES or host.endswith((".local", ".internal", ".localhost")):
        return False, "Internal hostnames are blocked."
    try:
        ip = ipaddress.ip_address(host)
        if _ip_is_unsafe(ip):
            return False, "Private or reserved IP addresses are blocked."
        return True, "ok"
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, "The hostname could not be resolved."
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _ip_is_unsafe(ip):
            return False, "The hostname resolves to a private or reserved address."
    return True, "ok"

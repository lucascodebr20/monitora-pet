from __future__ import annotations

from urllib.parse import unquote, urlsplit, urlunsplit


def split_url_credentials(raw_url: str) -> tuple[str, str, str]:
    url = raw_url.strip()
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url, "", ""
    userinfo, _, hostport = parts.netloc.rpartition("@")
    username, _, password = userinfo.partition(":")
    clean = urlunsplit((parts.scheme, hostport, parts.path, parts.query, parts.fragment))
    return clean, unquote(username), unquote(password)

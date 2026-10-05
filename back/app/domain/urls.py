"""Regras sobre URLs de câmera."""

from __future__ import annotations

from urllib.parse import unquote, urlsplit, urlunsplit


def split_url_credentials(raw_url: str) -> tuple[str, str, str]:
    """Separa ``usuario:senha@`` de uma URL, devolvendo (url_limpa, usuario, senha).

    Manuais de fabricantes costumam fornecer ``rtsp://admin:senha@ip/...``. A senha nunca
    deve ser persistida dentro da URL, então ela é extraída para os campos próprios.
    ``host:porta`` é mantido literalmente: funciona com IPv6 entre colchetes, porta inválida
    ou host ausente.
    """
    url = raw_url.strip()
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url, "", ""
    userinfo, _, hostport = parts.netloc.rpartition("@")
    username, _, password = userinfo.partition(":")
    clean = urlunsplit((parts.scheme, hostport, parts.path, parts.query, parts.fragment))
    return clean, unquote(username), unquote(password)

"""
RAISE (Research Assessment Intelligence & Semantic Extraction)
Security Subsystem — Real Client IP & Edge Header Resolver
Resolves real client WAN IPs and Cloudflare telemetry headers with defensive precedence.
"""

from typing import Dict, Any, Optional


def resolve_client_ip(scope: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
    """
    Defensively extracts the real client IP address.
    Only trusts proxy headers (CF-Connecting-IP, X-Forwarded-For, X-Real-IP)
    when the incoming socket originates from a local proxy/tunnel (127.0.0.1, ::1, localhost).
    Direct or LAN connections use the raw socket IP.
    """
    if headers is None:
        raw_headers = scope.get("headers", [])
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in raw_headers}

    client = scope.get("client")
    socket_ip = (
        str(client[0]).strip()
        if client and isinstance(client, (list, tuple)) and len(client) > 0 and client[0]
        else "127.0.0.1"
    )

    # Only trust proxy/Cloudflare headers when the socket connection originates from local proxy/tunnel
    is_trusted_proxy = socket_ip in ("127.0.0.1", "::1", "localhost")

    if is_trusted_proxy:
        cf_ip = headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()

        xff = headers.get("x-forwarded-for")
        if xff and xff.strip():
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                return parts[0]

        x_real = headers.get("x-real-ip")
        if x_real and x_real.strip():
            return x_real.strip()

    return socket_ip


def extract_edge_telemetry(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Extracts Cloudflare edge telemetry headers for tracking and session identification.
    """
    return {
        "country": headers.get("cf-ipcountry", "LOCAL").strip().upper() or "LOCAL",
        "ray_id": headers.get("cf-ray", "LOCAL_DIRECT").strip() or "LOCAL_DIRECT",
        "platform_hint": headers.get("sec-ch-ua-platform", "").strip().replace('"', ""),
    }

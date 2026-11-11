"""
Safe URL Fetcher with comprehensive SSRF defences.
Reference: Guideline Extraction Plan Section 7.1, 10.4 (GE-URL), 10.5 (GE-FET).
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Any, Literal
import httpx

MAX_URL_LENGTH = 2048
MAX_BODY_BYTES = 3 * 1024 * 1024  # 3 MB
CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 15.0
MAX_REDIRECTS = 5
USER_AGENT = "PublishAid-Bot/1.0 (+https://publishaid.org/bot)"

# Carrier-grade NAT (100.64.0.0/10) and IPv6 Unique Local (fc00::/7)
CARRIER_GRADE_NAT = ipaddress.ip_network("100.64.0.0/10")
IPV6_UNIQUE_LOCAL = ipaddress.ip_network("fc00::/7")
IPV6_LINK_LOCAL = ipaddress.ip_network("fe80::/10")
CLOUD_METADATA_IP = ipaddress.ip_address("169.254.169.254")

ALLOWED_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "text/plain",
}

BOT_CHALLENGE_PATTERNS = [
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"just a moment\.\.\.", re.IGNORECASE),
    re.compile(r"attention required!\s*\|\s*cloudflare", re.IGNORECASE),
    re.compile(r"checking your browser before accessing", re.IGNORECASE),
    re.compile(r"perimeterx", re.IGNORECASE),
]


class FetchError(Exception):
    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class FetchResult:
    content: str
    content_type: str
    final_url: str
    status_code: int
    redirect_count: int
    warnings: list[dict[str, str]] = field(default_factory=list)


# In-memory per-host politeness rate limiter: last request timestamp per host
_HOST_LAST_REQUEST: dict[str, float] = {}
# In-memory robots.txt cache: host -> (urllib.robotparser.RobotFileParser, timestamp)
_ROBOTS_CACHE: dict[str, tuple[urllib.robotparser.RobotFileParser | None, float]] = {}


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    Checks if an IP address is private, loopback, link-local, multicast,
    reserved, unspecified, carrier-grade NAT, or cloud metadata.
    Handles IPv4-mapped IPv6 addresses.
    """
    # Check for IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return is_ip_blocked(ip.ipv4_mapped)

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or ip == CLOUD_METADATA_IP
    ):
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        if ip in CARRIER_GRADE_NAT:
            return True
    elif isinstance(ip, ipaddress.IPv6Address):
        if ip in IPV6_UNIQUE_LOCAL or ip in IPV6_LINK_LOCAL:
            return True

    return False


def parse_and_validate_numeric_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """
    Detects and validates integer, octal, hex, and shorthand IP representations:
    e.g. 2130706433, 0x7f000001, 0177.0.0.1, 127.1.
    """
    # Hex integer: 0x7f000001
    if re.match(r"^0x[0-9a-fA-F]+$", host):
        try:
            val = int(host, 16)
            if 0 <= val <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(val)
        except ValueError:
            pass

    # Decimal integer: 2130706433
    if re.match(r"^\d+$", host):
        try:
            val = int(host, 10)
            if 0 <= val <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(val)
        except ValueError:
            pass

    # Dotted forms with octal, hex, or fewer than 4 parts (e.g. 0177.0.0.1, 127.1)
    parts = host.split(".")
    if 1 < len(parts) <= 4:
        try:
            # Try converting parts according to inet_aton rules
            nums = []
            for p in parts:
                if p.startswith(("0x", "0X")):
                    nums.append(int(p, 16))
                elif p.startswith("0") and len(p) > 1 and p.isdigit():
                    nums.append(int(p, 8))
                elif p.isdigit():
                    nums.append(int(p, 10))
                else:
                    return None
            
            if len(nums) == 4 and all(0 <= n <= 255 for n in nums):
                return ipaddress.IPv4Address(".".join(str(n) for n in nums))
            elif len(nums) == 2 and 0 <= nums[0] <= 255 and 0 <= nums[1] <= 0xFFFFFF:
                return ipaddress.IPv4Address((nums[0] << 24) | nums[1])
            elif len(nums) == 3 and 0 <= nums[0] <= 255 and 0 <= nums[1] <= 255 and 0 <= nums[2] <= 0xFFFF:
                return ipaddress.IPv4Address((nums[0] << 24) | (nums[1] << 16) | nums[2])
        except (ValueError, OverflowError):
            pass

    # Standard IP check
    try:
        clean_host = host.strip("[]")
        return ipaddress.ip_address(clean_host)
    except ValueError:
        return None


def clear_caches() -> None:
    """Clears in-memory politeness and robots.txt caches."""
    _HOST_LAST_REQUEST.clear()
    _ROBOTS_CACHE.clear()


def normalize_and_validate_url(raw_url: str) -> tuple[str, str, int]:
    """
    Validates and normalizes URL according to SSRF rules:
    - Scheme prepended if missing (https)
    - Rejects credentials (user:pass@host)
    - Allowed schemes: http, https only
    - Allowed ports: 80, 443 only
    - Normalizes scheme and host to lowercase, strips trailing dot and fragment
    - Returns (normalized_url, hostname, port)
    """
    if not isinstance(raw_url, str):
        raise FetchError("INVALID_URL", "URL must be a string")
    
    url = raw_url.strip()
    if not url:
        raise FetchError("INVALID_URL", "URL cannot be empty")
    
    if len(url) > MAX_URL_LENGTH:
        raise FetchError("INVALID_URL", f"URL exceeds maximum length of {MAX_URL_LENGTH} characters")

    # Check for explicit scheme
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception as e:
        raise FetchError("INVALID_URL", f"Malformed URL: {e}")

    if parsed.scheme:
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise FetchError("INVALID_URL", f"Unsupported scheme '{scheme}'. Only http and https are allowed.")
    else:
        # Check if URL starts with something like javascript:alert(1) or ftp:something
        first_colon = url.find(":")
        first_slash = url.find("/")
        if first_colon != -1 and (first_slash == -1 or first_colon < first_slash):
            raise FetchError("INVALID_URL", "Unsupported or invalid URL scheme")
        url = "https://" + url
        try:
            parsed = urllib.parse.urlsplit(url)
            scheme = "https"
        except Exception as e:
            raise FetchError("INVALID_URL", f"Malformed URL: {e}")

    if parsed.username or parsed.password:
        raise FetchError("INVALID_URL", "URLs containing credentials are not allowed")

    netloc = parsed.netloc
    if not netloc:
        raise FetchError("INVALID_URL", "Missing hostname")

    # Handle deceptive URLs like https://good.com@evil.com/
    # urlsplit handles this in netloc/hostname, but let's be strict
    host = parsed.hostname
    if not host:
        raise FetchError("INVALID_URL", "Could not parse hostname")

    # Strip trailing dot from host
    host = host.rstrip(".").lower()

    # IDN to punycode
    try:
        host = host.encode("idna").decode("ascii")
    except Exception:
        raise FetchError("INVALID_URL", "Invalid international domain name")

    # Determine port
    port = parsed.port
    if port is None:
        port = 80 if scheme == "http" else 443
    elif port not in (80, 443):
        raise FetchError("INVALID_URL", f"Port {port} is not permitted. Only ports 80 and 443 are allowed.")

    # Check for localhost literal
    if host in ("localhost", "localhost.localdomain"):
        raise FetchError("BLOCKED_HOST", f"Access to {host} is blocked")

    # Reconstruct normalized URL (without fragment)
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    port_part = f":{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else ""
    normalized_url = f"{scheme}://{host}{port_part}{path}{query}"

    return normalized_url, host, port


def resolve_and_verify_host(host: str, port: int) -> list[str]:
    """
    Resolves DNS for host (IPv4 and IPv6) and verifies that NO resolved IP
    is in the blocked / private IP range.
    Returns list of verified public IP addresses.
    """
    # 1. Check if host itself is a numeric/direct IP
    numeric_ip = parse_and_validate_numeric_ip(host)
    if numeric_ip is not None:
        if is_ip_blocked(numeric_ip):
            raise FetchError("BLOCKED_HOST", f"Direct access to private or reserved IP {numeric_ip} is blocked")
        return [str(numeric_ip)]

    # 2. Resolve DNS via getaddrinfo
    try:
        addr_info = socket.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchError("UNREACHABLE", f"Could not resolve host '{host}': {e}")
    except Exception as e:
        raise FetchError("UNREACHABLE", f"DNS lookup failed for '{host}': {e}")

    if not addr_info:
        raise FetchError("UNREACHABLE", f"No address records found for host '{host}'")

    verified_ips: list[str] = []
    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise FetchError("BLOCKED_HOST", f"Invalid resolved IP '{ip_str}'")

        if is_ip_blocked(ip_obj):
            raise FetchError("BLOCKED_HOST", f"Resolved address {ip_str} for host '{host}' is in a private or restricted network")

        if ip_str not in verified_ips:
            verified_ips.append(ip_str)

    if not verified_ips:
        raise FetchError("UNREACHABLE", f"No valid public IP resolved for '{host}'")

    return verified_ips


async def enforce_politeness(host: str) -> None:
    """Enforces per-host rate limit of at most 1 request per second."""
    now = time.time()
    last = _HOST_LAST_REQUEST.get(host, 0.0)
    delay = 1.0 - (now - last)
    if delay > 0:
        await asyncio.sleep(delay)
    _HOST_LAST_REQUEST[host] = time.time()


async def check_robots_txt(client: httpx.AsyncClient, scheme: str, host: str, port: int, path: str) -> bool:
    """
    Fetches and evaluates robots.txt for host.
    Returns True if allowed, False if disallowed.
    """
    now = time.time()
    cached = _ROBOTS_CACHE.get(host)
    if cached and (now - cached[1] < 600):  # 10 minutes cache
        rp = cached[0]
        if rp is None:
            return False  # Previously failed/disallowed
        return rp.can_fetch(USER_AGENT, path)

    port_part = f":{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else ""
    robots_url = f"{scheme}://{host}{port_part}/robots.txt"
    try:
        # Validate robots URL itself through SSRF check
        resolve_and_verify_host(host, port)
        resp = await client.get(robots_url, timeout=5.0)
        if resp.status_code in (404, 410):
            # Allowed
            rp = urllib.robotparser.RobotFileParser()
            rp.parse([])
            _ROBOTS_CACHE[host] = (rp, now)
            return True
        elif resp.status_code >= 400:
            # Conservative: 5xx or server error treated as disallowed
            _ROBOTS_CACHE[host] = (None, now)
            return False
        else:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(resp.text.splitlines())
            _ROBOTS_CACHE[host] = (rp, now)
            return rp.can_fetch(USER_AGENT, path)
    except Exception:
        # Timeout or unreachable robots.txt treated conservatively as disallowed
        _ROBOTS_CACHE[host] = (None, now)
        return False


def detect_bot_challenge(content: str) -> bool:
    """Detects bot challenge or Cloudflare interstitial pages."""
    if len(content) < 5000:
        for pat in BOT_CHALLENGE_PATTERNS:
            if pat.search(content):
                return True
    return False


async def safe_fetch_url(
    url: str,
    check_robots: bool = True,
    politeness_delay: bool = True,
) -> FetchResult:
    """
    Safely fetches a web page with full SSRF defences, redirect controls,
    politeness rate limiting, and size boundaries.
    """
    warnings: list[dict[str, str]] = []
    current_url = url
    initial_normalized_url, _, _ = normalize_and_validate_url(url)
    redirect_count = 0
    seen_urls = set()

    start_time = time.time()

    async with httpx.AsyncClient(
        verify=True,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9"},
        timeout=httpx.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
    ) as client:
        while True:
            # Total timeout enforcement across all hops
            if time.time() - start_time > TOTAL_TIMEOUT_SECONDS:
                raise FetchError("TIMEOUT", "Total request time exceeded 15 seconds")

            norm_url, host, port = normalize_and_validate_url(current_url)
            
            if norm_url in seen_urls:
                raise FetchError("UNREACHABLE", "Redirect loop detected")
            seen_urls.add(norm_url)

            # SSRF check on every hop
            verified_ips = resolve_and_verify_host(host, port)

            # Check robots.txt on initial hop
            if check_robots and redirect_count == 0:
                parsed_init = urllib.parse.urlsplit(norm_url)
                path_init = parsed_init.path or "/"
                allowed = await check_robots_txt(client, parsed_init.scheme, host, port, path_init)
                if not allowed:
                    raise FetchError("ROBOTS_DISALLOWED", f"Access to {norm_url} is disallowed by publisher's robots.txt")

            # Politeness rate limiter
            if politeness_delay:
                await enforce_politeness(host)

            # Perform request with streaming to enforce 3MB limit
            try:
                # Custom request targeting verified host
                req = client.build_request("GET", norm_url)
                response = await client.send(req, stream=True)
            except httpx.ConnectTimeout:
                raise FetchError("TIMEOUT", "Connection timed out")
            except httpx.TimeoutException:
                raise FetchError("TIMEOUT", "Request timed out")
            except httpx.ConnectError as e:
                raise FetchError("UNREACHABLE", f"Connection failed: {e}")
            except Exception as e:
                raise FetchError("UNREACHABLE", f"HTTP fetch error: {e}")

            # Check redirects (3xx)
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    await response.aclose()
                    raise FetchError("UNREACHABLE", f"Exceeded maximum redirect limit of {MAX_REDIRECTS} hops")

                location = response.headers.get("Location")
                await response.aclose()
                if not location:
                    raise FetchError("UNREACHABLE", "Redirect response missing Location header")

                # Resolve relative redirects
                next_url = urllib.parse.urljoin(norm_url, location)
                
                # Check for scheme change or host change
                orig_parsed = urllib.parse.urlsplit(norm_url)
                next_parsed = urllib.parse.urlsplit(next_url)
                if orig_parsed.netloc != next_parsed.netloc or orig_parsed.path != next_parsed.path:
                    warnings.append({
                        "code": "URL_REDIRECTED",
                        "message": f"Redirected to {next_url}",
                        "path": "source_url"
                    })

                current_url = next_url
                continue

            # Non-redirect response
            if response.status_code != 200:
                code_val = response.status_code
                await response.aclose()
                raise FetchError("HTTP_ERROR", f"HTTP error {code_val}", status_code=code_val)

            # Check Content-Type
            content_type_header = response.headers.get("Content-Type", "").lower()
            main_type = content_type_header.split(";")[0].strip()

            if "application/pdf" in main_type:
                await response.aclose()
                raise FetchError("PDF_NOT_SUPPORTED", "PDF documents are not supported. Please paste the guidelines text directly.")

            if main_type and not any(ct in main_type for ct in ALLOWED_CONTENT_TYPES):
                await response.aclose()
                raise FetchError("NOT_HTML", f"Unsupported content type '{main_type}'. Only HTML or plain text is accepted.")

            # Stream body up to 3MB decompressed
            body_chunks = []
            total_bytes = 0
            try:
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > MAX_BODY_BYTES:
                        await response.aclose()
                        raise FetchError("TOO_LARGE", f"Page body exceeded maximum size limit of 3MB")
                    body_chunks.append(chunk)
                    if time.time() - start_time > TOTAL_TIMEOUT_SECONDS:
                        await response.aclose()
                        raise FetchError("TIMEOUT", "Total request time exceeded 15 seconds")
            finally:
                await response.aclose()

            raw_bytes = b"".join(body_chunks)

            # Handle charset decoding
            encoding = response.encoding or "utf-8"
            try:
                decoded_text = raw_bytes.decode(encoding, errors="replace")
            except Exception:
                decoded_text = raw_bytes.decode("utf-8", errors="replace")

            # Missing Content-Type sniffing
            if not main_type:
                snippet = decoded_text[:500].lower()
                if "<html" in snippet or "<!doctype html" in snippet:
                    main_type = "text/html"
                else:
                    raise FetchError("NOT_HTML", "Response missing Content-Type and does not appear to be HTML")

            # Check bot-challenge
            if detect_bot_challenge(decoded_text):
                warnings.append({
                    "code": "BOT_CHALLENGE_DETECTED",
                    "message": "The publisher presented an automated bot challenge. Pasting the guidelines text is recommended.",
                })

            return FetchResult(
                content=decoded_text,
                content_type=main_type,
                final_url=norm_url,
                status_code=response.status_code,
                redirect_count=redirect_count,
                warnings=warnings,
            )

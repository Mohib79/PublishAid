"""
Tests for Safe Fetcher (GE-URL, GE-FET), Cleaner (GE-HTM, GE-LNG), and Chunker (GE-CHK).
Reference: Guideline Extraction Plan Sections 10.4, 10.5, 10.6, 10.7, 10.8.
All network calls and DNS lookups are strictly mocked.
"""

import socket
import pytest
import respx
import httpx
from unittest.mock import patch

from app.services.guidelines.fetcher import (
    normalize_and_validate_url,
    resolve_and_verify_host,
    safe_fetch_url,
    is_ip_blocked,
    parse_and_validate_numeric_ip,
    clear_caches,
    FetchError,
)

@pytest.fixture(autouse=True)
def reset_caches():
    clear_caches()
    yield
    clear_caches()
from app.services.guidelines.cleaner import (
    clean_guideline_content,
    detect_guideline_language,
    count_words,
    CleanError,
)
from app.services.guidelines.chunker import (
    build_text_chunks,
    split_into_sections,
    score_text_relevance,
)


# ===========================================================================
# 10.4 URL Validation and SSRF (GE-URL)
# ===========================================================================

def test_ge_url_01_https_valid():
    """GE-URL-01: https://example.org/authors is valid."""
    url, host, port = normalize_and_validate_url("https://example.org/authors")
    assert url == "https://example.org/authors"
    assert host == "example.org"
    assert port == 443


def test_ge_url_02_http_valid():
    """GE-URL-02: http://example.org/authors is valid."""
    url, host, port = normalize_and_validate_url("http://example.org/authors")
    assert url == "http://example.org/authors"
    assert host == "example.org"
    assert port == 80


def test_ge_url_03_scheme_prepended():
    """GE-URL-03: example.org/authors (no scheme) treated as https."""
    url, host, port = normalize_and_validate_url("example.org/authors")
    assert url == "https://example.org/authors"
    assert port == 443


def test_ge_url_04_invalid_schemes():
    """GE-URL-04: ftp://, file://, javascript:, data:, gopher://, ssh:// -> INVALID_URL."""
    bad_schemes = [
        "ftp://example.org",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,<h1>bad</h1>",
        "gopher://example.org",
        "ssh://example.org",
    ]
    for bad in bad_schemes:
        with pytest.raises(FetchError) as exc:
            normalize_and_validate_url(bad)
        assert exc.value.code == "INVALID_URL"


def test_ge_url_05_credentials_rejected():
    """GE-URL-05: URL with credentials https://user:pass@example.org -> INVALID_URL."""
    with pytest.raises(FetchError) as exc:
        normalize_and_validate_url("https://user:pass@example.org")
    assert exc.value.code == "INVALID_URL"


def test_ge_url_06_deceptive_url():
    """GE-URL-06: Deceptive https://good.com@evil.com/ -> host is evil.com."""
    with pytest.raises(FetchError) as exc:
        normalize_and_validate_url("https://good.com@evil.com/")
    assert exc.value.code == "INVALID_URL"  # contains credentials (good.com treated as user)


def test_ge_url_07_url_length_exceeded():
    """GE-URL-07: URL longer than 2,048 characters -> INVALID_URL."""
    long_url = "https://example.org/" + ("a" * 2050)
    with pytest.raises(FetchError) as exc:
        normalize_and_validate_url(long_url)
    assert exc.value.code == "INVALID_URL"


def test_ge_url_08_empty_or_whitespace():
    """GE-URL-08: Empty, whitespace-only, non-string -> INVALID_URL."""
    for empty in ["", "   ", "\t\n"]:
        with pytest.raises(FetchError) as exc:
            normalize_and_validate_url(empty)
        assert exc.value.code == "INVALID_URL"


def test_ge_url_09_leading_trailing_spaces_trimmed():
    """GE-URL-09: Leading and trailing spaces trimmed."""
    url, host, port = normalize_and_validate_url("   https://example.org/authors   ")
    assert url == "https://example.org/authors"


def test_ge_url_10_non_standard_ports_rejected():
    """GE-URL-10: Port 8080, 22, 6379, 3306, 5432 -> INVALID_URL."""
    for port in [8080, 22, 6379, 3306, 5432]:
        with pytest.raises(FetchError) as exc:
            normalize_and_validate_url(f"https://example.org:{port}/")
        assert exc.value.code == "INVALID_URL"


def test_ge_url_11_ports_80_and_443_explicit_allowed():
    """GE-URL-11: Ports 80 and 443 explicit are valid."""
    url80, _, p80 = normalize_and_validate_url("http://example.org:80/page")
    assert p80 == 80
    url443, _, p443 = normalize_and_validate_url("https://example.org:443/page")
    assert p443 == 443


def test_ge_url_12_localhost_and_loopback_blocked():
    """GE-URL-12: Host localhost, 127.0.0.1, 0.0.0.0, [::1] -> BLOCKED_HOST."""
    for host in ["localhost", "127.0.0.1", "0.0.0.0", "[::1]"]:
        with pytest.raises(FetchError) as exc:
            url, h, p = normalize_and_validate_url(f"http://{host}/")
            resolve_and_verify_host(h, p)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_13_private_subnets_blocked():
    """GE-URL-13: 10.0.0.5, 172.16.0.1, 172.31.255.255, 192.168.1.1 -> BLOCKED_HOST."""
    for ip in ["10.0.0.5", "172.16.0.1", "172.31.255.255", "192.168.1.1"]:
        with pytest.raises(FetchError) as exc:
            url, h, p = normalize_and_validate_url(f"http://{ip}/")
            resolve_and_verify_host(h, p)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_14_cloud_metadata_link_local_blocked():
    """GE-URL-14: 169.254.169.254 (cloud metadata) and other link-local -> BLOCKED_HOST."""
    for ip in ["169.254.169.254", "169.254.1.1"]:
        with pytest.raises(FetchError) as exc:
            url, h, p = normalize_and_validate_url(f"http://{ip}/")
            resolve_and_verify_host(h, p)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_15_carrier_grade_nat_blocked():
    """GE-URL-15: 100.64.0.1 (carrier-grade NAT) -> BLOCKED_HOST."""
    with pytest.raises(FetchError) as exc:
        url, h, p = normalize_and_validate_url("http://100.64.0.1/")
        resolve_and_verify_host(h, p)
    assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_16_ipv6_unique_local_link_local_blocked():
    """GE-URL-16: IPv6 unique-local fc00::1, link-local fe80::1 -> BLOCKED_HOST."""
    for ip in ["[fc00::1]", "[fe80::1]"]:
        with pytest.raises(FetchError) as exc:
            url, h, p = normalize_and_validate_url(f"http://{ip}/")
            resolve_and_verify_host(h, p)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_17_ipv4_mapped_ipv6_blocked():
    """GE-URL-17: IPv4-mapped IPv6 ::ffff:127.0.0.1 -> BLOCKED_HOST."""
    with pytest.raises(FetchError) as exc:
        url, h, p = normalize_and_validate_url("http://[::ffff:127.0.0.1]/")
        resolve_and_verify_host(h, p)
    assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_18_numeric_ip_forms_blocked():
    """GE-URL-18: Numeric forms: 2130706433, 0x7f000001, 0177.0.0.1, 127.1 -> BLOCKED_HOST."""
    numeric_tricks = ["2130706433", "0x7f000001", "0177.0.0.1", "127.1"]
    for trick in numeric_tricks:
        with pytest.raises(FetchError) as exc:
            url, h, p = normalize_and_validate_url(f"http://{trick}/")
            resolve_and_verify_host(h, p)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_19_public_hostname_resolving_to_private():
    """GE-URL-19: Public hostname whose DNS returns a private IP -> BLOCKED_HOST."""
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.50", 443))]
        with pytest.raises(FetchError) as exc:
            resolve_and_verify_host("malicious-journal.com", 443)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_20_dns_mix_public_and_private():
    """GE-URL-20: DNS returns a mix of public and private IPs -> BLOCKED_HOST."""
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]
        with pytest.raises(FetchError) as exc:
            resolve_and_verify_host("mixed-dns.com", 443)
        assert exc.value.code == "BLOCKED_HOST"


def test_ge_url_27_normalization_details():
    """GE-URL-27: Uppercase scheme/host, trailing dot in host, fragment removed."""
    url, host, port = normalize_and_validate_url("HTTPS://EXAMPLE.ORG.:443/guide#references")
    assert url == "https://example.org/guide"
    assert host == "example.org"


def test_ge_url_28_punycode_handling():
    """GE-URL-28: Internationalized domain names encoded to punycode."""
    url, host, port = normalize_and_validate_url("https://münchen.de/guide")
    assert host == "xn--mnchen-3ya.de"


def test_ge_url_29_hostname_not_resolving():
    """GE-URL-29: Hostname that does not resolve -> UNREACHABLE."""
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
        with pytest.raises(FetchError) as exc:
            resolve_and_verify_host("nonexistent-domain-xyz123.org", 443)
        assert exc.value.code == "UNREACHABLE"


# ===========================================================================
# 10.5 Fetching (GE-FET)
# ===========================================================================

@pytest.mark.anyio
@respx.mock
async def test_ge_fet_01_html_guidelines_page_success():
    """GE-FET-01: 200 HTML guidelines page fetched successfully."""
    target_url = "https://example.org/authors"
    respx.get("https://example.org/robots.txt").respond(404)
    respx.get(target_url).respond(
        200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        text="<html><body><h1>Guidelines</h1><p>Word limit is 5000 words.</p></body></html>",
    )

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        res = await safe_fetch_url(target_url, politeness_delay=False)
        assert res.status_code == 200
        assert "Word limit is 5000" in res.content
        assert res.content_type == "text/html"


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_02_http_errors():
    """GE-FET-02: 401, 403, 404, 500, 503 -> HTTP_ERROR with status."""
    respx.get("https://example.org/robots.txt").respond(404)
    for code in [401, 403, 404, 500, 503]:
        target = f"https://example.org/error_{code}"
        respx.get(target).respond(code)
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
            with pytest.raises(FetchError) as exc:
                await safe_fetch_url(target, politeness_delay=False)
            assert exc.value.code == "HTTP_ERROR"
            assert exc.value.status_code == code


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_05_body_larger_than_3mb():
    """GE-FET-05: Body larger than 3MB aborted with TOO_LARGE."""
    target_url = "https://example.org/huge"
    respx.get("https://example.org/robots.txt").respond(404)
    respx.get(target_url).respond(
        200,
        headers={"Content-Type": "text/html"},
        content=b"A" * (4 * 1024 * 1024),
    )

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with pytest.raises(FetchError) as exc:
            await safe_fetch_url(target_url, politeness_delay=False)
        assert exc.value.code == "TOO_LARGE"


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_08_pdf_not_supported():
    """GE-FET-08: application/pdf -> PDF_NOT_SUPPORTED."""
    target_url = "https://example.org/guidelines.pdf"
    respx.get("https://example.org/robots.txt").respond(404)
    respx.get(target_url).respond(
        200,
        headers={"Content-Type": "application/pdf"},
        content=b"%PDF-1.4 ...",
    )

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with pytest.raises(FetchError) as exc:
            await safe_fetch_url(target_url, politeness_delay=False)
        assert exc.value.code == "PDF_NOT_SUPPORTED"


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_09_unsupported_content_types():
    """GE-FET-09: image/png, application/zip -> NOT_HTML."""
    target_url = "https://example.org/archive.zip"
    respx.get("https://example.org/robots.txt").respond(404)
    respx.get(target_url).respond(
        200,
        headers={"Content-Type": "application/zip"},
        content=b"PK...",
    )

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with pytest.raises(FetchError) as exc:
            await safe_fetch_url(target_url, politeness_delay=False)
        assert exc.value.code == "NOT_HTML"


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_13_robots_disallowed():
    """GE-FET-13: robots.txt disallows the path -> ROBOTS_DISALLOWED."""
    target_url = "https://example.org/private/authors"
    robots_content = "User-agent: *\nDisallow: /private/\n"
    respx.get("https://example.org/robots.txt").respond(200, text=robots_content)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with pytest.raises(FetchError) as exc:
            await safe_fetch_url(target_url, politeness_delay=False)
        assert exc.value.code == "ROBOTS_DISALLOWED"


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_21_bot_challenge_detection():
    """GE-FET-21: Bot challenge detected -> warning BOT_CHALLENGE_DETECTED."""
    target_url = "https://example.org/authors"
    respx.get("https://example.org/robots.txt").respond(404)
    respx.get(target_url).respond(
        200,
        headers={"Content-Type": "text/html"},
        text="<html><body><h1>Please verify you are human</h1><p>Checking browser...</p></body></html>",
    )

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        res = await safe_fetch_url(target_url, politeness_delay=False)
        assert any(w["code"] == "BOT_CHALLENGE_DETECTED" for w in res.warnings)


@pytest.mark.anyio
@respx.mock
async def test_ge_fet_redirect_hop_limit():
    """GE-URL-24: Redirect chain of 6 hops fails with UNREACHABLE."""
    respx.get("https://example.org/robots.txt").respond(404)
    for i in range(6):
        respx.get(f"https://example.org/hop{i}").respond(302, headers={"Location": f"https://example.org/hop{i+1}"})

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with pytest.raises(FetchError) as exc:
            await safe_fetch_url("https://example.org/hop0", politeness_delay=False)
        assert exc.value.code == "UNREACHABLE"
        assert "redirect limit" in exc.value.message.lower()


# ===========================================================================
# 10.6 HTML Extraction and Text Cleaning (GE-HTM)
# ===========================================================================

def test_ge_htm_01_strip_boilerplate_keep_guidelines():
    """GE-HTM-01: Page with nav, footer, cookie banner -> only guideline content kept."""
    html = """
    <html>
      <head><title>Journal Author Guidelines</title></head>
      <body>
        <nav><a href="/">Home</a><a href="/login">Login</a></nav>
        <div class="cookie-banner">We use cookies.</div>
        <main>
          <h1>Submission Guidelines</h1>
          <p>The maximum manuscript length is 6000 words. All submissions must include an abstract under 250 words.</p>
          <p>Please format all references using IEEE style with numbered citations.</p>
          <p>Figures must be submitted at 300 DPI resolution in TIFF or PNG format.</p>
        </main>
        <footer>Copyright 2026 Publisher</footer>
      </body>
    </html>
    """
    cleaned, title, warnings = clean_guideline_content(html, is_html=True)
    assert title == "Journal Author Guidelines"
    assert "Submission Guidelines" in cleaned
    assert "6000 words" in cleaned
    assert "cookie" not in cleaned.lower()
    assert "login" not in cleaned.lower()


def test_ge_htm_03_tables_converted_to_readable_rows():
    """GE-HTM-03: Tables converted to readable markdown rows."""
    html = """
    <html>
      <head><title>Limits</title></head>
      <body>
        <h1>Article Limits</h1>
        <table>
          <tr><th>Article Type</th><th>Word Limit</th><th>Max Figures</th></tr>
          <tr><td>Research Article</td><td>8000</td><td>8</td></tr>
          <tr><td>Short Communication</td><td>3000</td><td>3</td></tr>
        </table>
      </body>
    </html>
    """
    cleaned, _, _ = clean_guideline_content(html, is_html=True)
    assert "Research Article" in cleaned
    assert "8000" in cleaned
    assert "Short Communication" in cleaned


def test_ge_htm_08_pasted_html_stripped():
    """GE-HTM-08: User pastes HTML source -> stripped to clean text."""
    pasted = (
        "<div><h3>Format</h3><p>Manuscript must be <b>double-spaced</b> with 12pt font. "
        "All submissions must include structured abstracts not exceeding 250 words. "
        "Ensure all tables and figures are uploaded separately in high resolution format.</p></div>"
    )
    cleaned, _, _ = clean_guideline_content(pasted, is_html=False)
    assert "double-spaced" in cleaned
    assert "<b>" not in cleaned


def test_ge_htm_10_odd_spaces_and_nfc_normalization():
    """GE-HTM-10: Non-breaking spaces and odd whitespace normalized."""
    raw = (
        "Length\u00a0is\u200b 5000\u00a0words.\n\n\n\nNext paragraph specifies formatting requirements. "
        "Please provide six keywords for cataloging purposes. References must follow Vancouver style. "
        "Ensure ethics declarations and conflict of interest statements are included with every submission."
    )
    cleaned, _, _ = clean_guideline_content(raw, is_html=False)
    assert "Length is 5000 words." in cleaned
    assert "\u00a0" not in cleaned
    assert "\u200b" not in cleaned


def test_ge_htm_16_empty_content_rejected():
    """GE-HTM-16: Fewer than 30 words found -> EMPTY_CONTENT."""
    with pytest.raises(CleanError) as exc:
        clean_guideline_content("<p>Only ten words are present in this very brief text snippet.</p>", is_html=True)
    assert exc.value.code == "EMPTY_CONTENT"


def test_ge_htm_17_insufficient_content_warning():
    """GE-HTM-17: 30 to 149 words found -> INSUFFICIENT_GUIDELINE_CONTENT."""
    text = "word " * 50
    cleaned, _, warnings = clean_guideline_content(text, is_html=False)
    assert any(w["code"] == "INSUFFICIENT_GUIDELINE_CONTENT" for w in warnings)


# ===========================================================================
# 10.7 Language Detection (GE-LNG)
# ===========================================================================

def test_ge_lng_01_english_guidelines():
    """GE-LNG-01: English guidelines -> no warning."""
    text = (
        "Manuscripts submitted to this journal must adhere strictly to formatting guidelines. "
        "The abstract must not exceed two hundred and fifty words. Include five keywords. "
        "All citations must be formatted using the Vancouver citation system. "
    ) * 3
    lang, warnings = detect_guideline_language(text)
    assert lang == "en"
    assert len(warnings) == 0


def test_ge_lng_02_foreign_guidelines():
    """GE-LNG-02: Non-English guidelines -> NOT_ENGLISH warning."""
    spanish_text = (
        "Las pautas de autor especifican que los manuscritos no deben exceder cinco mil palabras. "
        "El resumen debe tener un máximo de doscientas cincuenta palabras y estar estructurado. "
        "Las referencias deben seguir el formato APA versión siete con lista completa. "
    ) * 3
    lang, warnings = detect_guideline_language(spanish_text)
    assert lang != "en"
    assert any(w["code"] == "NOT_ENGLISH" for w in warnings)


def test_ge_lng_04_skip_detection_under_50_words():
    """GE-LNG-04: Under 50 words -> detection skipped, no warning."""
    short_text = "Ceci est un texte court en français avec peu de mots."
    lang, warnings = detect_guideline_language(short_text)
    assert lang == "en"
    assert len(warnings) == 0


# ===========================================================================
# 10.8 Relevance Filtering and Chunking (GE-CHK)
# ===========================================================================

def test_ge_chk_01_short_document_single_chunk():
    """GE-CHK-01: Short document (<= 24,000 chars) -> one chunk, no filtering."""
    doc = "# Guidelines\n\nManuscript limit is 5,000 words. References in IEEE style."
    chunks, warnings = build_text_chunks(doc)
    assert len(chunks) == 1
    assert chunks[0].heading_path == ""
    assert chunks[0].total_chunks == 1
    assert len(warnings) == 0


def test_ge_chk_02_long_document_with_headings():
    """GE-CHK-02: Long document with headings -> multiple chunks prefixed with heading path."""
    section1 = "# Manuscript Preparation\n\n" + ("Word count details and limits for research articles. " * 300)
    section2 = "# References and Citations\n\n" + ("Detailed citations instructions for IEEE format. " * 300)
    long_doc = section1 + "\n\n" + section2
    assert len(long_doc) > 24000

    chunks, warnings = build_text_chunks(long_doc)
    assert len(chunks) > 1
    assert any("Manuscript Preparation" in c.heading_path for c in chunks)
    assert any("References and Citations" in c.heading_path for c in chunks)


def test_ge_chk_04_relevance_scoring_priority():
    """GE-CHK-04: Relevant sections prioritized over irrelevant history sections."""
    relevant_score = score_text_relevance("Word limit is 5000 words. Format citations in IEEE style.", "Submission Guidelines")
    history_score = score_text_relevance("The journal was founded in 1892 in London by prominent scholars.", "Journal History")
    assert relevant_score > history_score


def test_ge_chk_05_truncation_warning_at_limit():
    """GE-CHK-05: More than 12 chunks -> truncated by priority, TRUNCATED warning."""
    sections = []
    for i in range(20):
        sections.append(f"# Section {i}\n\n" + (f"Detailed requirements for section {i}. " * 150))
    huge_doc = "\n\n".join(sections)

    chunks, warnings = build_text_chunks(huge_doc)
    assert len(chunks) == 12
    assert any(w["code"] == "TRUNCATED" for w in warnings)


def test_ge_chk_08_deterministic_chunks():
    """GE-CHK-08: Same input produces identical chunks (deterministic)."""
    doc = "# Guide\n\n" + ("Requirements content repeated. " * 1000)
    chunks1, _ = build_text_chunks(doc)
    chunks2, _ = build_text_chunks(doc)
    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.text == c2.text
        assert c1.heading_path == c2.heading_path

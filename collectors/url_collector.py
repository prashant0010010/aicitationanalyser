"""Fetch web pages safely and turn HTML into a structured Document."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment

from config.settings import Settings, get_settings
from models.schemas import Document, utcnow
from utils.cache import TTLCache
from utils.security import validate_url
from utils.text import normalize_ws, sanitize_input, word_count
from utils.urls import hostname, normalize_url

log = logging.getLogger("citation_analyser.collector")

_FETCH_CACHE = TTLCache(ttl_seconds=3600, max_items=128)
_BOILERPLATE_RE = re.compile(
    r"(?:^|[\s_-])(nav|navbar|menu|footer|sidebar|breadcrumbs?|cookie|cookies|consent|banner|advert|ads?|"
    r"promo|popup|modal|newsletter|social|share|sharing|comments?)(?:$|[\s_-])", re.I)
_ALLOWED_TYPES = ("text/html", "application/xhtml", "text/plain", "application/xml", "text/xml")


@dataclass
class FetchResult:
    ok: bool
    url: str
    final_url: str = ""
    html: str = ""
    error: str = ""
    status: int = 0
    content_type: str = ""


def _parser() -> str:
    try:
        import lxml  # noqa: F401

        return "lxml"
    except Exception:  # pragma: no cover
        return "html.parser"


# ------------------------------------------------------------------ fetching
def fetch_url(url: str, settings: Optional[Settings] = None, use_cache: bool = True) -> FetchResult:
    """Fetch one URL with SSRF checks on every redirect hop, size and time limits."""
    s = settings or get_settings()
    url = normalize_url(url)
    if use_cache:
        cached = _FETCH_CACHE.get(url)
        if cached is not None:
            return cached
    result = _fetch_uncached(url, s)
    if result.ok and use_cache:
        _FETCH_CACHE.ttl = s.cache_ttl_seconds
        _FETCH_CACHE.set(url, result)
    return result


def _fetch_uncached(url: str, s: Settings) -> FetchResult:
    current = url
    headers = {
        "User-Agent": s.user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5,*/*;q=0.1",
        "Accept-Language": "en",
    }
    try:
        for _ in range(s.max_redirects + 1):
            ok, reason = validate_url(current, s.allow_private_urls)
            if not ok:
                return FetchResult(False, url, error=f"URL rejected: {reason}")
            resp = requests.get(current, headers=headers, timeout=s.request_timeout, stream=True, allow_redirects=False)
            if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                current = urljoin(current, resp.headers["Location"])
                resp.close()
                continue
            if resp.status_code in (401, 403, 429):
                resp.close()
                return FetchResult(False, url, status=resp.status_code,
                                   error=f"The site blocked automated access (HTTP {resp.status_code}). Paste the page content instead.")
            if resp.status_code >= 400:
                resp.close()
                return FetchResult(False, url, status=resp.status_code, error=f"The server returned HTTP {resp.status_code}.")
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype and not ctype.startswith(_ALLOWED_TYPES):
                resp.close()
                return FetchResult(False, url, status=resp.status_code, content_type=ctype,
                                   error=f"Unsupported content type: {ctype}. Only HTML and text pages are supported.")
            data = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                data.extend(chunk)
                if len(data) > s.max_download_bytes:
                    break
            truncated = len(data) > s.max_download_bytes
            resp.close()
            raw = bytes(data[: s.max_download_bytes])
            encoding = resp.encoding if resp.encoding and "charset" in (resp.headers.get("Content-Type") or "").lower() else None
            if encoding:
                html = raw.decode(encoding, errors="replace")
            else:
                from bs4 import UnicodeDammit

                html = UnicodeDammit(raw).unicode_markup or raw.decode("utf-8", errors="replace")
            res = FetchResult(True, url, final_url=current, html=html, status=resp.status_code, content_type=ctype)
            if truncated:
                res.error = "Page was larger than the download limit and was truncated."
            return res
        return FetchResult(False, url, error="Too many redirects.")
    except requests.exceptions.Timeout:
        return FetchResult(False, url, error=f"The request timed out after {s.request_timeout} seconds.")
    except requests.exceptions.SSLError:
        return FetchResult(False, url, error="The site's SSL certificate could not be verified.")
    except requests.exceptions.ConnectionError:
        return FetchResult(False, url, error="Could not connect to the site. Check the URL and your network.")
    except requests.exceptions.RequestException as exc:
        return FetchResult(False, url, error=f"Request failed: {type(exc).__name__}.")
    except Exception as exc:  # never crash the app because of one URL
        log.exception("Unexpected fetch failure")
        return FetchResult(False, url, error=f"Unexpected error while fetching: {type(exc).__name__}.")


# ------------------------------------------------------------------ extraction
def _meta_content(soup: BeautifulSoup, **attrs: str) -> str:
    tag = soup.find("meta", attrs=attrs)
    return normalize_ws(tag.get("content", "")) if tag and tag.get("content") else ""


def _parse_jsonld(soup: BeautifulSoup) -> tuple[list[dict], list[str]]:
    nodes: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if "@graph" in node and isinstance(node["@graph"], list):
                    stack.extend(node["@graph"])
                nodes.append(node)
            elif isinstance(node, list):
                stack.extend(node)
    types: list[str] = []
    for n in nodes:
        t = n.get("@type")
        for v in (t if isinstance(t, list) else [t]):
            if isinstance(v, str) and v not in types:
                types.append(v)
    return nodes, types


def _find_date(soup: BeautifulSoup, nodes: list[dict]) -> tuple[str, str]:
    pub = (_meta_content(soup, property="article:published_time") or _meta_content(soup, itemprop="datePublished")
           or _meta_content(soup, name="date"))
    mod = _meta_content(soup, property="article:modified_time") or _meta_content(soup, itemprop="dateModified")
    for n in nodes:
        pub = pub or str(n.get("datePublished", "") or "")
        mod = mod or str(n.get("dateModified", "") or "")
    if not pub:
        t = soup.find("time", attrs={"datetime": True})
        if t:
            pub = t["datetime"]
    return pub[:32], mod[:32]


def _leaf_blocks(root, page_host: str, max_chars: int) -> tuple[list[dict], list[dict], list[dict]]:
    """Walk the content root in document order and return (blocks, links, tables)."""
    blocks: list[dict] = []
    links: list[dict] = []
    tables: list[dict] = []
    seen_lists: set[int] = set()
    total = 0
    last_text = ""
    for a in root.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = href if href.startswith("http") else ""
        host = hostname(absolute) if absolute else ""
        links.append({"href": absolute or href, "text": normalize_ws(a.get_text(" "))[:120],
                      "external": bool(host and host != page_host)})

    def ext_links(el) -> int:
        n = 0
        for a in el.find_all("a", href=True):
            h = a["href"]
            if h.startswith("http") and hostname(h) != page_host:
                n += 1
        return n

    for el in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "blockquote", "dd", "dt"]):
        if total > max_chars:
            break
        name = el.name
        if name in ("p", "blockquote", "dd", "dt") and el.find_parent(["li", "table"]):
            continue
        if name == "p" and el.find_parent("blockquote"):
            continue
        if name == "li":
            if el.find_parent("table") or el.find("li"):
                continue
            parent = el.find_parent(["ul", "ol"])
            if parent is None or id(parent) in seen_lists:
                continue
            seen_lists.add(id(parent))
            items = [normalize_ws(li.get_text(" ")) for li in parent.find_all("li") if not li.find("li")]
            items = [i for i in items if i]
            if not items:
                continue
            text = " ; ".join(items)
            blocks.append({"type": "list", "text": text, "items": items, "ext_links": ext_links(parent)})
            total += len(text)
            continue
        if name == "table":
            if el.find_parent("table"):
                continue
            rows = []
            for tr in el.find_all("tr")[:40]:
                cells = [normalize_ws(c.get_text(" ")) for c in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            if not rows:
                continue
            caption = el.find("caption")
            tables.append({"caption": normalize_ws(caption.get_text(" ")) if caption else "", "rows": rows})
            headers = rows[0] if len(rows) > 1 else []
            row_sents = []
            for r in (rows[1:] if headers else rows):
                pairs = [f"{headers[i]}: {c}" if i < len(headers) and headers[i] else c for i, c in enumerate(r) if c]
                if pairs:
                    row_sents.append("; ".join(pairs) + ".")
            text = " ".join(row_sents)
            blocks.append({"type": "table", "text": text, "ext_links": ext_links(el)})
            total += len(text)
            continue
        text = normalize_ws(el.get_text(" "))
        if not text or text == last_text:
            continue
        if name.startswith("h") and len(name) == 2:
            if len(text) > 300:
                continue
            blocks.append({"type": "heading", "level": int(name[1]), "text": text, "ext_links": 0})
        else:
            if len(text.split()) < 3:
                continue
            blocks.append({"type": "p", "text": text, "ext_links": ext_links(el)})
        last_text = text
        total += len(text)
    return blocks, links, tables


def extract_document(
    html: str, url: str = "", kind: str = "target", origin: str = "url",
    label: str = "", settings: Optional[Settings] = None,
) -> Document:
    """Convert raw HTML into a Document. Never raises for malformed HTML."""
    s = settings or get_settings()
    doc = Document(url=url, label=label or url, kind=kind, origin=origin, has_html=True, fetched_at=utcnow())
    try:
        html = sanitize_input(html, max_len=s.max_download_bytes)
        soup = BeautifulSoup(html, _parser())
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        nodes, types = _parse_jsonld(soup)
        doc.jsonld, doc.schema_types = nodes, types
        doc.title = normalize_ws(soup.title.get_text()) if soup.title else ""
        doc.meta = {
            "description": _meta_content(soup, name="description"),
            "og_title": _meta_content(soup, property="og:title"),
            "og_description": _meta_content(soup, property="og:description"),
            "og_image": _meta_content(soup, property="og:image"),
            "canonical": (soup.find("link", rel="canonical") or {}).get("href", "") if soup.find("link", rel="canonical") else "",
            "lang": (soup.html.get("lang", "") if soup.html else ""),
            "robots": _meta_content(soup, name="robots"),
        }
        doc.published, doc.modified = _find_date(soup, nodes)
        for tag in soup(["script", "style", "noscript", "template", "iframe", "svg", "form", "nav", "footer", "aside", "button", "select"]):
            tag.decompose()
        for header in soup.find_all("header"):
            if not header.find(["h1", "h2"]):
                header.decompose()
        root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
        root_len = len(root.get_text(" ", strip=True)) or 1
        for el in list(root.find_all(True)):
            if el.name in ("html", "body", "main", "article") or el.attrs is None:
                continue
            ident = " ".join(el.get("class", []) if isinstance(el.get("class"), list) else [str(el.get("class") or "")]) + " " + str(el.get("id") or "")
            if _BOILERPLATE_RE.search(ident) and len(el.get_text(" ", strip=True)) < 0.5 * root_len:
                el.decompose()
        host = hostname(url)
        blocks, links, tables = _leaf_blocks(root, host, s.max_content_chars)
        if sum(len(b["text"].split()) for b in blocks) < 100 and root is not soup.body and soup.body:
            blocks, links, tables = _leaf_blocks(soup.body, host, s.max_content_chars)
        if sum(len(b["text"].split()) for b in blocks) < 80:
            blocks = _trafilatura_fallback(html, blocks, doc)
        _fill_document(doc, blocks, links, tables, soup)
    except Exception as exc:
        log.exception("Extraction failed")
        doc.ok = False
        doc.error = f"Content extraction failed: {type(exc).__name__}."
    return doc


def _trafilatura_fallback(html: str, blocks: list[dict], doc: Document) -> list[dict]:
    try:
        import trafilatura

        text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_recall=True)
    except Exception:
        return blocks
    if not text:
        return blocks
    new = [{"type": "p", "text": normalize_ws(p), "ext_links": 0} for p in re.split(r"\n{1,}", text) if len(p.split()) >= 3]
    if sum(len(b["text"].split()) for b in new) > sum(len(b["text"].split()) for b in blocks):
        doc.notes.append("Main content was recovered with the trafilatura fallback extractor.")
        return new
    return blocks


def _terminated(block: dict) -> str:
    """Block text with terminal punctuation so sentence splitting never fuses neighbouring blocks."""
    t = block["text"].rstrip()
    if block["type"] in ("heading", "list", "table", "p") and t and t[-1] not in ".?!:":
        t += "."
    return t


def _fill_document(doc: Document, blocks: list[dict], links: list[dict], tables: list[dict], soup) -> None:
    doc.blocks = blocks
    doc.links = links[:300]
    doc.tables = tables
    for i, b in enumerate(blocks):
        if b["type"] == "heading":
            doc.headings.append({"level": b["level"], "text": b["text"], "block": i})
        elif b["type"] == "p":
            doc.paragraphs.append(b["text"])
            doc.para_links.append(b.get("ext_links", 0))
        elif b["type"] == "list":
            doc.lists.append(b.get("items", []))
    doc.text = "\n".join(_terminated(b) for b in blocks)
    doc.word_count = word_count(doc.text)
    if not doc.title and doc.headings:
        doc.title = doc.headings[0]["text"]
    if doc.word_count < 30:
        doc.ok = False
        doc.error = "Very little readable text was found. The page may need JavaScript to render or may be blocked. Paste the content instead."
    else:
        doc.ok = True


def collect_url(url: str, kind: str = "target", settings: Optional[Settings] = None) -> Document:
    """Fetch and extract a URL. Always returns a Document, with ok=False on failure."""
    s = settings or get_settings()
    url = normalize_url(url)
    res = fetch_url(url, s)
    if not res.ok:
        return Document(url=url, label=url, kind=kind, origin="url", ok=False, error=res.error, fetched_at=utcnow())
    if res.content_type.startswith("text/plain"):
        doc = collect_pasted(res.html, label=url, kind=kind, settings=s)
        doc.url, doc.origin = res.final_url or url, "url"
        return doc
    doc = extract_document(res.html, url=res.final_url or url, kind=kind, origin="url", label=url, settings=s)
    if res.error:
        doc.notes.append(res.error)
    return doc


_HTML_RE = re.compile(r"<\s*(html|body|div|p|h[1-6]|article|section|ul|ol|table|head|meta|title)\b", re.I)


def collect_pasted(text: str, label: str = "Pasted content", kind: str = "target",
                   url: str = "", settings: Optional[Settings] = None) -> Document:
    """Turn pasted HTML, markdown-ish text or plain text into a Document."""
    s = settings or get_settings()
    text = sanitize_input(text, max_len=s.max_content_chars)
    if not text.strip():
        return Document(url=url, label=label, kind=kind, origin="pasted_text", ok=False, error="No content was provided.", fetched_at=utcnow())
    if _HTML_RE.search(text[:5000]):
        return extract_document(text, url=url, kind=kind, origin="pasted_html", label=label, settings=s)
    doc = Document(url=url, label=label, kind=kind, origin="pasted_text", has_html=False, fetched_at=utcnow())
    blocks: list[dict] = []
    for chunk in re.split(r"\n\s*\n", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", chunk)
        if m and "\n" not in chunk:
            blocks.append({"type": "heading", "level": len(m.group(1)), "text": normalize_ws(m.group(2)), "ext_links": 0})
            continue
        lines = [ln.strip() for ln in chunk.split("\n") if ln.strip()]
        if len(lines) >= 2 and all(re.match(r"^([-*\u2022]|\d+[.)])\s+", ln) for ln in lines):
            items = [re.sub(r"^([-*\u2022]|\d+[.)])\s+", "", ln) for ln in lines]
            blocks.append({"type": "list", "text": " ; ".join(items), "items": items, "ext_links": 0})
            continue
        for ln in lines:
            hm = re.match(r"^(#{1,6})\s+(.*)$", ln)
            if hm:
                blocks.append({"type": "heading", "level": len(hm.group(1)), "text": normalize_ws(hm.group(2)), "ext_links": 0})
            else:
                n_links = len(re.findall(r"https?://", ln))
                blocks.append({"type": "p", "text": normalize_ws(ln), "ext_links": n_links})
    doc.title = next((b["text"] for b in blocks if b["type"] == "heading"), label)
    _fill_document(doc, blocks, [], [], None)
    doc.notes.append("Plain text input: HTML-only signals such as schema markup and metadata cannot be assessed.")
    return doc

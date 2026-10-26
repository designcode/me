#!/usr/bin/env python3
"""
Migrate one post from abbyontravel.com (WordPress.com) into this Astro blog.

    python3 scripts/migrate-abbyontravel.py <wordpress-url-or-slug> [options]

Examples:

    python3 scripts/migrate-abbyontravel.py https://abbyontravel.com/2019/10/29/1-day-hike-on-matterhorn-trail/ \
        --slug matterhorn-trail --category Guides

    python3 scripts/migrate-abbyontravel.py 5-days-in-madeira --dry-run

What it does:
  1. Fetches the post through the public WordPress.com REST API (no login needed).
  2. Downloads every image into public/<slug>/1.jpg, 2.jpg, ... (resized by WordPress to
     --max-width pixels on the long side, EXIF stripped).
  3. Converts the WordPress block HTML into MDX using this repo's components:
     PhotoGallery for galleries, EmbedYoutube for YouTube, EmbedGoogleMap for Google Maps.
  4. Writes src/posts/<date>-<slug>.mdx with frontmatter (slug, title, date, category,
     description, originalUrl).
  5. Adds a redirect from the old abbyontravel.com path to /posts/<slug> in astro.config.mjs
     and runs prettier on the touched files.

Options:
  --slug SLUG         URL slug on designcode.me (default: the WordPress slug)
  --category NAME     Category (default: Guides for guide/planning posts, otherwise Thoughts)
  --max-width N       Long-side pixel limit for downloaded images, 0 = original (default 2048)
  --dry-run           Print the MDX instead of writing; download nothing; touch no files
  --out-dir DIR       With --dry-run, write the MDX file into DIR instead of printing
  --force             Overwrite an existing post file / re-download existing images
  --no-redirect       Do not touch astro.config.mjs

Uses only the Python standard library (Python 3.9+).
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

WP_SITE = "abbyontravel.wordpress.com"
WP_API = f"https://public-api.wordpress.com/rest/v1.1/sites/{WP_SITE}/posts/"
OLD_HOST = "abbyontravel.com"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(REPO_ROOT, "src", "posts")
PUBLIC_DIR = os.path.join(REPO_ROOT, "public")
ASTRO_CONFIG = os.path.join(REPO_ROOT, "astro.config.mjs")

VOID_TAGS = {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}
BLOCK_TAGS = {"p", "div", "figure", "ul", "ol", "table", "blockquote", "pre", "hr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}
GALLERY_CLASS_PREFIXES = ("wp-block-gallery", "wp-block-jetpack-tiled-gallery", "tiled-gallery", "coblocks-gallery", "gallery")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


# --------------------------------------------------------------------------- DOM

class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.parent = parent
        self.children = []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def has_class_prefix(self, prefixes):
        return any(c.startswith(p) for c in self.classes for p in prefixes)

    def find_all(self, tag):
        out = []
        for c in self.children:
            if isinstance(c, Node):
                if c.tag == tag:
                    out.append(c)
                out.extend(c.find_all(tag))
        return out

    def find_first(self, tag):
        found = self.find_all(tag)
        return found[0] if found else None

    def text(self):
        parts = []
        for c in self.children:
            parts.append(c if isinstance(c, str) else c.text())
        return "".join(parts)

    def element_children(self):
        return [c for c in self.children if isinstance(c, Node)]


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID_TAGS:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if data:
            self.cur.children.append(data)


def parse_html(text):
    tb = TreeBuilder()
    tb.feed(text)
    tb.close()
    return tb.root


def strip_tags(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or ""))


# --------------------------------------------------------------------------- text helpers

def norm_ws(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " "))


def esc_md(s):
    """Escape characters that MDX/Markdown would otherwise interpret."""
    s = s.replace("\\", "\\\\")
    for ch in "*_`{}[]<":
        s = s.replace(ch, "\\" + ch)
    return s


def esc_block_start(s):
    """Escape list/heading/quote markers at the start of a paragraph."""
    return re.sub(r"^(\s*)([#>+-]|\d+[.)])(?=\s)", lambda m: m.group(1) + "\\" + m.group(2), s)


def js_str(s):
    return json.dumps(s, ensure_ascii=False)


def yaml_str(s):
    return json.dumps(s, ensure_ascii=False)


def html_attr(s):
    return html.escape(s, quote=True)


# --------------------------------------------------------------------------- image helpers

def image_source_url(img):
    """Best original URL of an <img>; strips WordPress/Photon size params."""
    for key in ("data-orig-file", "data-url", "data-large-file", "src"):
        url = img.attrs.get(key)
        if url:
            break
    else:
        return None
    url = html.unescape(url)
    m = re.match(r"https?://i\d\.wp\.com/(.+)", url)
    if m:
        url = "https://" + m.group(1)
    url = url.split("?", 1)[0]
    if url.startswith("//"):
        url = "https:" + url
    return url


def looks_like_filename(s):
    s = (s or "").strip()
    if not s:
        return True
    if re.match(r"^(img|dji|gopr|dsc|screenshot|photo|image|\d)[\w-]*$", s, re.I):
        return True
    # single "word" with digits or camel-case jumps: upload ids such as "W8AHYTZ", "PhVeuXP", "P1020345"
    return not re.search(r"\s", s) and bool(re.search(r"\d|[a-z][A-Z]", s))


def caption_for(img, container_tags=("figure", "li", "div")):
    """Caption text for an <img>: nearest figcaption in its figure/item, then data-image-caption, then alt."""
    n = img.parent
    while n is not None and n.tag not in container_tags:
        n = n.parent
    if n is not None:
        fc = n.find_first("figcaption")
        if fc and norm_ws(fc.text()).strip():
            return norm_ws(fc.text()).strip()
    cap = strip_tags(img.attrs.get("data-image-caption", ""))
    if cap.strip():
        return norm_ws(cap).strip()
    alt = norm_ws(img.attrs.get("alt", "")).strip()
    if alt and not looks_like_filename(alt):
        return alt
    title = norm_ws(img.attrs.get("data-image-title", "")).strip()
    if title and not looks_like_filename(title):
        return title
    return ""


def youtube_id(url):
    m = re.search(r"(?:youtube\.com/(?:embed/|watch\?v=|v/)|youtu\.be/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None


# --------------------------------------------------------------------------- converter

class Converter:
    def __init__(self, post, slug, max_width, download, verbose=True):
        self.post = post
        self.slug = slug
        self.max_width = max_width
        self.download = download
        self.verbose = verbose
        self.images = []  # (local_path, remote_url, alt)
        self.imports = set()
        self.warnings = []

    # -- images
    def register_image(self, img):
        url = image_source_url(img)
        if not url:
            return None
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or ".jpg"
        if ext not in IMAGE_EXTS:
            ext = ".jpg"
        for local, remote, _alt in self.images:
            if remote == url:
                return local
        local = f"/{self.slug}/{len(self.images) + 1}{ext}"
        alt = caption_for(img) or html.unescape(self.post["title"])
        self.images.append((local, url, alt))
        return local

    def photo_entry(self, img):
        local = self.register_image(img)
        if not local:
            return None
        alt = self.images[[l for l, _, _ in self.images].index(local)][2]
        return {"src": local, "alt": alt}

    # -- inline
    def inline(self, node, pending_images):
        out = []
        for c in node.children:
            if isinstance(c, str):
                out.append(esc_md(norm_ws(c)))
                continue
            t = c.tag
            if t == "img":
                pending_images.append(c)
            elif t == "br":
                out.append("<br />")
            elif t == "a":
                href = html.unescape(c.attrs.get("href", "")).strip()
                if c.find_first("img") and not norm_ws(c.text()).strip():
                    pending_images.extend(c.find_all("img"))
                    continue
                inner = self.inline(c, pending_images).strip()
                if not href or not inner:
                    out.append(inner)
                elif re.search(r"[()\s]", href):
                    out.append(f"[{inner}](<{href}>)")
                else:
                    out.append(f"[{inner}]({href})")
            elif t in ("strong", "b"):
                inner = self.inline(c, pending_images)
                out.append(self._wrap(inner, "**"))
            elif t in ("em", "i"):
                inner = self.inline(c, pending_images)
                out.append(self._wrap(inner, "_"))
            elif t == "code":
                out.append("`" + norm_ws(c.text()).strip() + "`")
            elif t in ("del", "s", "strike"):
                inner = self.inline(c, pending_images)
                out.append(self._wrap(inner, "~~"))
            elif t in ("script", "style", "meta", "link"):
                continue
            elif t == "iframe" or t in BLOCK_TAGS or c.has_class_prefix(GALLERY_CLASS_PREFIXES):
                pending_images.append(c)  # rendered as a block right after this paragraph
            else:
                out.append(self.inline(c, pending_images))
        return "".join(out)

    @staticmethod
    def _wrap(inner, mark):
        stripped = inner.strip()
        if not stripped:
            return inner
        lead = " " if inner[:1] == " " else ""
        trail = " " if inner[-1:] == " " else ""
        return f"{lead}{mark}{stripped}{mark}{trail}"

    # -- blocks
    def blocks(self, node):
        out = []
        for c in node.children:
            if isinstance(c, str):
                if c.strip():
                    out.append(esc_block_start(esc_md(norm_ws(c)).strip()))
                continue
            out.extend(self.block(c))
        return out

    def block(self, n):
        t = n.tag
        if t in ("script", "style", "meta", "link", "noscript"):
            return []
        if n.has_class_prefix(GALLERY_CLASS_PREFIXES) and n.find_first("img"):
            return self.gallery(n)
        if t == "p":
            return self.paragraph(n)
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = min(max(int(t[1]), 2), 4)  # h1 -> h2 (post title is the h1), cap at h4
            pending = []
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", self.inline(n, pending)).strip()
            res = [f"{'#' * level} {text}"] if text else []
            return res + self.pending_blocks(pending)
        if t in ("ul", "ol"):
            return self.list_block(n, 0)
        if t == "hr":
            return ["---"]
        if t == "blockquote":
            inner = self.blocks(n)
            return ["\n".join("> " + line for block in inner for line in block.split("\n"))] if inner else []
        if t == "figure":
            return self.figure(n)
        if t == "iframe":
            return self.iframe(n)
        if t == "img":
            return self.single_image(n, "")
        if t in ("div", "section", "article", "span", "center", "main", "aside"):
            imgs = n.find_all("img")
            if t == "div" and n.find_first("iframe") and not imgs and not n.find_first("p"):
                return sum((self.iframe(f) for f in n.find_all("iframe")), [])
            return self.blocks(n)
        if t in ("a", "strong", "em", "b", "i", "code", "br"):
            pending = []
            text = self.inline(Node("wrap", children=None) if False else n, pending).strip() if t != "br" else ""
            res = [esc_block_start(text)] if text else []
            return res + self.pending_blocks(pending)
        if t == "table":
            self.warnings.append("table kept as raw HTML")
            return [self.raw_html(n)]
        if t == "pre":
            return ["```\n" + n.text().strip("\n") + "\n```"]
        self.warnings.append(f"unhandled tag <{t}> flattened to text")
        return self.blocks(n)

    def paragraph(self, n):
        pending = []
        text = self.inline(n, pending).strip()
        res = [esc_block_start(text)] if text else []
        return res + self.pending_blocks(pending)

    def pending_blocks(self, pending):
        out = []
        for item in pending:
            if item.tag == "img":
                out.extend(self.single_image(item, caption_for(item)))
            elif item.tag == "iframe":
                out.extend(self.iframe(item))
            else:
                out.extend(self.block(item))
        return out

    def list_block(self, n, depth):
        lines = []
        ordered = n.tag == "ol"
        i = 0
        for li in n.element_children():
            if li.tag != "li":
                continue
            i += 1
            pending = []
            sub = []
            text_parts = []
            for c in li.children:
                if isinstance(c, Node) and c.tag in ("ul", "ol"):
                    sub.extend(self.list_block(c, depth + 1))
                elif isinstance(c, Node) and c.tag == "p":
                    text_parts.append(self.inline(c, pending))
                else:
                    text_parts.append(self.inline(Node("x", children=None) if False else self._wrap_node(c), pending))
            text = norm_ws(" ".join(text_parts)).strip()
            marker = f"{i}." if ordered else "-"
            lines.append(f"{'  ' * depth}{marker} {text}")
            lines.extend(sub)
            for extra in self.pending_blocks(pending):
                lines.append(extra)
        return ["\n".join(lines)] if lines else []

    @staticmethod
    def _wrap_node(child):
        w = Node("x")
        w.children = [child]
        return w

    def figure(self, n):
        classes = n.classes
        if any(c.startswith("wp-block-embed") for c in classes) or n.find_first("iframe"):
            frames = n.find_all("iframe")
            if frames:
                res = sum((self.iframe(f) for f in frames), [])
            else:
                wrapper = n.find_first("div")
                url = norm_ws(wrapper.text() if wrapper else n.text()).strip()
                res = [f"<{url}>"] if url.startswith("http") else []
            res += self.figcaption_block(n)
            return res
        imgs = n.find_all("img")
        if len(imgs) == 1:
            return self.single_image(imgs[0], caption_for(imgs[0]))
        if len(imgs) > 1:
            return self.gallery(n)
        return self.blocks(n)

    def figcaption_block(self, n):
        fc = [c for c in n.element_children() if c.tag == "figcaption"]
        if not fc:
            return []
        pending = []
        text = self.inline(fc[0], pending).strip()
        return [f"_{text}_"] if text else []

    def single_image(self, img, caption):
        local = self.register_image(img)
        if not local:
            return []
        alt = self.images[[l for l, _, _ in self.images].index(local)][2]
        lines = ["<figure>", f'  <img src="{local}" alt="{html_attr(alt)}" loading="lazy" />']
        if caption:
            lines.append(f"  <figcaption>{html.escape(caption, quote=False)}</figcaption>")
        lines.append("</figure>")
        return ["\n".join(lines)]

    def gallery(self, n):
        imgs = n.find_all("img")
        photos = [p for p in (self.photo_entry(i) for i in imgs) if p]
        if not photos:
            return []
        if len(photos) == 1:
            return self.single_image(imgs[0], caption_for(imgs[0]))
        cols = None
        for c in n.classes:
            m = re.match(r"columns-(\d+)$", c)
            if m:
                cols = int(m.group(1))
        if not cols:
            cols = min(len(photos), 3)
        cols = max(1, min(cols, 4, len(photos)))
        thumb = 600 if cols <= 2 else 400
        self.imports.add("PhotoGallery")
        items = ",\n".join(f"    {{ src: {js_str(p['src'])}, alt: {js_str(p['alt'])} }}" for p in photos)
        block = f"<PhotoGallery\n  photos={{[\n{items},\n  ]}}\n  columns={{{cols}}}\n  thumbnailSize={{{thumb}}}\n/>"
        # gallery-level caption (direct figcaption child of the gallery element)
        res = [block]
        direct_caps = [c for c in n.element_children() if c.tag == "figcaption"]
        if direct_caps:
            pending = []
            text = self.inline(direct_caps[0], pending).strip()
            if text:
                res.append(f"_{text}_")
        return res

    def iframe(self, f):
        src = html.unescape(f.attrs.get("src", "")).strip()
        vid = youtube_id(src)
        if vid:
            self.imports.add("EmbedYoutube")
            return [f'<EmbedYoutube videoId="{vid}" />']
        if "google.com/maps/embed" in src or "maps.google" in src:
            self.imports.add("EmbedGoogleMap")
            return [f"<EmbedGoogleMap src={js_str(src)} />"]
        if src:
            self.warnings.append(f"iframe kept as a link: {src[:80]}")
            return [f"[Embedded content]({src})"]
        return []

    def raw_html(self, n):
        def render(node):
            if isinstance(node, str):
                return html.escape(node, quote=False)
            attrs = "".join(f' {k}="{html_attr(v or "")}"' for k, v in node.attrs.items() if not k.startswith("data-") and k != "class")
            inner = "".join(render(c) for c in node.children)
            return f"<{node.tag}{attrs}>{inner}</{node.tag}>"
        return render(n)

    # -- run
    def convert(self):
        root = parse_html(self.post["content"])
        blocks = [b for b in self.blocks(root) if b and b.strip()]
        return "\n\n".join(blocks) + "\n"


# --------------------------------------------------------------------------- WordPress fetch

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "designcode-migrator/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_post(ref):
    """ref: full abbyontravel.com URL, a numeric post ID, or a slug."""
    ref = ref.strip()
    if re.fullmatch(r"\d+", ref):
        return fetch_json(WP_API + ref)
    slug = ref
    if "://" in ref or ref.startswith(OLD_HOST):
        path = urllib.parse.urlparse(ref if "://" in ref else "https://" + ref).path
        slug = [p for p in path.split("/") if p][-1]
    # Posts have a direct slug endpoint.
    try:
        post = fetch_json(WP_API + "slug:" + urllib.parse.quote(slug))
        if post.get("slug") == slug:
            return post
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    # Travel diaries on abbyontravel.com are WordPress *pages*: list them and match the slug.
    page_handle = None
    while True:
        q = {"type": "page", "number": 100, "status": "publish", "fields": "ID,slug"}
        if page_handle:
            q["page_handle"] = page_handle
        data = fetch_json(WP_API + "?" + urllib.parse.urlencode(q))
        for p in data.get("posts") or []:
            if p.get("slug") == slug:
                return fetch_json(WP_API + str(p["ID"]))
        page_handle = (data.get("meta") or {}).get("next_page")
        if not page_handle or not data.get("posts"):
            break
    sys.exit(f"error: no published post or page with slug '{slug}' on {OLD_HOST}")


def download(url, dest, max_width, force):
    if os.path.exists(dest) and not force:
        return "exists"
    params = ""
    if max_width and os.path.splitext(dest)[1].lower() in (".jpg", ".jpeg", ".png", ".webp"):
        params = f"?w={max_width}&strip=info"
    req = urllib.request.Request(url + params, headers={"User-Agent": "designcode-migrator/1.0"})
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
            fh.write(r.read())
    except urllib.error.HTTPError as e:
        if params:  # fall back to the untouched original
            req = urllib.request.Request(url, headers={"User-Agent": "designcode-migrator/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
                fh.write(r.read())
        else:
            raise e
    return f"{os.path.getsize(dest) // 1024} KB"


# --------------------------------------------------------------------------- frontmatter / output

def pick_category(post, override):
    if override:
        return override
    if post.get("type") == "page":
        return "Travels"
    cats = set(html.unescape(c) for c in (post.get("categories") or {}).keys())
    if cats & {"Hiking Guides", "Travel Planning"}:
        return "Guides"
    return "Thoughts"


def description_from(post):
    text = norm_ws(strip_tags(post.get("excerpt") or "")).strip()
    text = re.sub(r"\s*\[…\]\s*$|\s*\[\.\.\.\]\s*$|\s*…\s*$", "", text).strip()
    # keep whole sentences only
    m = list(re.finditer(r"[.!?](?=\s|$)", text))
    if m and m[-1].end() < len(text) and m[-1].end() > 60:
        text = text[: m[-1].end()]
    return text


def existing_matches(title, original_url):
    """Posts already in src/posts with the same title, or linking to the same abbyontravel.com URL."""
    hits = []
    key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    for name in sorted(os.listdir(POSTS_DIR)):
        if not name.endswith(".mdx"):
            continue
        with open(os.path.join(POSTS_DIR, name), encoding="utf-8") as fh:
            head = fh.read(3000)
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', head, re.M)
        t = re.sub(r"[^a-z0-9]+", " ", (m.group(1) if m else "").lower()).strip()
        if (key and t == key) or original_url.rstrip("/") in head:
            hits.append(f"src/posts/{name}")
    return hits


def old_path(post):
    path = urllib.parse.urlparse(post["URL"]).path
    return path.rstrip("/") or "/"


def add_redirect(old, new):
    with open(ASTRO_CONFIG, encoding="utf-8") as fh:
        cfg = fh.read()
    if re.search(r'["\']' + re.escape(old) + r'["\']\s*:', cfg):
        return False
    line = f'    "{old}": "{new}",\n'
    new_cfg, count = re.subn(r"(redirects:\s*\{\n)", lambda m: m.group(1) + line, cfg, count=1)
    if count != 1:
        sys.exit("error: could not find `redirects: {` in astro.config.mjs; add this line by hand:\n" + line)
    with open(ASTRO_CONFIG, "w", encoding="utf-8") as fh:
        fh.write(new_cfg)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", help="abbyontravel.com URL, WordPress slug, or numeric post ID")
    ap.add_argument("--slug")
    ap.add_argument("--category")
    ap.add_argument("--max-width", type=int, default=2048)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-redirect", action="store_true")
    args = ap.parse_args()

    post = fetch_post(args.ref)
    title = html.unescape(post["title"]).strip()
    slug = args.slug or post["slug"]
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        sys.exit(f"error: slug '{slug}' must be lowercase letters, digits and dashes")
    date = post["date"][:10]
    category = pick_category(post, args.category)
    original_url = f"https://{OLD_HOST}{old_path(post)}/"

    conv = Converter(post, slug, args.max_width, download=not args.dry_run)
    body = conv.convert()

    fm = [
        "---",
        f"slug: {yaml_str(slug)}",
        f"title: {yaml_str(title)}",
        f"date: {yaml_str(date)}",
        f"category: {yaml_str(category)}",
    ]
    desc = description_from(post)
    if desc:
        fm.append(f"description: {yaml_str(desc)}")
    fm.append(f"originalUrl: {yaml_str(original_url)}")
    fm.append("---")
    imports = "".join(f'import {name} from "../components/{name}.astro";\n' for name in sorted(conv.imports))
    mdx = "\n".join(fm) + "\n\n" + (imports + "\n" if imports else "") + body

    filename = f"{date}-{slug}.mdx"
    redirect_line = f'    "{old_path(post)}": "/posts/{slug}",'

    for existing in existing_matches(title, original_url):
        print(f"warning: {existing} looks like the same post (same title or URL). "
              f"To replace it, re-run with --slug <its slug> --force.", file=sys.stderr)

    for w in sorted(set(conv.warnings)):
        print(f"warning: {w}", file=sys.stderr)

    if args.dry_run:
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            out = os.path.join(args.out_dir, filename)
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(mdx)
            print(f"[dry-run] wrote {out}")
        else:
            print(mdx)
        print(f"[dry-run] {len(conv.images)} image(s) would be downloaded to public/{slug}/", file=sys.stderr)
        print(f"[dry-run] redirect to add: {redirect_line}", file=sys.stderr)
        return

    dest = os.path.join(POSTS_DIR, filename)
    clashes = [f for f in os.listdir(POSTS_DIR) if f.endswith(f"-{slug}.mdx") and f != filename]
    if clashes and not args.force:
        sys.exit(f"error: another post already uses slug '{slug}': {clashes[0]} (use --slug or --force)")
    if os.path.exists(dest) and not args.force:
        sys.exit(f"error: {os.path.relpath(dest, REPO_ROOT)} already exists (use --force to overwrite)")

    for local, remote, _alt in conv.images:
        target = os.path.join(PUBLIC_DIR, local.lstrip("/"))
        try:
            status = download(remote, target, args.max_width, args.force)
        except Exception as e:  # keep going; report at the end
            status = f"FAILED ({e})"
            conv.warnings.append(f"image download failed: {remote}")
        print(f"  {local:<28} <- {remote}  [{status}]")

    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(mdx)
    print(f"wrote {os.path.relpath(dest, REPO_ROOT)}")

    touched = [dest]
    if not args.no_redirect:
        if add_redirect(old_path(post), f"/posts/{slug}"):
            print(f"added redirect {old_path(post)} -> /posts/{slug} in astro.config.mjs")
            touched.append(ASTRO_CONFIG)
        else:
            print("redirect already present in astro.config.mjs")

    try:
        subprocess.run(["npx", "prettier", "--write", *touched], cwd=REPO_ROOT, check=True, capture_output=True)
    except Exception as e:
        print(f"warning: prettier did not run ({e}); run `npm run format`", file=sys.stderr)

    failed = [w for w in conv.warnings if w.startswith("image download failed")]
    if failed:
        print(f"\n{len(failed)} image(s) failed to download; re-run the same command to retry.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

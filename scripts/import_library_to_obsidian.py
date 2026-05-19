#!/usr/bin/env python3
"""Import the embedded HTML study library back into the canonical Obsidian vault.

The old HTML vault is treated as a public source archive. This script converts
public library pages into markdown notes under each compound's folder in the
regular peptide vault while skipping private inventory/order/vendor material.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DEFAULT_LIBRARY = Path(__file__).resolve().parents[1] / "library"
DEFAULT_VAULT = Path("/home/daneelbrain/Obsidian/💊 Peptides")

PRIVATE_ROOTS = {"📦 Inventory", "📋 Templates", "➕ Add to Wiki Inbox"}
PRIVATE_NEEDLES = ("inventory", "vendor", "order", "sourcing", "tailnet", "tailscale", "100.94.160.75")
STUDY_MARKERS = ("🔬 Science & Studies", "clinicaltrials.gov", "pubmed", "nct", "phase", "trial", "study")


def slugify_filename(name: str) -> str:
    safe = re.sub(r"[\\/:*?\"<>|]+", " ", name).strip()
    safe = re.sub(r"\s+", " ", safe)
    return (safe[:140] or "Imported Study") + ".md"


def is_private_item(item: dict[str, Any]) -> bool:
    raw = " ".join(str(item.get(k, "")) for k in ("title", "category", "path", "excerpt")).lower()
    parts = [p for p in str(item.get("path") or "").split("/") if p]
    if parts and parts[0] in PRIVATE_ROOTS:
        return True
    if any(root.lower() in raw for root in PRIVATE_ROOTS):
        return True
    # Sourcing/vendor/order pages are private unless they are clearly regulatory/FDA news pages.
    if any(n in raw for n in PRIVATE_NEEDLES) and not any(pub in raw for pub in ("pubmed", "clinicaltrials", "fda", "dailymed")):
        return True
    return False


def is_study_item(item: dict[str, Any], markdown: str = "") -> bool:
    raw = " ".join(str(item.get(k, "")) for k in ("title", "category", "path", "excerpt")) + " " + markdown[:1200]
    raw_l = raw.lower()
    return any(marker.lower() in raw_l for marker in STUDY_MARKERS)


def derive_category_compound(item: dict[str, Any]) -> tuple[str, str] | None:
    parts = [p for p in str(item.get("path") or "").split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    category = str(item.get("category") or "").strip()
    compound = str(item.get("compound") or "").strip()
    if category and compound and compound != "All":
        return category, compound
    return None


class ArticleMarkdownParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_article = False
        self.capture_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []
        self.link_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k: v or "" for k, v in attrs}
        classes = set(attrs_d.get("class", "").split())
        if tag == "article" or "article" in classes:
            self.in_article = True
            self.capture_depth = 1
            return
        if self.in_article:
            self.capture_depth += 1
        if tag in {"script", "style", "nav"}:
            self.skip_depth += 1
        if not self.in_article or self.skip_depth:
            return
        if tag in {"h1", "h2", "h3", "p", "li", "blockquote", "pre"}:
            self.parts.append("\n")
            if tag == "h1":
                self.parts.append("# ")
            elif tag == "h2":
                self.parts.append("## ")
            elif tag == "h3":
                self.parts.append("### ")
            elif tag == "li":
                self.parts.append("- ")
            elif tag == "blockquote":
                self.parts.append("> ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "strong":
            self.parts.append("**")
        elif tag == "em":
            self.parts.append("*")
        elif tag == "a":
            self.link_href = attrs_d.get("href") or None

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth and tag in {"script", "style", "nav"}:
            self.skip_depth -= 1
        if not self.in_article:
            return
        if not self.skip_depth:
            if tag in {"h1", "h2", "h3", "p", "li", "blockquote", "pre", "div"}:
                self.parts.append("\n")
            elif tag == "strong":
                self.parts.append("**")
            elif tag == "em":
                self.parts.append("*")
            elif tag == "a":
                self.link_href = None
        self.capture_depth -= 1
        if self.capture_depth <= 0:
            self.in_article = False

    def handle_data(self, data: str) -> None:
        if not self.in_article or self.skip_depth:
            return
        text = html.unescape(data)
        if not text.strip():
            if self.parts and not self.parts[-1].endswith((" ", "\n")):
                self.parts.append(" ")
            return
        if self.link_href and self.link_href.startswith("http"):
            self.parts.append(f"[{text.strip()}]({self.link_href})")
        else:
            self.parts.append(text)

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"([^\n])\n([A-Za-z0-9*])", r"\1\n\2", text)
        return text.strip()


def html_to_markdown(html_text: str) -> str:
    parser = ArticleMarkdownParser()
    parser.feed(html_text)
    md = parser.markdown()
    if md:
        return md
    # Fallback for bare fragments in tests/edge cases.
    text = re.sub(r"<\s*h1[^>]*>(.*?)<\s*/\s*h1\s*>", lambda m: "\n# " + re.sub("<[^>]+>", "", m.group(1)) + "\n", html_text, flags=re.I | re.S)
    text = re.sub(r"<\s*h2[^>]*>(.*?)<\s*/\s*h2\s*>", lambda m: "\n## " + re.sub("<[^>]+>", "", m.group(1)) + "\n", text, flags=re.I | re.S)
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}|[ \t]{2,}", "\n\n", text).strip()


def extract_source(markdown: str, item: dict[str, Any]) -> str:
    for pattern in [r"\*\*Source:\*\*\s*(https?://\S+)", r"\*\*Full Trial:\*\*\s*(https?://\S+)", r"(https?://(?:clinicaltrials\.gov|pubmed\.ncbi\.nlm\.nih\.gov)\S*)"]:
        match = re.search(pattern, markdown, flags=re.I)
        if match:
            return match.group(1).rstrip(").,;")
    href = str(item.get("href") or "")
    return href if href.startswith("http") else ""


def source_name_for(url: str) -> str:
    if "clinicaltrials.gov" in url:
        return "ClinicalTrials.gov"
    if "pubmed" in url or "ncbi.nlm.nih.gov" in url:
        return "PubMed"
    return "Imported HTML vault"


def build_note(item: dict[str, Any], markdown: str) -> str:
    title = str(item.get("title") or "Imported Study").strip()
    source = extract_source(markdown, item)
    frontmatter = [
        "---",
        "type: imported-library-study",
        "tags: [peptides, imported-library, study]",
        f"source: {json.dumps(source, ensure_ascii=False)}",
        f"source_name: {json.dumps(source_name_for(source), ensure_ascii=False)}",
        f"legacy_path: {json.dumps(str(item.get('path') or ''), ensure_ascii=False)}",
        f"legacy_href: {json.dumps(str(item.get('href') or ''), ensure_ascii=False)}",
        "generated_by: import_library_to_obsidian.py",
        "---",
        "",
    ]
    if not markdown.lstrip().startswith("#"):
        frontmatter.append(f"# {title}\n")
    body = markdown.strip()
    if source and source not in body:
        body += f"\n\n**Source:** {source}"
    return "\n".join(frontmatter) + body.rstrip() + "\n"


def import_library_to_obsidian(library: Path = DEFAULT_LIBRARY, vault: Path = DEFAULT_VAULT, *, dry_run: bool = False, overwrite: bool = True) -> dict[str, int]:
    library = Path(library)
    vault = Path(vault)
    manifest_path = library / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = {"imported": 0, "skipped_private": 0, "skipped_non_study": 0, "skipped_missing_html": 0, "skipped_existing": 0}

    for item in manifest:
        if is_private_item(item):
            result["skipped_private"] += 1
            continue
        location = derive_category_compound(item)
        if not location:
            result["skipped_non_study"] += 1
            continue
        href = str(item.get("href") or "")
        html_path = library / href
        if not html_path.exists():
            result["skipped_missing_html"] += 1
            continue
        markdown = html_to_markdown(html_path.read_text(encoding="utf-8", errors="ignore"))
        if not is_study_item(item, markdown):
            result["skipped_non_study"] += 1
            continue
        category, compound = location
        title = str(item.get("title") or Path(str(item.get("path") or href)).stem)
        original_stem = Path(str(item.get("path") or "")).stem
        target_name = slugify_filename(original_stem or title)
        target = vault / category / compound / "🔬 Science & Studies" / target_name
        if target.exists() and not overwrite:
            result["skipped_existing"] += 1
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(build_note(item, markdown), encoding="utf-8")
        result["imported"] += 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-overwrite", action="store_true")
    args = parser.parse_args()
    result = import_library_to_obsidian(args.library, args.vault, dry_run=args.dry_run, overwrite=not args.no_overwrite)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

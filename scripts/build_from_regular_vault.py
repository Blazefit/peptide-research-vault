#!/usr/bin/env python3
"""Build the public Research Vault data from the regular Obsidian peptide vault.

The Obsidian vault is the canonical source of truth. This script extracts the
public peptide overview pages plus public source notes and emits the static JSON
shape consumed by the Research Vault UI.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_VAULT = Path("/home/daneelbrain/Obsidian/💊 Peptides")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "peptide_details.json"
DEFAULT_LEGACY = Path(__file__).resolve().parents[1] / "data" / "peptide_details.json"
DEFAULT_LIBRARY_MANIFEST = Path(__file__).resolve().parents[1] / "library" / "manifest.json"

PRIVATE_ROOTS = {
    "📦 Inventory",
    "📋 Templates",
    "➕ Add to Wiki Inbox",
}

TIER_COLORS = {
    "S": "#FF3B47",
    "A": "#FF8A1F",
    "B": "#FFD60A",
    "C": "#22E07C",
    "D": "#4DA3FF",
    "F": "#8E8E93",
}

# Until the regular vault gets explicit tier frontmatter, preserve the public
# evidence tier work that already existed in the research dataset by slug.
KNOWN_TIER_OVERRIDES = {
    "semaglutide": "S",
    "tirzepatide": "S",
    "retatrutide": "S",
    "tesamorelin": "S",
    "hgh": "S",
    "liraglutide": "S",
    "sermorelin": "A",
    "bpc-157": "A",
    "tb-500": "B",
    "ghk-cu": "B",
    "mots-c": "B",
    "cagrisema": "B",
    "aod-9604": "C",
    "5-amino-1mq": "C",
    "ipamorelin": "C",
    "cjc-1295": "C",
    "semax": "C",
    "selank": "C",
    "pt-141-bremelanotide": "S",
}


def slugify(value: str) -> str:
    value = re.sub(r"\s+—\s+overview$", "", value, flags=re.I)
    value = value.replace("'", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "note"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4 :].lstrip()
    return parse_simple_yaml(raw), body


def parse_simple_yaml(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(clean_scalar(line[4:]))
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        current_key = key
        if value == "":
            data[key] = []
        else:
            data[key] = clean_scalar(value)
    return data


def clean_scalar(value: str) -> Any:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [clean_scalar(part.strip()) for part in inner.split(",") if part.strip()]
    return value


def title_from_body(path: Path, body: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, flags=re.M)
    title = m.group(1).strip() if m else path.stem
    return re.sub(r"\s+—\s+Overview$", "", title).strip()


def section_text(body: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    m = re.search(pattern, body, flags=re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def plain_excerpt(text: str, limit: int = 190) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r"[*_`>#|\[\]()]", " ", text)
    text = re.sub(r"^-\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    placeholders = ["draft summary placeholder", "add high-quality notes here"]
    if any(p in text.lower() for p in placeholders):
        return "Public notes are indexed from the regular peptide vault; summary needs final editorial pass."
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def aliases_from_meta(meta: dict[str, Any]) -> list[str]:
    aliases = meta.get("aliases", [])
    if isinstance(aliases, str):
        return [a.strip() for a in aliases.split(",") if a.strip()]
    if isinstance(aliases, list):
        return [str(a).strip() for a in aliases if str(a).strip()]
    return []


def public_md_files(vault: Path) -> list[Path]:
    return [p for p in vault.rglob("*.md") if not is_private_path(p, vault)]


def is_private_path(path: Path, vault: Path) -> bool:
    rel = path.relative_to(vault)
    return bool(rel.parts and rel.parts[0] in PRIVATE_ROOTS)


def load_legacy_by_slug(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(p.get("slug")): p for p in data.get("peptides", []) if p.get("slug")}


def source_type(path: Path, meta: dict[str, Any], body: str) -> str:
    tags = " ".join(str(t).lower() for t in meta.get("tags", [])) if isinstance(meta.get("tags"), list) else str(meta.get("tags", "")).lower()
    body_type = " ".join(re.findall(r"\*\*Type:\*\*\s*([^\n]+)", body, flags=re.I)).lower()
    folder = " ".join(path.parts).lower()
    combined = " ".join([tags, body_type, folder])
    if "youtube" in combined or "transcript" in combined:
        return "youtube"
    if "x feed" in combined or "social" in combined or "twitter" in combined:
        return "social"
    if "study" in combined or "pubmed" in combined:
        return "study"
    return "note"


def reference_bucket(kind: str, url: str) -> str:
    # Keep the existing UI's six research buckets while populating them from the
    # regular vault. PubMed/source studies land under Reviews until each note has
    # a more specific evidence-type field.
    if "clinicaltrials.gov" in url:
        return "official"
    if "fda.gov" in url or "dailymed" in url:
        return "official"
    if kind == "study":
        return "review"
    if kind == "youtube":
        return "observational"
    if kind == "social":
        return "observational"
    return "adverse"


def first_url(meta: dict[str, Any], body: str) -> str:
    source = str(meta.get("source", "")).strip()
    if source.startswith("http"):
        return source
    m = re.search(r"\*\*Link:\*\*\s*(https?://\S+)", body)
    return m.group(1).strip() if m else ""


def collect_source_notes(vault: Path) -> tuple[dict[str, Counter], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], int]:
    counts: dict[str, Counter] = defaultdict(Counter)
    notes_by_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    references: dict[str, list[dict[str, Any]]] = {k: [] for k in ["rct", "preclinical", "review", "official", "observational", "adverse"]}
    private_count = sum(1 for p in vault.rglob("*.md") if is_private_path(p, vault))

    for path in public_md_files(vault):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        meta, body = split_frontmatter(raw)
        if meta.get("type") == "peptide-overview" or path.name.endswith("— Overview.md"):
            continue
        rel = path.relative_to(vault)
        # Most routed notes are category/compound/source-type/note.md.
        if len(rel.parts) < 3:
            continue
        compound = rel.parts[1]
        slug = slugify(compound)
        kind = source_type(path, meta, body)
        url = first_url(meta, body)
        title = title_from_body(path, body)
        note = {
            "title": title,
            "type": kind,
            "source_name": str(meta.get("source_name") or meta.get("channel") or "Regular vault"),
            "url": url,
            "vault_path": rel.as_posix(),
        }
        counts[slug][kind] += 1
        notes_by_slug[slug].append(note)
        bucket = reference_bucket(kind, url)
        if url and len(references[bucket]) < 150:
            references[bucket].append(
                {
                    "header": title,
                    "description": f"{compound} · {note['source_name']} · {kind.title()}",
                    "notes": rel.as_posix(),
                    "url": url,
                }
            )
    return counts, notes_by_slug, references, private_count



def collect_library_entries(manifest_path: Path | None = DEFAULT_LIBRARY_MANIFEST) -> dict[str, list[dict[str, Any]]]:
    """Group the embedded old HTML vault pages by compound slug.

    The old library manifest has many entries with compound="All", but its path
    usually preserves the real structure: Category/Compound/source/note.md.
    Derive from that path so clicking Retatrutide shows every Retatrutide page.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not manifest_path or not manifest_path.exists():
        return grouped
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return grouped

    for item in manifest:
        raw_path = str(item.get("path") or "")
        parts = [part for part in raw_path.split("/") if part]
        if not parts or parts[0] in PRIVATE_ROOTS:
            continue
        if "📦 Inventory" in raw_path or "➕ Add to Wiki Inbox" in raw_path:
            continue
        compound = ""
        if len(parts) >= 2:
            compound = parts[1]
        elif item.get("compound") and item.get("compound") != "All":
            compound = str(item.get("compound"))
        if not compound or compound == "All":
            continue
        slug = slugify(compound)
        href = str(item.get("href") or "")
        if not href:
            continue
        grouped[slug].append(
            {
                "title": str(item.get("title") or Path(raw_path).stem),
                "type": "overview" if item.get("overview") else "library",
                "category": str(item.get("category") or (parts[0] if parts else "")),
                "vault_path": raw_path,
                "href": "library/" + href.lstrip("/"),
                "excerpt": plain_excerpt(str(item.get("excerpt") or ""), limit=260),
                "overview": bool(item.get("overview")),
            }
        )

    for slug, entries in grouped.items():
        entries.sort(key=lambda e: (not e.get("overview"), e.get("title", "").lower()))
    return grouped

def overview_files(vault: Path) -> list[Path]:
    files = []
    for path in public_md_files(vault):
        raw = path.read_text(encoding="utf-8", errors="ignore")[:1200]
        meta, _ = split_frontmatter(raw)
        if meta.get("type") == "peptide-overview" or path.name.endswith("— Overview.md"):
            files.append(path)
    return sorted(files)


def build_dataset(vault: Path = DEFAULT_VAULT, legacy_data: Path | None = DEFAULT_LEGACY) -> dict[str, Any]:
    vault = Path(vault)
    legacy = load_legacy_by_slug(legacy_data)
    counts, notes_by_slug, references, private_count = collect_source_notes(vault)
    library_by_slug = collect_library_entries(DEFAULT_LIBRARY_MANIFEST)

    peptides: list[dict[str, Any]] = []
    for path in overview_files(vault):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        meta, body = split_frontmatter(raw)
        name = title_from_body(path, body)
        slug = slugify(name)
        legacy_item = legacy.get(slug, {})
        what_it_is = section_text(body, "What It Is")
        one_liner = plain_excerpt(what_it_is) if what_it_is else legacy_item.get("one_liner", "Public notes from the regular peptide vault.")
        tier = str(meta.get("tier") or legacy_item.get("tier") or KNOWN_TIER_OVERRIDES.get(slug) or "D")
        category = str(meta.get("category") or path.relative_to(vault).parts[0])
        source_counts = dict(counts.get(slug, Counter()))
        library_entries = library_by_slug.get(slug, [])
        if library_entries:
            source_counts["library"] = len(library_entries)
        peptides.append(
            {
                "slug": slug,
                "name": name,
                "tier": tier,
                "tier_color": TIER_COLORS.get(tier, TIER_COLORS["D"]),
                "one_liner": one_liner,
                "category": category,
                "aliases": aliases_from_meta(meta),
                "vault_path": path.relative_to(vault).as_posix(),
                "source_counts": source_counts,
                "source_notes": notes_by_slug.get(slug, []),
                "library_entries": library_entries,
            }
        )

    peptides.sort(key=lambda p: ("SABCDF".find(p["tier"]) if p["tier"] in "SABCDF" else 99, p["name"].lower()))
    total_refs = sum(len(items) for items in references.values())
    return {
        "source": {
            "canonical": "regular_peptide_vault",
            "vault_path": str(vault),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "public_private_rule": "Generated from public overview/source notes; inventory, templates, and inbox folders are excluded.",
        },
        "summary": {
            "total_peptides": len(peptides),
            "total_references": total_refs,
            "private_notes_excluded": private_count,
            "total_source_notes_indexed": sum(sum(c.values()) for c in counts.values()),
            "total_library_entries_indexed": sum(len(v) for v in library_by_slug.values()),
            "source_counts": dict(sum((Counter(p["source_counts"]) for p in peptides), Counter())),
        },
        "peptides": peptides,
        "references": references,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--legacy-data", type=Path, default=DEFAULT_LEGACY)
    args = parser.parse_args()
    data = build_dataset(args.vault, args.legacy_data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} from {args.vault}")
    print(f"Peptides: {data['summary']['total_peptides']} | refs: {data['summary']['total_references']} | private excluded: {data['summary']['private_notes_excluded']}")


if __name__ == "__main__":
    main()

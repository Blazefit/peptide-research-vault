import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_from_regular_vault import build_dataset, slugify


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_slugify_handles_peptide_names():
    assert slugify("BPC-157 — Overview") == "bpc-157"
    assert slugify("PT-141 (Bremelanotide)") == "pt-141-bremelanotide"


def test_build_dataset_uses_regular_vault_overviews_and_excludes_private_inventory(tmp_path):
    vault = tmp_path / "vault"
    write(
        vault / "🩹 Healing & Tissue Repair" / "BPC-157" / "BPC-157 — Overview.md",
        """---
type: peptide-overview
category: "🩹 Healing & Tissue Repair"
aliases: "bpc-157, body protection compound"
---
# BPC-157 — Overview

> Educational knowledge base only.

## What It Is

A repair-focused peptide discussed for connective tissue and gut-barrier research.

## Mechanism / Pathway

Angiogenesis and nitric-oxide pathway signaling.
""",
    )
    write(
        vault / "🩹 Healing & Tissue Repair" / "BPC-157" / "🔬 Studies" / "Safety Study.md",
        """---
tags: [peptides, bpc-157, study]
source: "https://pubmed.ncbi.nlm.nih.gov/123/"
source_name: "PubMed"
date: 2026-05-01
type: routed-content
---
# Safety Study

**Source:** PubMed
**Type:** Study
**Link:** https://pubmed.ncbi.nlm.nih.gov/123/

## Content Preview

A study summary.
""",
    )
    write(
        vault / "📦 Inventory" / "Vendor Orders.md",
        "# Vendor Orders\n\nDo not publish this.\n",
    )

    data = build_dataset(vault)

    assert data["source"]["canonical"] == "regular_peptide_vault"
    assert data["summary"]["total_peptides"] == 1
    assert data["summary"]["private_notes_excluded"] == 1
    assert data["peptides"][0]["name"] == "BPC-157"
    assert data["peptides"][0]["category"] == "🩹 Healing & Tissue Repair"
    assert data["peptides"][0]["aliases"] == ["bpc-157", "body protection compound"]
    assert data["peptides"][0]["source_counts"]["study"] == 1
    assert "repair-focused peptide" in data["peptides"][0]["one_liner"]
    assert data["references"]["review"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert "Vendor Orders" not in json.dumps(data)

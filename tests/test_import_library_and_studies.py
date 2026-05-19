import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_from_regular_vault import build_dataset
from import_library_to_obsidian import import_library_to_obsidian


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_import_library_to_obsidian_converts_trial_html_into_compound_study_note(tmp_path):
    library = tmp_path / "library"
    vault = tmp_path / "vault"
    manifest = [
        {
            "title": "A Study of Retatrutide (LY3437943) in Participants With Obesity or Overweight",
            "category": "⚖️ GLP's & Weight Loss",
            "path": "⚖️ GLP's & Weight Loss/Retatrutide/🔬 Science & Studies/A Study of Retatrutide.md",
            "href": "pages/reta-study.html",
            "excerpt": "ClinicalTrials.gov phase 3 retatrutide obesity trial",
            "overview": False,
        },
        {
            "title": "Vendor Orders",
            "category": "📦 Inventory",
            "path": "📦 Inventory/Vendor Orders.md",
            "href": "pages/vendor.html",
            "excerpt": "private vendor data",
            "overview": False,
        },
    ]
    write(library / "manifest.json", json.dumps(manifest))
    write(
        library / "pages" / "reta-study.html",
        """<!doctype html><html><head><title>A Study of Retatrutide - Peptide Vault</title></head><body><main><div class="topbar"><span class="label">🔬 Science &amp; Studies/Retatrutide/A Study of Retatrutide.md</span></div><article class="article"><h1>A Study of Retatrutide</h1><p><strong>NCT ID:</strong> NCT07232719<br><strong>Status:</strong> ACTIVE_NOT_RECRUITING<br><strong>Phase:</strong> PHASE3<br><strong>Source:</strong> https://clinicaltrials.gov/study/NCT07232719</p><h2>Summary</h2><p>The purpose is to evaluate efficacy and safety for body weight reduction.</p></article></main></body></html>""",
    )
    write(library / "pages" / "vendor.html", "<article><h1>Vendor Orders</h1><p>Do not publish.</p></article>")

    result = import_library_to_obsidian(library, vault, dry_run=False)

    assert result["imported"] == 1
    assert result["skipped_private"] == 1
    imported = vault / "⚖️ GLP's & Weight Loss" / "Retatrutide" / "🔬 Science & Studies" / "A Study of Retatrutide.md"
    assert imported.exists()
    text = imported.read_text(encoding="utf-8")
    assert "type: imported-library-study" in text
    assert "NCT07232719" in text
    assert "https://clinicaltrials.gov/study/NCT07232719" in text
    assert "private vendor data" not in "\n".join(p.read_text(encoding="utf-8") for p in vault.rglob("*.md"))


def test_build_dataset_emits_searchable_studies_collection(tmp_path):
    vault = tmp_path / "vault"
    write(
        vault / "⚖️ GLP's & Weight Loss" / "Retatrutide" / "Retatrutide — Overview.md",
        """---
type: peptide-overview
category: "⚖️ GLP's & Weight Loss"
---
# Retatrutide — Overview

## What It Is
Triple agonist research compound.
""",
    )
    write(
        vault / "⚖️ GLP's & Weight Loss" / "Retatrutide" / "🔬 Science & Studies" / "A Study of Retatrutide.md",
        """---
type: imported-library-study
source: "https://clinicaltrials.gov/study/NCT07232719"
source_name: "ClinicalTrials.gov"
---
# A Study of Retatrutide

**Phase:** PHASE3

## Summary
Obesity trial for body weight reduction.
""",
    )

    data = build_dataset(vault, legacy_data=None)

    assert data["summary"]["total_studies"] == 1
    assert data["studies"][0]["peptide"] == "Retatrutide"
    assert data["studies"][0]["slug"] == "retatrutide"
    assert data["studies"][0]["url"] == "https://clinicaltrials.gov/study/NCT07232719"
    assert "Obesity trial" in data["studies"][0]["excerpt"]


def test_homepage_has_dedicated_studies_search_section():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="studies"' in html
    assert 'id="studySearchInput"' in html
    assert 'id="studyResults"' in html
    assert "renderStudyResults" in js
    assert "studySearchInput" in js

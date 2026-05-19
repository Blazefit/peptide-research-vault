import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_homepage_links_full_study_library():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert "library/index.html" in html
    assert "Full Study Library" in html
    assert "peptides-101-slideshow.html" in html


def test_embedded_library_excludes_private_inventory_and_inbox_content():
    manifest_path = ROOT / "library" / "manifest.json"
    assert manifest_path.exists(), "embedded study library manifest is missing"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_text = json.dumps(manifest, ensure_ascii=False)
    index_html = (ROOT / "library" / "index.html").read_text(encoding="utf-8")

    assert len(manifest) >= 1200
    assert len(list((ROOT / "library" / "pages").glob("*.html"))) == len(manifest)
    assert "CrossFit Blaze Peptide Inventory" not in manifest_text
    assert "📦 Inventory" not in manifest_text
    assert "➕ Add to Wiki Inbox" not in manifest_text
    assert "100.94.160.75" not in manifest_text
    assert "CrossFit Blaze Peptide Inventory" not in index_html
    assert "crossfit-blaze-peptide-inventory" not in index_html


def test_compound_drawer_data_includes_full_old_vault_library_under_compound():
    data = json.loads((ROOT / "data" / "peptide_details.json").read_text(encoding="utf-8"))
    retatrutide = next(p for p in data["peptides"] if p["slug"] == "retatrutide")

    assert len(retatrutide["source_notes"]) >= 60
    assert len(retatrutide["library_entries"]) >= 60
    assert any("LY3437943" in entry["title"] for entry in retatrutide["library_entries"])
    assert all(entry["href"].startswith("library/pages/") for entry in retatrutide["library_entries"])
    assert "📦 Inventory" not in json.dumps(retatrutide, ensure_ascii=False)

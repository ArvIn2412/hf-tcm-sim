"""Presentation integration and Unicode regression gates."""

from pathlib import Path


def test_stage4_modules_are_loaded():
    page = Path("src/hf_tcm/studio/static/scientific.html").read_text(encoding="utf-8")
    for name in ("layout4.js", "lab4.js", "study_catalog.js", "energy_interactive.js"):
        assert f"/static/{name}" in page
    assert "/static/stage4_layout.css" in page


def test_ukrainian_sources_and_reports():
    root = Path("src/hf_tcm/studio/static")
    for name, heading in (
        ("scientific.html", "Сузір’я 8PSK"),
        ("sequence_navigator.js", "Навігатор послідовності"),
        ("metric_live.js", "Декодування та решітка Вітербі"),
    ):
        source = (root / name).read_text(encoding="utf-8")
        assert heading in source
        assert "????" not in source
        assert "\ufffd" not in source
    for folder in ("ui_interactivity_stage3", "ui_interactivity_stage4"):
        for path in Path("outputs", folder).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            assert any("А" <= c <= "я" for c in text), path
            assert "????" not in text, path
            assert "\ufffd" not in text, path
    headings = {
        "01_FINAL_IMPLEMENTATION_UK.md": "Реалізація та фактичний статус етапу 4",
        "02_FUNCTIONAL_ACCEPTANCE_MATRIX_UK.md": "Матриця функціонального приймання",
        "03_PERFORMANCE_REPORT.md": "Вимірювання швидкодії",
        "04_BROWSER_TEST_RESULTS.md": "Результати браузерних E2E",
        "05_REMAINING_ISSUES_UK.md": "Залишкові проблеми та межі приймання",
        "06_USER_GUIDE_UK.md": "Інструкція користувача лабораторії",
    }
    for name, heading in headings.items():
        path = Path("outputs/ui_interactivity_stage4", name)
        # Reports are optional on portable CI checkouts, but existing reports
        # must retain their exact Ukrainian heading, not merely Cyrillic bytes.
        if path.exists():
            assert path.read_text(encoding="utf-8").startswith("# " + heading)

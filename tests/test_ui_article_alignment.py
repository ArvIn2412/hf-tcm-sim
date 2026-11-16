from pathlib import Path


def test_six_navigation_destinations():
    html = Path("src/hf_tcm/studio/static/scientific.html").read_text(encoding="utf8")
    assert html.count('<button class="tab') == 6
    assert "/static/article_workspace.js" in html


def test_article_profile_and_honest_gain():
    js = Path("src/hf_tcm/studio/static/article_workspace.js").read_text(encoding="utf8")
    assert "20000" in js
    assert "ENERGY_GAIN_NOT_ESTIMABLE" in js
    assert "Хемінг" in js and "Евклід" in js

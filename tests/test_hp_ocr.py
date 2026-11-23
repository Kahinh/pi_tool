"""V2.4: HP % OCR on synthetic hearts (+ real annotated captures when present)."""

import cv2
import numpy as np
import pytest

from conftest import screen_fixtures
from pi_tool.vision import hp_ocr
from pi_tool.vision.hp_ocr import Templates, crop_roi, learn, merge, read_hp
from synth import heart


@pytest.fixture(scope="module")
def tpl():
    samples = [learn(heart(t, 1.2), t) for t in ("12345%", "67890%")]
    return Templates(merge(samples), validated=True)


@pytest.mark.parametrize("scale", [0.8, 1.0, 1.3, 1.8])
@pytest.mark.parametrize("text", ["85%", "100%", "7%", "0%", "42%", "69%"])
def test_reads_percent_at_several_ui_sizes(tpl, text, scale):
    r = read_hp(heart(text, scale, seed=3), tpl)
    assert r.value == int(text[:-1]), r


@pytest.mark.parametrize(
    ("img", "reason"),
    [
        (heart("150%", 1.2), "hors 0–100"),
        (heart("1000%", 1.2), "mal formé"),
        (heart("05%", 1.2), "zéro initial"),
        (heart("", 1.2), "aucun texte"),
    ],
)
def test_rejects_invalid_values(tpl, img, reason):
    r = read_hp(img, tpl)
    assert r.value is None and reason in r.reason


def test_rejects_uncertain_reads(tpl):
    img = heart("85%", 1.2)
    blurred = cv2.GaussianBlur(img, (0, 0), 6)  # unreadable
    assert read_hp(blurred, tpl).value is None
    hidden = img.copy()
    h, w = hidden.shape[:2]
    hidden[: h // 2 + 4, w // 2 - 6 : w // 2 + 6] = (255, 255, 255)  # cursor over a digit
    assert read_hp(hidden, tpl).value is None
    assert read_hp(None, tpl).reason == "zone PV hors image"
    assert read_hp(img, Templates({})).reason.startswith("modèles")


def test_crop_roi_is_fractional():
    img = np.zeros((1000, 2000, 3), np.uint8)
    assert crop_roi(img, (0.5, 0.9, 0.05, 0.08)).shape == (80, 100, 3)
    assert crop_roi(img, (1.2, 0.9, 0.05, 0.08)) is None


def test_templates_roundtrip(tpl, tmp_path):
    hp_ocr.save_templates(tpl, tmp_path)
    back = hp_ocr.load_templates(tmp_path)
    assert back.validated and set(back.glyphs) == set(tpl.glyphs)
    assert read_hp(heart("58%", 1.0), back).value == 58
    assert not hp_ocr.load_templates(tmp_path / "none").complete


def test_learn_rejects_mismatch():
    with pytest.raises(ValueError):
        learn(heart("85%"), "100%")


@pytest.mark.fixtures
@pytest.mark.parametrize(
    ("png", "ann"),
    [f for f in screen_fixtures() if "hp_pct" in f[1] and "hp_roi" in f[1]] or [(None, None)],
)
def test_real_captures(png, ann):
    t = hp_ocr.load_templates()
    if png is None or not t.complete:
        pytest.skip("no annotated HP capture / digit templates yet (./dev digits)")
    x, y, w, h = ann["hp_roi"]
    r = read_hp(cv2.imread(str(png))[y : y + h, x : x + w], t)
    assert r.value == ann["hp_pct"], f"{png.name}: expected {ann['hp_pct']} got {r}"

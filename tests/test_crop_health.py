"""Crop health (AG-04): NDVI questions are answered by the red and NIR bands, never by a VLM guess.

Covers the routing of crop-health wording, the `optical.vegetation_health` tool and its answer, the
refusals when NDVI cannot be measured (no NIR, radar input, too little clear land), and the daily
refresh of the imagery cache. The server's cloud check for these questions is in test_server.py.
"""

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from satquery.agent.intents import classify, needs_crop_health, needs_multiple_dates, route_query
from satquery.api import analyze
from satquery.providers import copernicus
from satquery.providers.copernicus import CopernicusSentinelProvider
from satquery.schemas import AnalysisRequest, ImageInput
from satquery.settings import Settings
from satquery.specialists.tools import VegetationHealthParams
from satquery.specialists.vlm import FakeVLM

S2 = ["B02", "B03", "B04", "B08"]

TARGET_QUERIES = ["What is the NDVI?", "How healthy is the crop here?", "Is vegetation stressed here?"]


class RefusingVLM(FakeVLM):
    """Fails the test if anything asks the VLM: crop health must come from the bands alone."""

    def _refuse(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("the VLM must not be asked a crop-health question")

    caption = vqa = detect = ground = segment = change = _refuse


@pytest.fixture
def settings(tmp_path):
    return Settings(vlm_backend="fake", runs_dir=tmp_path / "runs")


def ask(settings, path, query="How healthy is the crop here?", modality="optical", **request):
    return analyze(AnalysisRequest(query=query, images=[ImageInput(path=path, modality=modality)], **request),
                   settings=settings, vlm=RefusingVLM())


# --------------------------------------------------------------------------------------- routing

@pytest.mark.parametrize("query", TARGET_QUERIES + [
    "Show me how healthy the crops are.",
    "Is the paddy under stress?",
    "What is the vegetation index of this field?",
    "Describe the condition of the farmland.",
])
def test_crop_health_wording_is_a_crop_health_task(query):
    intent = classify(query, "single_optical")
    assert intent.task == "crop_health" and intent.target == "vegetation"
    assert intent.matched_rule.startswith("crop-health cue (") and "-> NDVI crop-health analysis" in intent.matched_rule


@pytest.mark.parametrize("query, task", [
    ("Highlight the vegetation.", "grounding"),
    ("Describe the vegetation.", "caption"),
    ("Is there a water body in this image?", "vqa"),
    ("Is the lake healthy?", "vqa"),                              # a health cue, but no vegetation word
    ("What is the condition of the road?", "vqa"),
    ("Is there brown planthopper risk in the paddy?", "vqa"),     # pest names are not NDVI questions
])
def test_other_questions_keep_their_task(query, task):
    assert needs_crop_health(query) is None
    assert classify(query, "single_optical").task == task


@pytest.mark.parametrize("query", [
    "How healthy is the crop compared to last year?",
    "Has crop health declined since June?",
    "Has the crop health worsened?",
    "Is the crop deteriorating?",
])
def test_a_crop_health_question_about_change_over_time_needs_two_dates(query):
    """One date cannot show a change, so these take the two-date path instead of a single NDVI snapshot."""
    assert needs_multiple_dates(query)


@pytest.mark.parametrize("query", ["How can farmers improve crop health?", "Which improved rice varieties grow here?"])
def test_advice_wording_is_not_mistaken_for_change_over_time(query):
    assert needs_multiple_dates(query) is None


@pytest.mark.parametrize("query, route", [
    ("How healthy is the crop here?", "imagery"),
    ("What is the NDVI?", "imagery"),
    ("Is the rain stressing the crops?", "mixed"),   # the forecast cannot answer the crop-health half
    ("Will it rain on the farm tomorrow?", "weather"),
])
def test_routing_of_crop_health_and_weather_wording(query, route):
    decided, rule = route_query(query)
    assert decided == route
    if route == "mixed":
        assert "crop-health cue" in rule


# ----------------------------------------------------------------------------------- the analysis

@pytest.mark.parametrize("query", TARGET_QUERIES)
def test_the_target_queries_run_ndvi_and_expose_it_in_the_trace(settings, write_tiff, optical_scene, query):
    response = ask(settings, write_tiff("s2.tif", optical_scene, band_names=S2), query)
    assert response.status == "ok" and response.task == "crop_health"
    assert [(p.tool, p.purpose) for p in response.trace.plan] == [
        ("optical.vegetation_health", "primary evidence: NDVI from the red and near-infrared bands")]
    step = response.trace.steps[0]
    assert step.status == "ok" and step.model is None, "deterministic: no model involved"
    # The fixture's vegetation has red 500, NIR 3000: NDVI (3000 - 500) / 3500 = 0.714.
    assert step.outputs["mean_ndvi"] == pytest.approx(0.714, abs=0.01)
    assert step.outputs["class_fractions"]["dense"] == 1.0
    assert response.answer.startswith("Mean NDVI 0.71 over the clear land of this area: high vegetation vigour")
    assert response.confidence.value is None and not response.confidence.calibrated
    assert "computed directly from surface reflectance" in response.confidence.method


def test_water_is_left_out_of_the_land_figure(settings, write_tiff, optical_scene):
    response = ask(settings, write_tiff("s2.tif", optical_scene, band_names=S2))
    outputs = response.trace.steps[0].outputs
    # Over every pixel, the 400 water pixels (NDVI about -0.45) would pull the mean down to about 0.6.
    assert outputs["mean_ndvi"] > 0.7 and outputs["land_pixels"] == 64 * 64 - 400
    assert "Water (NDWI > 0, 9.8% of the area) is not counted as land." in response.answer


def test_the_answer_says_what_one_date_of_ndvi_cannot_show(settings, write_tiff, optical_scene):
    answer = ask(settings, write_tiff("s2.tif", optical_scene, band_names=S2), "Is vegetation stressed here?").answer
    assert "This is one date: NDVI shows how green and vigorous the vegetation is, not why." in answer
    assert "needs a comparison with the same season's baseline and a field check" in answer


def test_low_vigour_vegetation_is_measured_and_located(settings, write_tiff, optical_scene):
    patchy = optical_scene.copy()
    patchy[2, 40:60, 40:60], patchy[3, 40:60, 40:60] = 1500, 2500  # NDVI 0.25: low vigour
    response = ask(settings, write_tiff("patchy.tif", patchy, band_names=S2))
    fractions = response.trace.steps[0].outputs["class_fractions"]
    assert fractions["low"] == pytest.approx(400 / 3696, abs=0.001)
    assert "low (0.2–0.4) 10.8%" in response.answer
    assert "Low-vigour vegetation is mainly in the" in response.answer


def test_masked_cloud_is_not_counted_and_is_said(settings, write_tiff, optical_scene):
    clouded = optical_scene.copy()
    clouded[:, 50:, :] = np.nan  # what the server's SCL masking leaves for cloud
    response = ask(settings, write_tiff("clouded.tif", clouded, band_names=S2))
    assert response.trace.steps[0].outputs["land_pixels"] == 64 * 64 - 400 - 14 * 64
    assert "21.9% of the image had no usable data (for example, masked cloud) and is not counted." in response.answer


def test_the_vigour_map_is_visual_evidence_above_the_input_image(settings, write_tiff, optical_scene):
    response = ask(settings, write_tiff("s2.tif", optical_scene, band_names=S2))
    overlays = [e for e in response.evidence if e.kind == "overlay"]
    assert [e.label.split(" (")[0] for e in overlays] == ["input image", "NDVI vigour"], "NDVI is drawn on top"
    assert all(e.image_index == 0 and Path(e.file).is_file() for e in overlays)
    assert any(e.kind == "metric" and e.label == "mean NDVI (clear land)" for e in response.evidence)


def test_too_little_clear_land_is_said_and_nothing_is_estimated(settings, write_tiff, optical_scene):
    flooded = optical_scene.copy()
    flooded[:, :, :] = optical_scene[:, 5:6, 5:6]  # the water pixel's values everywhere
    response = ask(settings, write_tiff("flooded.tif", flooded, band_names=S2))
    assert response.answer.startswith("No crop-health figure was computed: only 0 clear land pixels remain")
    assert "No value was estimated in its place." in response.answer
    assert "Mean NDVI" not in response.answer and "mean_ndvi" not in response.trace.steps[0].outputs


def test_an_image_without_nir_is_refused_not_guessed(settings, write_tiff, optical_scene):
    rgb = write_tiff("rgb.tif", optical_scene[[2, 1, 0]], band_names=["red", "green", "blue"])
    response = ask(settings, rgb)
    assert response.status == "invalid_input" and response.trace.steps == []
    issue = next(i for i in response.trace.validation if i.severity == "error")
    assert issue.code == "missing_nir" and "no NDVI was computed and none was estimated" in issue.message


def test_a_radar_image_is_refused_for_crop_health(settings, write_tiff, sar_scene):
    response = ask(settings, write_tiff("s1.tif", sar_scene, band_names=["VV", "VH"]), modality="sar")
    assert response.status == "invalid_input" and response.trace.steps == []
    issue = next(i for i in response.trace.validation if i.severity == "error")
    assert issue.code == "crop_health_needs_optical" and "cannot measure NDVI" in issue.message


def test_crop_health_can_be_forced_by_the_caller(settings, write_tiff, optical_scene):
    response = ask(settings, write_tiff("s2.tif", optical_scene, band_names=S2), "Analyse this.",
                   forced_task="crop_health")
    assert response.task == "crop_health" and response.trace.intent.matched_rule == "task forced by caller"


def test_the_vigour_breaks_are_permitted_parameters_only():
    with pytest.raises(ValidationError):
        VegetationHealthParams(sparse_below=0.5, low_below=0.4)
    with pytest.raises(ValidationError):
        VegetationHealthParams(threshold=0.3)


# ------------------------------------------------------------------------------ the imagery cache

def test_a_cached_scene_is_not_served_on_a_later_day(monkeypatch):
    """The search window is "the last N days" from today: yesterday's search must not answer today."""
    provider = CopernicusSentinelProvider("id", "secret")
    bbox, bands = (93.70, 24.45, 93.80, 24.55), ["B02", "B03", "B04", "B08"]
    keys = {}
    for day in ("2026-10-07", "2026-10-08"):
        monkeypatch.setattr(copernicus, "search_date", lambda day=day: day)
        keys[day] = (provider.cache_key(bbox, bands), provider.sar_cache_key(bbox),
                     provider.optical_sar_cache_key(bbox, bands))
        assert keys[day] == (provider.cache_key(bbox, bands), provider.sar_cache_key(bbox),
                             provider.optical_sar_cache_key(bbox, bands)), "stable within a day"
    assert all(a != b for a, b in zip(keys["2026-10-07"], keys["2026-10-08"]))

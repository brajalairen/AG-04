"""The web client's wire types (web/src/state/types.ts) mirror the Python models by hand. This keeps
the two from drifting apart: every interface must list exactly the fields its model sends."""

import re
from pathlib import Path

import pytest

from satquery import schemas, server
from satquery.agri import escalation as agri_escalation, history as agri_history, models as agri_models, \
    routes as agri_routes, views as agri_views

TYPES_TS = Path(__file__).resolve().parent.parent / "web" / "src" / "state" / "types.ts"

MIRRORED = {
    "ImageSummary": schemas.ImageSummary,
    "ValidationIssue": schemas.ValidationIssue,
    "Intent": schemas.Intent,
    "PlanStep": schemas.PlanStep,
    "Evidence": schemas.Evidence,
    "Confidence": schemas.Confidence,
    "StepResult": schemas.StepResult,
    "ExecutionTrace": schemas.ExecutionTrace,
    "AnalysisResponse": schemas.AnalysisResponse,
    "OverlayLayer": server.OverlayLayer,
    "AreaScope": server.AreaScope,
    "AnalyzeResult": server.AnalyzeResult,
    "UploadInfo": server.UploadInfo,
    "Example": server.Example,
    "FetchImageryResult": server.FetchImageryResult,
    "FetchedScene": server.FetchedScene,
    "ComparisonWindow": server.ComparisonWindow,
    "TemporalInfo": server.TemporalInfo,
    "Health": server.Health,
    "WeatherInfo": server.WeatherInfo,
    "RouteResult": server.RouteResult,
    "OpticalQualityInfo": server.OpticalQualityInfo,
    "SceneCheck": server.SceneCheck,
    # AG-04 risk dashboard
    "AgriProvenance": agri_models.Provenance,
    "PestReport": agri_models.PestReport,
    "DayCheck": agri_models.DayCheck,
    "PestEvaluation": agri_models.PestEvaluation,
    "NdviWindow": agri_models.NdviWindow,
    "NdviAnomaly": agri_models.NdviAnomaly,
    "FactorResult": agri_models.FactorResult,
    "PestRiskAssessment": agri_models.PestRiskAssessment,
    "PestNotAssessed": agri_models.PestNotAssessed,
    "RiskConfidence": agri_models.RiskConfidence,
    "RiskAssessment": agri_models.RiskAssessment,
    "AreaSummary": agri_routes.AreaSummary,
    "AgriOverview": agri_routes.AgriOverview,
    "AgriAreaDetail": agri_routes.AgriAreaDetail,
    "AgriQueryResult": agri_routes.AgriQueryResult,
    "DistrictSummary": agri_routes.DistrictSummary,
    # AG-04 Phase 3 decision-support views
    "AgriTrustLabels": agri_views.TrustLabels,
    "AgriInputStatus": agri_views.InputStatus,
    "AgriRulesStatus": agri_views.RulesStatus,
    "AgriBoundaryStatus": agri_views.BoundaryStatus,
    "AgriLimitation": agri_views.Limitation,
    "AgriAreaStatus": agri_views.AreaStatus,
    "AgriAreaList": agri_views.AreaList,
    "AgriFactorPoints": agri_views.FactorPoints,
    "AgriPersistence": agri_escalation.Persistence,
    "AgriEscalationFacts": agri_escalation.EscalationFacts,
    "AgriAttentionStatus": agri_escalation.AttentionStatus,
    "AgriPriorityItem": agri_views.PriorityItem,
    "AgriPriorityList": agri_views.PriorityList,
    "AgriAreaRef": agri_views.AreaRef,
    "AgriOverallView": agri_views.OverallView,
    "AgriWeatherDay": agri_views.WeatherDay,
    "AgriWeatherPest": agri_views.WeatherPest,
    "AgriWeatherView": agri_views.WeatherView,
    "AgriNdviView": agri_views.NdviView,
    "AgriObservationView": agri_views.ObservationView,
    "AgriPestView": agri_views.PestView,
    "AgriNotAssessed": agri_views.NotAssessedView,
    "AgriPestsView": agri_views.PestsView,
    "AgriRuleSource": agri_views.RuleSource,
    "AgriFieldVerification": agri_views.FieldVerification,
    "AgriProvenanceView": agri_views.ProvenanceView,
    "AgriAreaExplanation": agri_views.AreaExplanation,
    "AgriPestLevel": agri_history.PestLevel,
    "AgriHistoryEntry": agri_history.HistoryEntry,
    "AgriAreaHistory": agri_views.AreaHistory,
    "AgriVocabulary": agri_views.Vocabulary,
}


def interface_fields(source: str, name: str) -> set[str]:
    block = re.search(rf"export interface {name} \{{\n(.*?)\n\}}", source, re.S)
    assert block, f"interface {name} not found in types.ts"
    # Top-level members are indented two spaces; nested object types stay on one line.
    return set(re.findall(r"^  (\w+)\??:", block.group(1), re.M))


@pytest.mark.parametrize("name", sorted(MIRRORED))
def test_web_types_match_the_python_models(name):
    source = TYPES_TS.read_text(encoding="utf-8")
    assert interface_fields(source, name) == set(MIRRORED[name].model_fields), f"{name} differs between types.ts and Python"

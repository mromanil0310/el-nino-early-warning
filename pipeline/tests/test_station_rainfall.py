"""
test_station_rainfall.py
Unit tests for the station-level, probability-based rainfall severity model (ELN-031).

Locks the calibration of the continuous severity function against the legacy
categorical step weights, verifies the anomaly↔probability mappings, and checks that
weighted station→province aggregation both averages correctly and — the whole point —
DIFFERENTIATES provinces with different drought tilts (the old model collapsed them
all to an identical score).

Run: python -m pytest pipeline/tests/test_station_rainfall.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from outlook import (  # noqa: E402
    anomaly_from_probabilities,
    label_from_probabilities,
    parse_station_probabilities_from_text,
    probabilities_from_anomaly,
    probabilities_from_category,
    severity_from_probabilities,
)


class TestSeverityFromProbabilities:
    def test_all_below_is_max(self):
        assert severity_from_probabilities(1.0, 0.0, 0.0) == 1.0

    def test_all_above_is_zero(self):
        assert severity_from_probabilities(0.0, 0.0, 1.0) == 0.0

    def test_all_near_is_zero(self):
        # Near-normal rainfall carries no drought risk: severity = P_below only.
        assert severity_from_probabilities(0.0, 1.0, 0.0) == 0.0

    def test_climatology_is_one_third(self):
        # 1/3 each → severity = P_below = 1/3 (~0.333), Low even at peak vulnerability.
        assert severity_from_probabilities(1 / 3, 1 / 3, 1 / 3) == pytest.approx(1 / 3, abs=1e-3)

    def test_accepts_percentages(self):
        # Same distribution expressed 0–100 must give the same severity as 0–1.
        assert severity_from_probabilities(70, 25, 5) == pytest.approx(
            severity_from_probabilities(0.70, 0.25, 0.05)
        )

    def test_normalizes_non_unit_sum(self):
        # Not summing to 1 (or 100) is still normalized.
        assert severity_from_probabilities(2, 1, 1) == pytest.approx(
            severity_from_probabilities(0.5, 0.25, 0.25)
        )

    def test_degenerate_zero(self):
        assert severity_from_probabilities(0, 0, 0) == 0.0

    def test_stronger_below_tilt_is_more_severe(self):
        mild = severity_from_probabilities(0.50, 0.35, 0.15)
        strong = severity_from_probabilities(0.80, 0.15, 0.05)
        assert strong > mild


class TestCalibrationVsLegacy:
    """A canonical distribution per legacy label keeps the below-normal end calibrated
    with the legacy step weights (below ≈0.75, much-below ≈0.95) so switching to the
    continuous model doesn't silently move High warnings; near/above map low."""

    def test_below_normal_reproduces_075(self):
        pb, pn, pa = probabilities_from_category("below normal")
        assert severity_from_probabilities(pb, pn, pa) == pytest.approx(0.75, abs=0.03)

    def test_much_below_normal_near_one(self):
        pb, pn, pa = probabilities_from_category("much below normal")
        assert severity_from_probabilities(pb, pn, pa) == pytest.approx(0.95, abs=0.05)

    def test_above_normal_near_zero(self):
        pb, pn, pa = probabilities_from_category("above normal")
        assert severity_from_probabilities(pb, pn, pa) < 0.30

    def test_near_normal_stays_low(self):
        # Near Normal (0% anomaly) → severity ≈ climatological floor → Low at reproductive.
        pb, pn, pa = probabilities_from_category("near normal")
        assert severity_from_probabilities(pb, pn, pa) < 0.35

    def test_unknown_label_defaults_near(self):
        assert probabilities_from_category("gibberish") == probabilities_from_category("near normal")


class TestDeadZoneKeepsMildProvincesLow:
    """The calibration fix: mild-anomaly provinces (−5…−9%) must score Low even at peak
    crop vulnerability (severity < 0.35), while the drought belt (−18…−30%) stays in the
    Medium/High range and differentiates."""

    def test_mild_anomalies_low(self):
        for a in (-5, -8, -9):
            sev = severity_from_probabilities(*probabilities_from_anomaly(a))
            assert sev < 0.35, f"anomaly {a}% severity {sev} should be Low (<0.35)"

    def test_drought_belt_high(self):
        for a in (-22, -25, -28, -30):
            sev = severity_from_probabilities(*probabilities_from_anomaly(a))
            assert sev > 0.65, f"anomaly {a}% severity {sev} should be High (>0.65)"

    def test_drought_belt_differentiates(self):
        sevs = [severity_from_probabilities(*probabilities_from_anomaly(a)) for a in (-22, -25, -28, -30)]
        assert len(set(round(s, 3) for s in sevs)) == 4  # each distinct


class TestProbabilitiesFromAnomaly:
    def test_sums_to_one(self):
        for a in (-45, -30, -25, -10, 0, 15, 30):
            pb, pn, pa = probabilities_from_anomaly(a)
            assert pb + pn + pa == pytest.approx(1.0)
            assert all(0.0 <= p <= 1.0 for p in (pb, pn, pa))

    def test_drier_raises_below(self):
        dry = probabilities_from_anomaly(-30)[0]
        neutral = probabilities_from_anomaly(0)[0]
        wet = probabilities_from_anomaly(20)[0]
        assert dry > neutral > wet

    def test_severity_monotonic_in_dryness(self):
        sevs = [severity_from_probabilities(*probabilities_from_anomaly(a)) for a in (20, 0, -10, -25, -40)]
        assert sevs == sorted(sevs)  # drier → higher severity, strictly increasing order


class TestAnomalyRoundTrip:
    def test_roundtrip_within_clamp(self):
        for a in (-30, -25, -10, 0):
            probs = probabilities_from_anomaly(a)
            assert anomaly_from_probabilities(*probs) == pytest.approx(a, abs=1.0)


class TestLabelFromProbabilities:
    def test_strong_below(self):
        assert label_from_probabilities(0.90, 0.07, 0.03) == "Much Below Normal"

    def test_drought_belt_labelled_below_not_much(self):
        # −25% → P_below ≈ 0.74 → "Below Normal", not escalated to "Much Below Normal".
        assert label_from_probabilities(*probabilities_from_anomaly(-25)) == "Below Normal"

    def test_moderate_below(self):
        assert label_from_probabilities(0.55, 0.35, 0.10) == "Below Normal"

    def test_near(self):
        assert label_from_probabilities(0.34, 0.33, 0.33) == "Near Normal"

    def test_above(self):
        assert label_from_probabilities(0.10, 0.30, 0.60) == "Above Normal"


class TestWeightedStationAggregation:
    """Province severity = Σ(weight × station_severity). Mirrors int_province_rainfall.sql.
    Weights per province sum to 1.0 (enforced by assert_station_weights_sum_to_one.sql)."""

    @staticmethod
    def province_severity(stations):
        # stations: list of (weight, (pb, pn, pa))
        return sum(w * severity_from_probabilities(*probs) for w, probs in stations)

    def test_single_station(self):
        s = self.province_severity([(1.0, (0.70, 0.25, 0.05))])
        assert s == pytest.approx(severity_from_probabilities(0.70, 0.25, 0.05))

    def test_two_station_average(self):
        # 0.5/0.5 blend of a dry and a wet station lands between them.
        dry = severity_from_probabilities(0.80, 0.15, 0.05)
        wet = severity_from_probabilities(0.20, 0.30, 0.50)
        blended = self.province_severity([(0.5, (0.80, 0.15, 0.05)), (0.5, (0.20, 0.30, 0.50))])
        assert min(dry, wet) < blended < max(dry, wet)
        assert blended == pytest.approx((dry + wet) / 2)

    def test_provinces_differentiate(self):
        # THE regression this whole change exists to fix: two provinces with different
        # drought tilts must get different severities (old categorical model gave both
        # the same 0.75).
        nueva_ecija = self.province_severity([(1.0, probabilities_from_anomaly(-30))])
        laguna = self.province_severity([(1.0, probabilities_from_anomaly(-10))])
        assert nueva_ecija > laguna
        assert abs(nueva_ecija - laguna) > 0.05


class TestStationTextParser:
    STATIONS = [("DAGUPAN", "Dagupan City Synoptic Station"), ("CABANATUAN", "Cabanatuan Synoptic Station")]

    def test_parses_triple_after_station_name(self):
        text = "Seasonal Rainfall Outlook\nDagupan City 70 25 5\nCabanatuan 78 18 4\n"
        out = parse_station_probabilities_from_text(text, self.STATIONS)
        assert out["DAGUPAN"] == (70.0, 25.0, 5.0)
        assert out["CABANATUAN"] == (78.0, 18.0, 4.0)

    def test_matches_by_station_code_when_name_absent(self):
        text = "DAGUPAN: below 60 near 30 above 10"
        out = parse_station_probabilities_from_text(text, self.STATIONS)
        assert out["DAGUPAN"] == (60.0, 30.0, 10.0)

    def test_rejects_triples_not_summing_to_100(self):
        text = "Dagupan City temperature 28 humidity 80 wind 12"
        out = parse_station_probabilities_from_text(text, self.STATIONS)
        assert "DAGUPAN" not in out  # 28+80+12 != ~100 in a valid consecutive window

    def test_missing_station_omitted(self):
        out = parse_station_probabilities_from_text("no stations here", self.STATIONS)
        assert out == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

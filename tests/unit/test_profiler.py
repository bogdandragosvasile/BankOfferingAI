"""Unit tests for the customer profiler module.

Tests build_profile() which returns a ProfileResult with:
  customer_id, life_stage, risk_score, financial_health,
  lifestyle_segment, investor_readiness, risk_bucket,
  context_signals, family_context

Financial health rules:
  healthy   -> debt_to_income < 0.5 AND monthly_savings > 500
  watchlist -> 0.5 <= dti < 1.2
  fragile   -> dti >= 1.2

Investor readiness rules:
  high   -> idle_cash > 10000 AND monthly_savings > 500 AND has life_event
  medium -> 5000 < idle_cash <= 10000
  low    -> idle_cash <= 5000
"""

import pytest
from unittest.mock import MagicMock, patch

from services.worker.profiler import build_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_features(
    *,
    age: int = 35,
    monthly_income: float = 5000.0,
    monthly_debt_payment: float = 1000.0,
    monthly_savings: float = 800.0,
    idle_cash: float = 8000.0,
    dependents: int = 0,
    married: bool = False,
    risk_profile: str = "medium",
    event_type: str | None = None,
    employment_status: str = "employed",
) -> dict:
    """Build a minimal feature dict for build_profile()."""
    features: dict = {
        "age": age,
        "monthly_income": monthly_income,
        "monthly_debt_payment": monthly_debt_payment,
        "monthly_savings": monthly_savings,
        "idle_cash": idle_cash,
        "dependents": dependents,
        "married": married,
        "risk_profile": risk_profile,
        "employment_status": employment_status,
    }
    if event_type is not None:
        features["event_type"] = event_type
    return features


# ---------------------------------------------------------------------------
# Financial health tests
# ---------------------------------------------------------------------------


class TestFinancialHealth:
    def test_financial_health_healthy(self):
        """dti < 0.5 AND monthly_savings > 500 -> healthy."""
        # income 6000, debt 2400 -> dti = 0.4, savings = 1200
        features = make_features(
            monthly_income=6000.0,
            monthly_debt_payment=2400.0,
            monthly_savings=1200.0,
        )
        result = build_profile("cust_healthy_001", features)
        assert result.financial_health == "healthy"

    def test_financial_health_healthy_boundary_dti(self):
        """dti just below 0.5 boundary -> still healthy (savings also > 500)."""
        # income 8000, debt 3999 -> dti ~0.4999
        features = make_features(
            monthly_income=8000.0,
            monthly_debt_payment=3999.0,
            monthly_savings=600.0,
        )
        result = build_profile("cust_healthy_002", features)
        assert result.financial_health == "healthy"

    def test_financial_health_watchlist_lower(self):
        """dti = 0.5 (inclusive lower bound) -> watchlist."""
        # income 4000, debt 2000 -> dti = 0.5
        features = make_features(
            monthly_income=4000.0,
            monthly_debt_payment=2000.0,
            monthly_savings=300.0,
        )
        result = build_profile("cust_watchlist_001", features)
        assert result.financial_health == "watchlist"

    def test_financial_health_watchlist_mid(self):
        """0.5 <= dti < 1.2 -> watchlist."""
        # income 5000, debt 4000 -> dti = 0.8
        features = make_features(
            monthly_income=5000.0,
            monthly_debt_payment=4000.0,
            monthly_savings=400.0,
        )
        result = build_profile("cust_watchlist_002", features)
        assert result.financial_health == "watchlist"

    def test_financial_health_fragile(self):
        """dti >= 1.2 -> fragile."""
        # income 3000, debt 3600 -> dti = 1.2
        features = make_features(
            monthly_income=3000.0,
            monthly_debt_payment=3600.0,
            monthly_savings=100.0,
        )
        result = build_profile("cust_fragile_001", features)
        assert result.financial_health == "fragile"

    def test_financial_health_fragile_severe(self):
        """dti well above 1.2 -> fragile."""
        # income 3000, debt 6000 -> dti = 2.0
        features = make_features(
            monthly_income=3000.0,
            monthly_debt_payment=6000.0,
            monthly_savings=0.0,
        )
        result = build_profile("cust_fragile_002", features)
        assert result.financial_health == "fragile"

    @pytest.mark.parametrize(
        "income,debt,savings,expected",
        [
            (6000.0, 2400.0, 1200.0, "healthy"),    # dti=0.40, sav=1200
            (5000.0, 2000.0, 600.0,  "healthy"),    # dti=0.40, sav=600
            (4000.0, 2000.0, 300.0,  "watchlist"),  # dti=0.50
            (5000.0, 4500.0, 200.0,  "watchlist"),  # dti=0.90
            (3000.0, 3600.0, 100.0,  "fragile"),    # dti=1.20
            (3000.0, 5000.0, 50.0,   "fragile"),    # dti=1.67
        ],
    )
    def test_financial_health_parametrized(self, income, debt, savings, expected):
        features = make_features(
            monthly_income=income,
            monthly_debt_payment=debt,
            monthly_savings=savings,
        )
        result = build_profile("cust_param", features)
        assert result.financial_health == expected


# ---------------------------------------------------------------------------
# Investor readiness tests
# ---------------------------------------------------------------------------


class TestInvestorReadiness:
    def test_investor_readiness_high(self):
        """idle_cash > 10000 AND monthly_savings > 500 AND has life event -> high."""
        features = make_features(
            idle_cash=15000.0,
            monthly_savings=800.0,
            event_type="salary_increase",
        )
        result = build_profile("cust_inv_high_001", features)
        assert result.investor_readiness == "high"

    def test_investor_readiness_high_travel_event(self):
        """high investor readiness with travel_spike event."""
        features = make_features(
            idle_cash=20000.0,
            monthly_savings=1200.0,
            event_type="travel_spike",
        )
        result = build_profile("cust_inv_high_002", features)
        assert result.investor_readiness == "high"

    def test_investor_readiness_medium(self):
        """5000 < idle_cash <= 10000 -> medium."""
        features = make_features(idle_cash=7500.0, monthly_savings=300.0)
        result = build_profile("cust_inv_med_001", features)
        assert result.investor_readiness == "medium"

    def test_investor_readiness_medium_boundary_lower(self):
        """idle_cash just above 5000 -> medium."""
        features = make_features(idle_cash=5001.0, monthly_savings=200.0)
        result = build_profile("cust_inv_med_002", features)
        assert result.investor_readiness == "medium"

    def test_investor_readiness_medium_boundary_upper(self):
        """idle_cash at 10000 -> medium (not high)."""
        features = make_features(idle_cash=10000.0, monthly_savings=300.0)
        result = build_profile("cust_inv_med_003", features)
        assert result.investor_readiness == "medium"

    def test_investor_readiness_low(self):
        """idle_cash <= 5000 -> low."""
        features = make_features(idle_cash=2500.0, monthly_savings=200.0)
        result = build_profile("cust_inv_low_001", features)
        assert result.investor_readiness == "low"

    def test_investor_readiness_low_zero(self):
        """idle_cash = 0 -> low."""
        features = make_features(idle_cash=0.0, monthly_savings=100.0)
        result = build_profile("cust_inv_low_002", features)
        assert result.investor_readiness == "low"

    @pytest.mark.parametrize(
        "idle_cash,monthly_savings,event_type,expected",
        [
            (15000.0, 700.0, "salary_increase", "high"),
            (12000.0, 600.0, "bonus_received",  "high"),
            (7500.0,  300.0, None,              "medium"),
            (10000.0, 200.0, None,              "medium"),
            (5000.0,  400.0, None,              "low"),
            (1000.0,  100.0, None,              "low"),
        ],
    )
    def test_investor_readiness_parametrized(self, idle_cash, monthly_savings, event_type, expected):
        features = make_features(
            idle_cash=idle_cash,
            monthly_savings=monthly_savings,
            event_type=event_type,
        )
        result = build_profile("cust_param_inv", features)
        assert result.investor_readiness == expected


# ---------------------------------------------------------------------------
# Context signals tests
# ---------------------------------------------------------------------------


class TestContextSignals:
    def test_context_signals_travel_spike(self):
        """event_type=travel_spike -> 'travel_spike' appears in context_signals."""
        features = make_features(event_type="travel_spike", idle_cash=3000.0)
        result = build_profile("cust_ctx_travel_001", features)
        assert "travel_spike" in result.context_signals

    def test_context_signals_idle_cash_high(self):
        """idle_cash > 10000 -> 'idle_cash_high' in context_signals."""
        features = make_features(idle_cash=12000.0, monthly_savings=600.0)
        result = build_profile("cust_ctx_cash_001", features)
        assert "idle_cash_high" in result.context_signals

    def test_context_signals_idle_cash_not_flagged_when_low(self):
        """idle_cash <= 10000 -> 'idle_cash_high' NOT in context_signals."""
        features = make_features(idle_cash=5000.0)
        result = build_profile("cust_ctx_cash_002", features)
        assert "idle_cash_high" not in result.context_signals

    def test_context_signals_is_list(self):
        """context_signals must be a list."""
        features = make_features()
        result = build_profile("cust_ctx_type_001", features)
        assert isinstance(result.context_signals, list)

    def test_context_signals_salary_increase(self):
        """event_type=salary_increase -> 'salary_increase' in context_signals."""
        features = make_features(event_type="salary_increase", idle_cash=6000.0)
        result = build_profile("cust_ctx_salary_001", features)
        assert "salary_increase" in result.context_signals

    @pytest.mark.parametrize(
        "event_type,idle_cash,expected_signal",
        [
            ("travel_spike",    3000.0,  "travel_spike"),
            ("salary_increase", 4000.0,  "salary_increase"),
            ("bonus_received",  5000.0,  "bonus_received"),
            (None,             11000.0,  "idle_cash_high"),
        ],
    )
    def test_context_signals_parametrized(self, event_type, idle_cash, expected_signal):
        features = make_features(event_type=event_type, idle_cash=idle_cash)
        result = build_profile("cust_ctx_param", features)
        assert expected_signal in result.context_signals


# ---------------------------------------------------------------------------
# Life stage tests
# ---------------------------------------------------------------------------


class TestLifeStage:
    def test_life_stage_young_family(self):
        """Age 30, dependents 2 -> young_family."""
        features = make_features(age=30, dependents=2, married=True)
        result = build_profile("cust_ls_yfam_001", features)
        assert result.life_stage == "young_family"

    def test_life_stage_retired(self):
        """Age 68 -> retired."""
        features = make_features(age=68, employment_status="retired")
        result = build_profile("cust_ls_ret_001", features)
        assert result.life_stage == "retired"

    def test_life_stage_new_graduate(self):
        """Age 22, no dependents, employed -> new_graduate."""
        features = make_features(age=22, dependents=0, monthly_income=3200.0)
        result = build_profile("cust_ls_grad_001", features)
        assert result.life_stage == "new_graduate"

    def test_life_stage_mid_career(self):
        """Age 42, dependents 1 -> mid_career."""
        features = make_features(age=42, dependents=1, monthly_income=7000.0)
        result = build_profile("cust_ls_mid_001", features)
        assert result.life_stage == "mid_career"

    def test_life_stage_pre_retirement(self):
        """Age 55 -> pre_retirement."""
        features = make_features(age=55, monthly_income=7500.0)
        result = build_profile("cust_ls_preretire_001", features)
        assert result.life_stage == "pre_retirement"

    @pytest.mark.parametrize(
        "age,dependents,employment_status,expected_stage",
        [
            (22, 0, "employed",  "new_graduate"),
            (30, 2, "employed",  "young_family"),
            (42, 1, "employed",  "mid_career"),
            (55, 0, "employed",  "pre_retirement"),
            (68, 0, "retired",   "retired"),
        ],
    )
    def test_life_stage_parametrized(self, age, dependents, employment_status, expected_stage):
        features = make_features(
            age=age,
            dependents=dependents,
            employment_status=employment_status,
        )
        result = build_profile("cust_ls_param", features)
        assert result.life_stage == expected_stage


# ---------------------------------------------------------------------------
# Risk bucket tests
# ---------------------------------------------------------------------------


class TestRiskBucket:
    @pytest.mark.parametrize(
        "risk_profile,expected_bucket",
        [
            ("low",    "low"),
            ("medium", "medium"),
            ("high",   "high"),
        ],
    )
    def test_risk_bucket_mapping(self, risk_profile, expected_bucket):
        """risk_profile field maps directly to risk_bucket on the result."""
        features = make_features(risk_profile=risk_profile)
        result = build_profile("cust_rb_param", features)
        assert result.risk_bucket == expected_bucket

    def test_risk_score_in_valid_range(self):
        """risk_score must be a numeric value in [0, 10]."""
        features = make_features()
        result = build_profile("cust_rb_range_001", features)
        assert isinstance(result.risk_score, (int, float))
        assert 0.0 <= result.risk_score <= 10.0

    def test_risk_score_low_for_low_risk_profile(self):
        """Low-risk customers should have lower risk scores than high-risk."""
        low_features = make_features(risk_profile="low", age=62, monthly_income=4000.0)
        high_features = make_features(risk_profile="high", age=28, monthly_income=7000.0)
        low_result = build_profile("cust_rb_low", low_features)
        high_result = build_profile("cust_rb_high", high_features)
        assert low_result.risk_score < high_result.risk_score


# ---------------------------------------------------------------------------
# Family context tests
# ---------------------------------------------------------------------------


class TestFamilyContext:
    def test_family_context_married_true(self):
        """married=True -> family_context=True."""
        features = make_features(married=True, dependents=0)
        result = build_profile("cust_fc_married_001", features)
        assert result.family_context is True

    def test_family_context_with_dependents(self):
        """Dependents > 0 -> family_context=True."""
        features = make_features(married=False, dependents=2)
        result = build_profile("cust_fc_deps_001", features)
        assert result.family_context is True

    def test_family_context_single_no_dependents(self):
        """married=False, dependents=0 -> family_context=False."""
        features = make_features(married=False, dependents=0)
        result = build_profile("cust_fc_single_001", features)
        assert result.family_context is False

    @pytest.mark.parametrize(
        "married,dependents,expected",
        [
            (True,  0, True),
            (False, 2, True),
            (True,  3, True),
            (False, 0, False),
        ],
    )
    def test_family_context_parametrized(self, married, dependents, expected):
        features = make_features(married=married, dependents=dependents)
        result = build_profile("cust_fc_param", features)
        assert result.family_context == expected


# ---------------------------------------------------------------------------
# ProfileResult structure tests
# ---------------------------------------------------------------------------


class TestProfileResultStructure:
    def test_profile_has_customer_id(self):
        result = build_profile("cust_struct_001", make_features())
        assert result.customer_id == "cust_struct_001"

    def test_profile_has_all_required_fields(self):
        result = build_profile("cust_struct_002", make_features())
        required_fields = [
            "customer_id",
            "life_stage",
            "risk_score",
            "financial_health",
            "lifestyle_segment",
            "investor_readiness",
            "risk_bucket",
            "context_signals",
            "family_context",
        ]
        for field in required_fields:
            assert hasattr(result, field), f"Missing field: {field}"

    def test_financial_health_is_valid_enum(self):
        result = build_profile("cust_struct_003", make_features())
        assert result.financial_health in {"healthy", "watchlist", "fragile"}

    def test_investor_readiness_is_valid_enum(self):
        result = build_profile("cust_struct_004", make_features())
        assert result.investor_readiness in {"high", "medium", "low"}

    def test_life_stage_is_valid_enum(self):
        result = build_profile("cust_struct_005", make_features())
        valid_stages = {"new_graduate", "young_family", "mid_career", "pre_retirement", "retired"}
        assert result.life_stage in valid_stages

    def test_risk_bucket_is_valid_enum(self):
        result = build_profile("cust_struct_006", make_features())
        assert result.risk_bucket in {"low", "medium", "high"}

    def test_lifestyle_segment_is_string(self):
        result = build_profile("cust_struct_007", make_features())
        assert isinstance(result.lifestyle_segment, str)
        assert len(result.lifestyle_segment) > 0

    def test_context_signals_list_type(self):
        result = build_profile("cust_struct_008", make_features())
        assert isinstance(result.context_signals, list)

    def test_family_context_is_bool(self):
        result = build_profile("cust_struct_009", make_features())
        assert isinstance(result.family_context, bool)

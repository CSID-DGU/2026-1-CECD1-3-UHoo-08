from agents.score_agent import budget_scorer


class TestBudgetScorer:
    def test_within_tolerance_returns_100(self):
        assert budget_scorer.compute(30000, 30000, 10) == 100
        assert budget_scorer.compute(31000, 30000, 10) == 100  # ~3.3%

    def test_double_tolerance_returns_0(self):
        # tolerance 10% → 20% 초과 이상이면 0
        assert budget_scorer.compute(36000, 30000, 10) == 0
        assert budget_scorer.compute(40000, 30000, 10) == 0

    def test_between_tolerance_linear(self):
        # 15% 초과 (tol 10% × 1.5) → 50점
        score = budget_scorer.compute(34500, 30000, 10)
        assert 40 <= score <= 60

    def test_no_target_returns_neutral(self):
        assert budget_scorer.compute(30000, None, 10) == 50

    def test_no_tolerance_returns_100(self):
        assert budget_scorer.compute(99999, 30000, None) == 100

    def test_zero_tolerance_strict(self):
        assert budget_scorer.compute(30000, 30000, 1) == 100
        assert budget_scorer.compute(30100, 30000, 1) == 100
        assert budget_scorer.compute(31000, 30000, 1) == 0   # 3.3% 차이, tol*2=2% 초과 → 0
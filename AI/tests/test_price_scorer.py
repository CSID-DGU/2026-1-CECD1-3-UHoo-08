from agents.score_agent import price_scorer


class TestPriceScorer:
    def test_no_discount_returns_50(self):
        assert price_scorer.compute(30000, 30000) == 50

    def test_high_discount_returns_100(self):
        # 60% 할인
        assert price_scorer.compute(12000, 30000) == 100

    def test_partial_discount_linear(self):
        # 20% 할인 → 0.2 × 100 + 50 = 70
        assert price_scorer.compute(24000, 30000) == 70

    def test_no_data_returns_neutral(self):
        assert price_scorer.compute(None, 30000) == 50
        assert price_scorer.compute(30000, None) == 50
        assert price_scorer.compute(30000, 0) == 50

    def test_higher_than_original_returns_50(self):
        assert price_scorer.compute(40000, 30000) == 50
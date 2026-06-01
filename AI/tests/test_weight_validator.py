"""weight_validator 단위 테스트."""
from services.weight_validator import DEFAULT_WEIGHTS, validate_and_normalize


class TestWeightValidator:
    def test_valid_input_normalized(self):
        raw = {
            "budget_fit": 0.4,
            "price_value": 0.2,
            "review_score": 0.2,
            "personalization": 0.2,
        }
        w = validate_and_normalize(raw)
        assert abs(sum(w.values()) - 1.0) < 1e-6
        assert w["budget_fit"] > w["price_value"]

    def test_already_normalized_kept(self):
        raw = dict(DEFAULT_WEIGHTS)
        w = validate_and_normalize(raw)
        for k, v in raw.items():
            assert abs(w[k] - v) < 1e-6

    def test_missing_key_returns_default(self):
        raw = {"budget_fit": 0.5, "price_value": 0.5}
        assert validate_and_normalize(raw) == DEFAULT_WEIGHTS

    def test_out_of_range_returns_default(self):
        raw = {
            "budget_fit": 1.5,
            "price_value": 0.2,
            "review_score": 0.2,
            "personalization": 0.2,
        }
        assert validate_and_normalize(raw) == DEFAULT_WEIGHTS

    def test_negative_returns_default(self):
        raw = {
            "budget_fit": -0.1,
            "price_value": 0.4,
            "review_score": 0.4,
            "personalization": 0.3,
        }
        assert validate_and_normalize(raw) == DEFAULT_WEIGHTS

    def test_non_dict_returns_default(self):
        assert validate_and_normalize(None) == DEFAULT_WEIGHTS
        assert validate_and_normalize("string") == DEFAULT_WEIGHTS

    def test_all_zero_returns_default(self):
        raw = {
            "budget_fit": 0.0,
            "price_value": 0.0,
            "review_score": 0.0,
            "personalization": 0.0,
        }
        assert validate_and_normalize(raw) == DEFAULT_WEIGHTS
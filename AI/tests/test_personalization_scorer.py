from agents.score_agent import personalization_scorer


class TestPersonalizationScorer:
    def test_full_match(self):
        profile = {
            "skin_type": "OILY",
            "personal_color": "SPRING_WARM",
            "skin_concerns": ["SEBUM", "ACNE"],
        }
        feat = {
            "skin_type": "지성",
            "personal_color": "웜톤",
            "skin_concern": ["모공"],  # SEBUM과 매칭
        }
        assert personalization_scorer.compute(profile, feat) == 100

    def test_partial_match(self):
        profile = {
            "skin_type": "OILY",
            "personal_color": "SUMMER_COOL",
            "skin_concerns": ["SEBUM"],
        }
        feat = {
            "skin_type": "지성",  # 매칭
            "personal_color": "웜톤",  # 불일치
            "skin_concern": ["모공"],  # 매칭
        }
        # 3개 중 2개 매칭 → 67
        assert personalization_scorer.compute(profile, feat) == 67

    def test_no_feature_returns_neutral(self):
        profile = {"skin_type": "OILY", "personal_color": None, "skin_concerns": []}
        assert personalization_scorer.compute(profile, None) == 50

    def test_neutral_color_matches_anyone(self):
        profile = {"skin_type": None, "personal_color": "SPRING_WARM", "skin_concerns": []}
        feat = {"personal_color": "뉴트럴"}
        assert personalization_scorer.compute(profile, feat) == 100

    def test_no_overlap_concerns(self):
        profile = {
            "skin_type": "DRY",
            "personal_color": None,
            "skin_concerns": ["WHITENING"],
        }
        feat = {"skin_type": "지성", "skin_concern": ["모공"]}
        # skin_type 불일치, concerns 교집합 없음 → 2개 모두 false → 0
        assert personalization_scorer.compute(profile, feat) == 0
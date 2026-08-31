"""
AS7341 채널 → CIE Lab 변환 테스트.

여기서 확인하는 것은 "숫자가 나온다"가 아니라 **그 숫자를 색으로 믿어도
되는가**다. 변환이 조용히 틀리면 화면에는 그럴듯한 ITA°가 뜨고, 그것이
피부 추이의 근거로 쌓인다.
"""
import math

from db.iot.skin_reader import ita_degree
from services.iot.skin_color import (
    CHANNELS, WHITE_X, WHITE_Y, WHITE_Z, reflectance, to_lab, to_xyz,
)

WHITE = {k: 1000.0 for k in CHANNELS}


def _from_reflectance(values):
    """반사율 목록을 채널값으로. 백색을 1000으로 두었으므로 그대로 곱한다."""
    return {k: values[i] * 1000.0 for i, k in enumerate(CHANNELS)}


class TestWhitePoint:
    def test_matches_d65_within_a_few_percent(self):
        # 여덟 점 적분이 얼마나 거친지 보는 시험.
        # 415~680nm 밖이 잘려 나가므로 표준 D65 백색점과 정확히 같을 수는
        # 없지만, 몇 % 안쪽이어야 색으로 쓸 만하다.
        x = WHITE_X / WHITE_Y * 100
        z = WHITE_Z / WHITE_Y * 100
        assert abs(x - 95.047) < 3.0
        assert abs(z - 108.883) < 3.0

    def test_perfect_white_is_neutral(self):
        # 완전 반사체는 L*=100, a*=b*=0이어야 한다. 이것이 어긋나면
        # 모든 측정이 그만큼 치우친 채로 쌓인다.
        l, a, b = to_lab(WHITE, WHITE)
        assert l == 100.0
        assert abs(a) < 0.01
        assert abs(b) < 0.01

    def test_grey_follows_the_lab_curve(self):
        # 반사율 0.5의 무채색은 L*≈76.07. Lab의 비선형 압축이 맞는지 본다.
        l, a, b = to_lab(_from_reflectance([0.5] * 8), WHITE)
        assert abs(l - 76.07) < 0.1
        assert abs(a) < 0.01 and abs(b) < 0.01


class TestSkinTones:
    """문헌상 전형적인 피부 반사율을 넣어 값의 자리가 맞는지 본다."""

    LIGHT = [0.20, 0.25, 0.32, 0.38, 0.42, 0.55, 0.62, 0.65]
    DARK = [0.05, 0.06, 0.08, 0.10, 0.12, 0.17, 0.22, 0.27]

    def test_light_skin_lands_in_the_expected_range(self):
        l, a, b = to_lab(_from_reflectance(self.LIGHT), WHITE)
        # 밝은 피부는 대략 L* 65~80, a* 5~15, b* 15~30에 들어온다.
        assert 65 < l < 80
        assert 5 < a < 15
        assert 15 < b < 30

    def test_darker_skin_has_lower_lightness(self):
        light = to_lab(_from_reflectance(self.LIGHT), WHITE)
        dark = to_lab(_from_reflectance(self.DARK), WHITE)
        assert dark[0] < light[0] - 20

    def test_ita_orders_the_two(self):
        # ITA°는 밝을수록 크다. 이 순서가 뒤집히면 화면의 분류가 통째로 틀린다.
        light = to_lab(_from_reflectance(self.LIGHT), WHITE)
        dark = to_lab(_from_reflectance(self.DARK), WHITE)
        assert ita_degree(light[0], light[2]) > ita_degree(dark[0], dark[2])

    def test_redness_raises_a_star(self):
        # 붉은 쪽(F7·F8) 반사율만 올리면 a*가 커져야 한다. 홍반 지수가
        # a*를 그대로 쓰므로, 이 방향이 틀리면 붉은기를 거꾸로 읽는다.
        base = list(self.LIGHT)
        red = list(self.LIGHT)
        red[6] += 0.08
        red[7] += 0.08
        assert to_lab(_from_reflectance(red), WHITE)[1] > \
               to_lab(_from_reflectance(base), WHITE)[1]


class TestGuards:
    def test_without_white_reference_there_is_no_colour(self):
        # 백색 기준 없이 채널값만으로 색을 말할 수 없다. 조명 밝기가
        # 그대로 피부색이 되어 버린다.
        assert to_lab(_from_reflectance([0.4] * 8), None) is None
        assert to_xyz(_from_reflectance([0.4] * 8), {}) is None

    def test_missing_channel_is_refused(self):
        partial = _from_reflectance([0.4] * 8)
        del partial["F5"]
        assert to_lab(partial, WHITE) is None

    def test_zero_white_is_refused(self):
        # 백색 기준이 0이면 나눌 수 없다. 예외 대신 None으로 막는다.
        assert to_lab(_from_reflectance([0.4] * 8), dict(WHITE, F3=0.0)) is None

    def test_specular_highlight_is_clamped(self):
        # 번들거리면 백색 표준판보다 밝게 잡힌다. 자르지 않으면 L*이
        # 100을 크게 넘어 ITA°가 터무니없이 커진다.
        r = reflectance({k: 9000.0 for k in CHANNELS}, WHITE)
        assert all(v <= 1.5 for v in r)
        assert not math.isnan(to_lab({k: 9000.0 for k in CHANNELS}, WHITE)[0])

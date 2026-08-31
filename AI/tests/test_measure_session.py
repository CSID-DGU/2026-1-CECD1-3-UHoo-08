"""
측정 세션 라우터 테스트.

DB 없이 세션의 상태 전이만 확인한다. 여기서 잡으려는 것은 계산이 아니라
순서다. 백색 없이 시료가 들어오거나, 게인이 바뀐 채로 두 값이 합쳐지거나,
포화한 측정이 결과로 굳어지는 것은 전부 화면에 정상처럼 보이면서 틀린
숫자를 남긴다.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from config import settings

USER = "aa000000-0000-0000-0000-000000000001"
UPID = "bb000000-0000-0000-0000-000000000002"
SID = "cc000000-0000-0000-0000-000000000003"
NODE = "measure-01"

WHITE = {"F1": 18000.0, "F2": 21000.0, "F3": 24000.0, "F4": 26000.0,
         "F5": 27000.0, "F6": 26000.0, "F7": 25000.0, "F8": 23000.0,
         "CLEAR": 52000.0, "NIR": 16000.0}
SAMPLE = {k: v * 0.8 for k, v in WHITE.items()}


def _client():
    from fastapi import FastAPI
    from api.care.router import router as care_router
    from api.iot.router import router as iot_router

    app = FastAPI()
    app.include_router(iot_router)
    app.include_router(care_router)
    return TestClient(app)


def _session(status="waiting_white", **over):
    row = {
        "id": SID,
        "node_id": NODE,
        "user_id": USER,
        "target": "product",
        "user_product_id": UPID,
        "site": None,
        "status": status,
        "white_ref": None,
        "channels": None,
        "meta": None,
        "saturated": False,
        "baseline": None,
        "delta_pct": None,
        "message": None,
        "expires_at": (datetime.now(timezone.utc)
                       + timedelta(seconds=300)).isoformat(),
    }
    row.update(over)
    return row


def _sample_body(step, channels, **over):
    body = {
        "node_id": NODE,
        "step": step,
        "ts": datetime.now(timezone.utc).isoformat(),
        "channels": channels,
        "saturated": False,
        "gain": "64x",
        "led_ma": 10,
        "dark_applied": True,
        "fw": "test",
    }
    body.update(over)
    return body


def _headers():
    # IOT_API_KEY가 설정된 환경에서도 돌아야 한다.
    return {"X-Node-Key": settings.IOT_API_KEY} if settings.IOT_API_KEY else {}


class TestStartSession:
    @patch("api.care.router.get_optical_baseline", return_value=None)
    @patch("api.care.router.create_measure_session")
    @patch("api.care.router.list_nodes")
    @patch("api.care.router.get_care_products")
    def test_opens_waiting_white(self, products, nodes, create, _base):
        products.return_value = [
            {"user_product_id": UPID, "optical_grade": "suitable"}]
        nodes.return_value = [
            {"node_id": NODE, "user_id": USER, "node_type": "measure",
             "location_label": "휴대형"}]
        create.return_value = _session()

        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"user_product_id": UPID})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "waiting_white"
        assert data["step"] == "white"
        assert data["has_baseline"] is False
        assert data["node_label"] == "휴대형"

    @patch("api.care.router.list_nodes")
    @patch("api.care.router.get_care_products")
    def test_rejects_unsuitable_formulation(self, products, nodes):
        # 투명한 제형은 재봐야 조명 잡음만 남는다. 노드를 부르기 전에 끊는다.
        products.return_value = [
            {"user_product_id": UPID, "optical_grade": "unsuitable"}]
        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"user_product_id": UPID})
        assert res.status_code == 422
        nodes.assert_not_called()

    @patch("api.care.router.list_nodes", return_value=[])
    @patch("api.care.router.get_care_products")
    def test_without_measure_node(self, products, _nodes):
        products.return_value = [
            {"user_product_id": UPID, "optical_grade": "suitable"}]
        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"user_product_id": UPID})
        assert res.status_code == 409

    @patch("api.care.router.get_care_products", return_value=[])
    def test_other_users_product(self, _products):
        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"user_product_id": UPID})
        assert res.status_code == 404


class TestNodePolling:
    @patch("api.iot.router.get_open_measure_session")
    @patch("api.iot.router.get_node")
    def test_returns_step_once_armed(self, node, session):
        node.return_value = {"node_id": NODE, "user_id": USER,
                             "node_type": "measure", "location_label": None}
        session.return_value = _session("capturing_sample")

        res = _client().get(f"/api/iot/nodes/{NODE}/session", headers=_headers())
        assert res.status_code == 200
        assert res.json()["step"] == "sample"

    @patch("api.iot.router.get_open_measure_session")
    @patch("api.iot.router.get_node")
    def test_no_step_before_user_taps(self, node, session):
        # 세션은 열려 있지만 사용자가 아직 시료를 올려놓는 중이다.
        # 여기서 재면 아무것도 없는 측정부를 잰다.
        node.return_value = {"node_id": NODE, "user_id": USER,
                             "node_type": "measure", "location_label": None}
        session.return_value = _session("waiting_white")

        res = _client().get(f"/api/iot/nodes/{NODE}/session", headers=_headers())
        assert res.status_code == 200
        assert res.json()["step"] is None
        assert res.json()["session_id"] == SID

    @patch("api.iot.router.get_open_measure_session", return_value=None)
    @patch("api.iot.router.get_node")
    def test_idle_without_session(self, node, _session):
        node.return_value = {"node_id": NODE, "user_id": USER,
                             "node_type": "measure", "location_label": None}
        res = _client().get(f"/api/iot/nodes/{NODE}/session", headers=_headers())
        assert res.status_code == 200
        assert res.json()["status"] == "idle"
        assert res.json()["session_id"] is None

    @patch("api.iot.router.get_node")
    def test_environment_node_is_not_a_measure_node(self, node):
        node.return_value = {"node_id": "storage-01", "user_id": USER,
                             "node_type": "storage", "location_label": None}
        res = _client().get("/api/iot/nodes/storage-01/session",
                            headers=_headers())
        assert res.status_code == 400


class TestSampleUpload:
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_white_advances_to_sample(self, get, update):
        get.return_value = _session("capturing_white")
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", WHITE),
                             headers=_headers())
        assert res.status_code == 200
        assert res.json()["next_step"] == "sample"
        patch_arg = update.call_args[0][1]
        assert patch_arg["status"] == "waiting_sample"
        assert patch_arg["white_ref"] == WHITE

    @patch("api.iot.router.insert_optical")
    @patch("api.iot.router.get_optical_baseline", return_value=None)
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_first_sample_becomes_baseline(self, get, update, _base, insert):
        get.return_value = _session(
            "capturing_sample", white_ref=WHITE,
            meta={"gain": "64x", "led_ma": 10})

        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", SAMPLE),
                             headers=_headers())
        assert res.status_code == 200
        assert res.json()["status"] == "done"

        insert.assert_called_once()
        # 기준값이면 변화율을 남기지 않는다. 비교 대상이 없다.
        assert insert.call_args[0][3] is None
        patch_arg = update.call_args[0][1]
        assert patch_arg["baseline"] is True
        assert patch_arg["delta_pct"] is None

    @patch("api.iot.router.insert_optical")
    @patch("api.iot.router.get_optical_baseline")
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_second_sample_reports_change(self, get, update, base, _insert):
        get.return_value = _session(
            "capturing_sample", white_ref=WHITE,
            meta={"gain": "64x", "led_ma": 10})
        base.return_value = {"channels": SAMPLE, "white_ref": WHITE}

        # 파란 쪽만 10% 떨어뜨린다. 누레지는 변화의 모양이다.
        now = dict(SAMPLE)
        for k in ("F1", "F2", "F3", "F4"):
            now[k] *= 0.90

        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", now),
                             headers=_headers())
        assert res.status_code == 200
        delta = update.call_args[0][1]["delta_pct"]
        # 여덟 채널 중 넷이 10% 변했으므로 평균 5% 언저리
        assert 4.5 < delta < 5.5

    @patch("api.iot.router.get_measure_session")
    def test_sample_before_white_is_rejected(self, get):
        get.return_value = _session("capturing_white")
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", SAMPLE),
                             headers=_headers())
        assert res.status_code == 409

    @patch("api.iot.router.get_measure_session")
    def test_measurement_without_a_tap_is_rejected(self, get):
        # 사용자가 누르기 전에 올라온 값은 요청한 측정이 아니다.
        get.return_value = _session("waiting_white")
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", WHITE),
                             headers=_headers())
        assert res.status_code == 409

    @patch("api.iot.router.get_measure_session")
    def test_another_node_cannot_fill_the_session(self, get):
        get.return_value = _session("capturing_white")
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", WHITE,
                                               node_id="measure-99"),
                             headers=_headers())
        assert res.status_code == 403

    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_saturated_measurement_fails_the_session(self, get, update):
        get.return_value = _session("capturing_white")
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", WHITE, saturated=True),
                             headers=_headers())
        assert res.status_code == 200
        assert res.json()["status"] == "failed"
        assert update.call_args[0][1]["status"] == "failed"

    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_missing_channels_fail_the_session(self, get, update):
        get.return_value = _session("capturing_white")
        partial = {k: v for k, v in WHITE.items() if k not in ("F3", "F4")}
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", partial),
                             headers=_headers())
        assert res.status_code == 200
        assert res.json()["status"] == "failed"
        assert "F3" in update.call_args[0][1]["message"]

    @patch("api.iot.router.insert_optical")
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_gain_change_between_steps_fails(self, get, update, insert):
        # 게인이 다르면 두 값의 축척이 달라 시료/백색이 반사율이 아니게 된다.
        get.return_value = _session(
            "capturing_sample", white_ref=WHITE,
            meta={"gain": "64x", "led_ma": 10})
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", SAMPLE, gain="32x"),
                             headers=_headers())
        assert res.status_code == 200
        assert res.json()["status"] == "failed"
        insert.assert_not_called()

    @patch("api.iot.router.get_measure_session")
    def test_unsynced_clock_is_rejected(self, get):
        get.return_value = _session("capturing_white")
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", WHITE,
                                               ts="1970-01-01T00:00:00Z"),
                             headers=_headers())
        assert res.status_code == 422

    @patch("api.iot.router.get_measure_session", return_value=None)
    def test_unknown_session(self, _get):
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("white", WHITE),
                             headers=_headers())
        assert res.status_code == 404


class TestCapture:
    """사용자가 "측정"을 누르는 자리."""

    @patch("api.care.router.update_measure_session")
    @patch("api.care.router.get_measure_session")
    def test_tap_arms_the_node(self, get, update):
        get.return_value = _session("waiting_white")
        update.return_value = _session("capturing_white")

        res = _client().post(f"/api/care/measure/sessions/{SID}/capture",
                             params={"user_id": USER})
        assert res.status_code == 200
        assert update.call_args[0][1]["status"] == "capturing_white"
        data = res.json()
        assert data["capturing"] is True
        assert data["step"] == "white"

    @patch("api.care.router.update_measure_session")
    @patch("api.care.router.get_measure_session")
    def test_double_tap_does_not_restart(self, get, update):
        # 이미 재는 중인 측정을 화면 두 번 눌렀다고 취소하거나 두 번 재면 안 된다.
        get.return_value = _session("capturing_white")
        res = _client().post(f"/api/care/measure/sessions/{SID}/capture",
                             params={"user_id": USER})
        assert res.status_code == 200
        update.assert_not_called()

    @patch("api.care.router.get_measure_session")
    def test_cannot_tap_a_finished_session(self, get):
        get.return_value = _session("done", delta_pct=3.2)
        res = _client().post(f"/api/care/measure/sessions/{SID}/capture",
                             params={"user_id": USER})
        assert res.status_code == 409


class TestKioskPolling:
    @patch("api.care.router.get_measure_session")
    def test_shows_result_when_done(self, get):
        get.return_value = _session("done", baseline=False, delta_pct=6.4,
                                    message="처음 잰 색과 6.4% 다릅니다.")
        res = _client().get(f"/api/care/measure/sessions/{SID}",
                            params={"user_id": USER})
        assert res.status_code == 200
        data = res.json()
        assert data["delta_pct"] == 6.4
        assert data["step"] is None
        assert "6.4%" in data["message"]

    @patch("api.care.router.get_measure_session")
    def test_waiting_state_asks_for_a_tap(self, get):
        get.return_value = _session("waiting_sample")
        res = _client().get(f"/api/care/measure/sessions/{SID}",
                            params={"user_id": USER})
        data = res.json()
        assert data["step"] == "sample"
        assert data["awaiting_tap"] is True
        assert data["capturing"] is False

    @patch("api.care.router.get_measure_session")
    def test_other_users_session_is_not_visible(self, get):
        get.return_value = _session(user_id="dd000000-0000-0000-0000-000000000004")
        res = _client().get(f"/api/care/measure/sessions/{SID}",
                            params={"user_id": USER})
        assert res.status_code == 404

    @patch("api.care.router.update_measure_session")
    @patch("api.care.router.get_measure_session")
    def test_cancel_closes_open_session(self, get, update):
        get.return_value = _session("waiting_sample")
        res = _client().delete(f"/api/care/measure/sessions/{SID}",
                               params={"user_id": USER})
        assert res.status_code == 204
        assert update.call_args[0][1]["status"] == "cancelled"

    @patch("api.care.router.update_measure_session")
    @patch("api.care.router.get_measure_session")
    def test_cancel_leaves_finished_session_alone(self, get, update):
        # 끝난 측정의 결과를 취소로 덮어쓰면 안 된다.
        get.return_value = _session("done", delta_pct=3.2)
        res = _client().delete(f"/api/care/measure/sessions/{SID}",
                               params={"user_id": USER})
        assert res.status_code == 204
        update.assert_not_called()


# ── 피부 측정 ────────────────────────────────────────────────────

SKIN_SITE = "손등 안쪽"

# 밝은 피부에 가까운 반사율. 백색을 1000으로 두고 그 비율로 만든다.
SKIN_SAMPLE = {"F1": 200.0, "F2": 250.0, "F3": 320.0, "F4": 380.0,
               "F5": 420.0, "F6": 550.0, "F7": 620.0, "F8": 650.0,
               "CLEAR": 430.0, "NIR": 700.0}
SKIN_WHITE = {k: 1000.0 for k in SKIN_SAMPLE}


def _skin_session(status="capturing_sample", **over):
    return _session(status, target="skin", user_product_id=None,
                    site=SKIN_SITE, **over)


class TestStartSkinSession:
    @patch("api.care.router.count_site_measurements", return_value=0)
    @patch("api.care.router.create_measure_session")
    @patch("api.care.router.list_nodes")
    def test_opens_with_a_site(self, nodes, create, _count):
        nodes.return_value = [
            {"node_id": NODE, "user_id": USER, "node_type": "measure",
             "location_label": "휴대형"}]
        create.return_value = _skin_session("waiting_white")

        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"target": "skin", "site": SKIN_SITE})
        assert res.status_code == 200
        data = res.json()
        assert data["target"] == "skin"
        assert data["site"] == SKIN_SITE
        assert data["has_baseline"] is False
        assert create.call_args.kwargs["site"] == SKIN_SITE
        # 피부 세션에 제품이 딸려가면 안 된다.
        assert create.call_args.kwargs["user_product_id"] is None

    def test_site_is_required(self):
        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"target": "skin"})
        assert res.status_code == 422

    def test_unknown_site_is_refused(self):
        # 목록 밖 값을 받으면 "손등"과 "손등 안쪽"이 따로 쌓여 추이가 갈린다.
        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"target": "skin", "site": "손등"})
        assert res.status_code == 422

    @patch("api.care.router.get_care_products", return_value=[])
    def test_product_target_still_needs_a_product(self, _products):
        res = _client().post("/api/care/measure/sessions",
                             params={"user_id": USER},
                             json={"target": "product"})
        assert res.status_code == 422


class TestSkinUpload:
    @patch("api.iot.router.count_site_measurements", return_value=0)
    @patch("api.iot.router.insert_skin_measurement")
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_first_measurement_is_a_baseline(self, get, update, insert, _count):
        get.return_value = _skin_session(white_ref=SKIN_WHITE,
                                         meta={"gain": "64x", "led_ma": 10})

        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", SKIN_SAMPLE),
                             headers=_headers())
        assert res.status_code == 200
        assert res.json()["status"] == "done"

        # 첫 측정은 비교 대상이 없다. 변화량을 말하면 안 된다.
        patch_arg = update.call_args[0][1]
        assert patch_arg["baseline"] is True
        assert "기준선" in patch_arg["message"]

        lab = insert.call_args[0][1]
        assert 65 < lab[0] < 80          # 밝은 피부의 L*
        assert insert.call_args.kwargs["site"] == SKIN_SITE

    @patch("api.iot.router.count_site_measurements", return_value=3)
    @patch("api.iot.router.insert_skin_measurement")
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_later_measurement_reports_values(self, get, update, insert, _count):
        get.return_value = _skin_session(white_ref=SKIN_WHITE,
                                         meta={"gain": "64x", "led_ma": 10})
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", SKIN_SAMPLE),
                             headers=_headers())
        assert res.status_code == 200
        patch_arg = update.call_args[0][1]
        assert patch_arg["baseline"] is False
        assert "ITA" in patch_arg["message"]

    @patch("api.iot.router.insert_skin_measurement")
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_without_white_reference_it_fails(self, get, update, insert):
        # 백색 기준 없이는 색으로 옮길 수 없다. 조명 밝기가 그대로
        # 피부색이 되므로, 값을 남기지 않고 세션을 실패로 닫는다.
        get.return_value = _skin_session(white_ref=None,
                                         meta={"gain": "64x", "led_ma": 10})
        res = _client().post(f"/api/iot/sessions/{SID}/samples",
                             json=_sample_body("sample", SKIN_SAMPLE),
                             headers=_headers())
        assert res.json()["status"] == "failed"
        insert.assert_not_called()

    @patch("api.iot.router.insert_skin_measurement")
    @patch("api.iot.router.update_measure_session")
    @patch("api.iot.router.get_measure_session")
    def test_gloss_is_never_stored(self, get, update, insert):
        # AS7341로는 광택을 잴 수 없다. 컬럼이 있다고 채우면 화면이
        # 그것을 근거처럼 보여주게 된다.
        get.return_value = _skin_session(white_ref=SKIN_WHITE,
                                         meta={"gain": "64x", "led_ma": 10})
        with patch("api.iot.router.count_site_measurements", return_value=1):
            _client().post(f"/api/iot/sessions/{SID}/samples",
                           json=_sample_body("sample", SKIN_SAMPLE),
                           headers=_headers())
        assert "gloss" not in insert.call_args.kwargs

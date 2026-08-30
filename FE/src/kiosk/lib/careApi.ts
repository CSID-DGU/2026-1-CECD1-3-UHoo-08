import { kioskDelete, kioskGet, kioskPost, KioskApiError, KIOSK_USER_ID } from "./kioskApi";
import { MOCK_ENABLED, mockClearMeasure, mockFor, mockPostFor } from "./mock";
import type { MeasureSession, MeasureStartResponse } from "./types";

/**
 * 화면이 쓰는 조회 함수.
 *
 * ?mock=1 이면 서버 대신 시드 데이터를 돌려준다. 서버 API가 아직 없는
 * 화면을 만드는 동안 배치와 넘침을 확인하기 위한 것이다.
 *
 * kioskApi.ts를 직접 고치지 않고 감싸는 이유: 목업 모드는 개발 중에만
 * 쓰는 임시 장치라, 실제 통신 코드와 섞이지 않는 편이 지우기 쉽다.
 */
export async function careGet<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<T> {
  if (MOCK_ENABLED) {
    const data = mockFor(path, params);
    if (data === null) {
      throw new KioskApiError("목업 데이터가 없는 경로", path, 404);
    }
    // 실제 응답처럼 약간의 지연을 준다. 로딩 상태가 화면에서 어떻게
    // 보이는지도 함께 확인해야 한다.
    await new Promise((r) => setTimeout(r, 250));
    return data as T;
  }
  return kioskGet<T>(path, params);
}

export { MOCK_ENABLED };

/**
 * POST 요청.
 *
 * 목업 모드에서는 서버에 보내지 않고 그럴듯한 응답을 만들어 돌려준다.
 * 화면 흐름을 확인하는 것이 목적이라 실제 저장은 필요 없다.
 */
export async function carePost<T>(
  path: string,
  body: unknown,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<T> {
  if (MOCK_ENABLED) {
    const data = mockPostFor(path, body);
    if (data === null) {
      throw new KioskApiError("목업 응답이 없는 경로", path, 404);
    }
    await new Promise((r) => setTimeout(r, 250));
    return data as T;
  }
  return kioskPost<T>(path, body, params);
}
/**
 * DELETE 요청. 목업 모드에서는 서버에 보내지 않고 상태만 지운다.
 */
export async function careDelete(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<void> {
  if (MOCK_ENABLED) {
    mockClearMeasure();
    await new Promise((r) => setTimeout(r, 150));
    return;
  }
  return kioskDelete(path, params);
}

// ── 측정 세션 ────────────────────────────────────────────────
//
// 네 호출이 한 번의 측정을 이룬다.
//
//   start   측정 노드에 이 제품을 재라고 알린다
//   capture "올려놓았으니 재세요" — 백색 표준판과 제품에 한 번씩, 두 번
//   status  노드가 채워 넣는 동안 짧은 간격으로 본다
//   cancel  도중에 나갈 때. 닫지 않으면 노드가 시한까지 세션을 붙들고 있다

const MEASURE_BASE = "/api/care/measure/sessions";

export const measureApi = {
  start: (userProductId: string) =>
    carePost<MeasureStartResponse>(
      MEASURE_BASE,
      { user_product_id: userProductId },
      { user_id: KIOSK_USER_ID }
    ),

  capture: (sessionId: string) =>
    carePost<MeasureSession>(
      `${MEASURE_BASE}/${sessionId}/capture`,
      {},
      { user_id: KIOSK_USER_ID }
    ),

  status: (sessionId: string) =>
    careGet<MeasureSession>(`${MEASURE_BASE}/${sessionId}`, {
      user_id: KIOSK_USER_ID,
    }),

  cancel: (sessionId: string) =>
    careDelete(`${MEASURE_BASE}/${sessionId}`, { user_id: KIOSK_USER_ID }),
};

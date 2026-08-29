import { kioskGet, kioskPost, KioskApiError } from "./kioskApi";
import { MOCK_ENABLED, mockFor, mockPostFor } from "./mock";

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
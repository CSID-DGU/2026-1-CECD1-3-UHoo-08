import type { MissingInfo } from "../../api/myProductApi";

/**
 * 사용자가 직접 채울 수 있는 항목인지.
 *
 * 성분 민감도(has_profile)와 개봉 후 사용기간(pao_months)은 제품 자체의
 * 성질이라 사용자가 넣을 곳이 없다. 그것까지 "미등록"이라고 띄우면 어디서
 * 고치라는 건지 알 수 없는 안내가 된다.
 */
export function isUserFixable(m: MissingInfo) {
  return m.field === "opened_at" || m.field === "storage_node_id";
}

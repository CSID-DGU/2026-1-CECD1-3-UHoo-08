/**
 * 개봉일 입력값 변환.
 *
 * 컴포넌트 파일에서 분리했다. React Fast Refresh는 컴포넌트만 export하는
 * 파일에서 동작하는데, 순수 함수를 같이 두면 그게 깨진다.
 */
/**
 * 입력값을 서버가 받는 형태로 만든다.
 *
 * 일이 없으면 "YYYY-MM"으로 보낸다. 화면에서 임의로 1일을 채우지 않는다.
 * 어떻게 추정할지는 서버가 정할 일이고, 그래야 추정했다는 사실도 서버가
 * 함께 알려줄 수 있다.
 */
export function toOpenedAt(
  year: string,
  month: string,
  day: string,
): string | null {
  const y = Number(year);
  const m = Number(month);
  if (!y || y < 1900 || y > 2999) return null;
  if (!m || m < 1 || m > 12) return null;

  const head = `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}`;
  if (!day) return head;

  const d = Number(day);
  if (!d || d < 1 || d > 31) return null;
  return `${head}-${String(d).padStart(2, "0")}`;
}

/** "2025-03-15" → {year:"2025", month:"3", day:"15"} */
export function fromOpenedAt(value: string | null) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? "");
  if (!m) return { year: "", month: "", day: "" };
  return { year: m[1], month: String(Number(m[2])), day: String(Number(m[3])) };
}

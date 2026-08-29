/**
 * 개봉일 입력.
 *
 * 캘린더를 쓰지 않는다. 몇 달 전 날짜를 고르려면 달을 여러 번 넘겨야 하고
 * 화면도 무거워진다. 숫자를 직접 치는 편이 빠르다.
 *
 * 일(day)은 선택이다. 개봉일을 정확히 기억하는 사람은 많지 않은데 그걸
 * 강제하면 아무 날짜나 넣게 된다. 비워두면 서버가 월 중간으로 잡는다.
 */
export function OpenedDateInput({
  year,
  month,
  day,
  onChange,
}: {
  year: string;
  month: string;
  day: string;
  onChange: (next: { year: string; month: string; day: string }) => void;
}) {
  const box =
    "h-[48px] rounded-2xl border border-gray-100 bg-white text-center text-body2 text-gray-500 outline-none focus:border-primary-300";

  // 숫자만 남긴다. 문자가 섞여 들어오면 서버까지 가서야 걸린다.
  const digits = (v: string, max: number) => v.replace(/\D/g, "").slice(0, max);

  return (
    <div className="flex items-center gap-2">
      <input
        className={`${box} w-[84px]`}
        inputMode="numeric"
        placeholder="2026"
        value={year}
        onChange={(e) => onChange({ year: digits(e.target.value, 4), month, day })}
      />
      <span className="text-caption text-gray-300">년</span>

      <input
        className={`${box} w-[62px]`}
        inputMode="numeric"
        placeholder="3"
        value={month}
        onChange={(e) => onChange({ year, month: digits(e.target.value, 2), day })}
      />
      <span className="text-caption text-gray-300">월</span>

      <input
        className={`${box} w-[62px]`}
        inputMode="numeric"
        placeholder="선택"
        value={day}
        onChange={(e) => onChange({ year, month, day: digits(e.target.value, 2) })}
      />
      <span className="text-caption text-gray-300">일</span>
    </div>
  );
}

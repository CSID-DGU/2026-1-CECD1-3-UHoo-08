import { useEffect, useState, type ReactNode } from "react";

/**
 * 화면을 꽉 채우는 프레임.
 *
 * ── 처음 방식과 무엇이 다른가 ────────────────────────────────
 * 처음에는 1024×600을 통째로 고정하고 min(가로배율, 세로배율)로 확대했다.
 * 그러면 아이패드(1194×802)에서 1194×700이 되고 위아래로 102px이 남는다.
 * 문제는 남는 것이 화면 여백일 뿐, **콘텐츠는 여전히 600px 안에 갇힌다**는
 * 점이다. 실제로 점검 탭에서 세 번째 카드가 잘리고 버튼이 붙어버렸다.
 *
 * 그래서 가로만 1024로 고정하고 세로는 화면에 맞춰 늘린다.
 *
 *   배율     = 1194 / 1024 = 1.166
 *   논리 높이 =  802 / 1.166 = 688
 *   결과     = 1024×688을 1.166배 → 1194×802  (정확히 일치)
 *
 * 가로세로를 따로 늘리면(scaleX ≠ scaleY) 글자가 15% 세로로 늘어나 보인다.
 * 여기서는 배율이 하나라 왜곡이 없고, 잘리는 곳도 없다. 늘어난 88px은
 * 본문 영역이 가져간다. 화면들이 flex 세로 배치라 자동으로 채워진다.
 *
 * ── 화면이 아주 납작한 경우 ──────────────────────────────────
 * 가로 기준으로 잡았을 때 논리 높이가 600px보다 작아지면, 목업이 전제한
 * 최소 높이가 무너진다. 그때는 반대로 세로를 600으로 고정하고 가로를
 * 늘린다. 어느 쪽이든 화면은 꽉 찬다.
 */

/** 목업 기준 가로. 이 값을 바꾸면 모든 화면의 글자 크기가 함께 바뀐다. */
const BASE_W = 1024;

/** 목업이 전제한 최소 세로. 이보다 납작해지면 기준을 세로로 바꾼다. */
const MIN_H = 600;

/** 확대 전 잠깐 보이는 배경. 목업 body 색과 같다. */
const BASE_BG = "#2a2d33";

type Layout = { w: number; h: number; scale: number };

function computeLayout(): Layout {
  // visualViewport는 iOS에서 주소창·툴바를 제외한 실제 표시 영역을 준다.
  const vw = window.visualViewport?.width ?? window.innerWidth;
  const vh = window.visualViewport?.height ?? window.innerHeight;

  const scaleByWidth = vw / BASE_W;
  const logicalH = vh / scaleByWidth;

  if (logicalH >= MIN_H) {
    // 보통의 경우. 가로를 기준으로 잡고 세로를 늘린다.
    return { w: BASE_W, h: logicalH, scale: scaleByWidth };
  }

  // 아주 납작한 화면. 세로를 기준으로 잡고 가로를 늘린다.
  const scaleByHeight = vh / MIN_H;
  return { w: vw / scaleByHeight, h: MIN_H, scale: scaleByHeight };
}

export function KioskFrame({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<Layout>(computeLayout);

  useEffect(() => {
    const update = () => setLayout(computeLayout());

    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    window.visualViewport?.addEventListener("resize", update);

    // 홈 화면에서 실행한 직후에는 표시 영역이 한 박자 늦게 확정된다.
    // 회전 직후에도 값이 바로 갱신되지 않아 두 번 확인한다.
    const t1 = window.setTimeout(update, 300);
    const t2 = window.setTimeout(update, 1000);

    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
      window.visualViewport?.removeEventListener("resize", update);
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  return (
    <div className="fixed inset-0 overflow-hidden" style={{ background: BASE_BG }}>
      <div
        style={{
          width: layout.w,
          height: layout.h,
          transform: `scale(${layout.scale})`,
          // 좌상단 기준으로 확대해야 위치 계산이 필요 없다.
          // 가운데 기준이면 확대 후 좌표가 밀려 여백 계산을 따로 해야 한다.
          transformOrigin: "top left",
          willChange: "transform",
        }}
        className="relative overflow-hidden bg-gray-100"
      >
        {children}
      </div>
    </div>
  );
}

/**
 * 목업 기준 크기.
 *
 * 세로는 화면에 따라 늘어나므로 이 값은 "최소 높이"라는 뜻이다.
 * 절대 위치로 무언가를 배치할 때 이 값을 높이로 쓰면 안 된다.
 */
export const KIOSK_FRAME_SIZE = { width: BASE_W, minHeight: MIN_H };
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

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

function computeLayout(host: HTMLElement | null): Layout {
  // 프레임을 감싸는 상자(fixed inset-0)의 실제 크기를 쓴다.
  //
  // 예전에는 visualViewport를 썼는데, viewport-fit=cover로 홈 화면에서
  // 실행하면 이 값이 **홈 인디케이터 영역을 뺀** 높이를 준다. 그 높이로
  // 프레임을 만들면 화면 아래쪽이 프레임 밖으로 남고, 그 자리에 body
  // 배경색(#eceff2)이 그대로 드러난다. 아이패드에서 아래가 잘려 보인
  // 원인이다.
  //
  // 감싸는 상자는 안전영역을 포함한 화면 전체를 차지하므로, 그 크기를
  // 그대로 쓰면 위아래 어디에도 빈 곳이 남지 않는다. host가 아직 없는
  // 첫 렌더에서만 예전 값으로 대체한다.
  const vw = host?.clientWidth || window.visualViewport?.width || window.innerWidth;
  const vh = host?.clientHeight || window.visualViewport?.height || window.innerHeight;

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
  const hostRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<Layout>(() => computeLayout(null));

  useEffect(() => {
    const update = () => setLayout(computeLayout(hostRef.current));

    // 감싸는 상자 자체를 관찰한다. observe 직후 한 번 호출되므로 첫 값도
    // 여기서 잡힌다. 회전·분할 화면처럼 창 이벤트가 안 오는 경우도 덮는다.
    const observer = new ResizeObserver(update);
    if (hostRef.current) observer.observe(hostRef.current);

    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    window.visualViewport?.addEventListener("resize", update);

    // 홈 화면에서 실행한 직후에는 표시 영역이 한 박자 늦게 확정된다.
    // 회전 직후에도 값이 바로 갱신되지 않아 두 번 확인한다.
    const t1 = window.setTimeout(update, 300);
    const t2 = window.setTimeout(update, 1000);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
      window.visualViewport?.removeEventListener("resize", update);
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  return (
    <div ref={hostRef} className="fixed inset-0 overflow-hidden" style={{ background: BASE_BG }}>
      <div
        style={{
          width: layout.w,
          height: layout.h,
          transform: `scale(${layout.scale})`,
          // 안전영역(상태 표시줄·홈 인디케이터)은 실제 화면 픽셀 단위인데,
          // 이 안쪽은 scale배 확대되는 좌표계다. 그대로 쓰면 확대된 만큼
          // 더 밀리므로 배율로 나눠 논리 픽셀로 바꿔 내려보낸다.
          "--kiosk-safe-top": `calc(env(safe-area-inset-top, 0px) / ${layout.scale})`,
          "--kiosk-safe-bottom": `calc(env(safe-area-inset-bottom, 0px) / ${layout.scale})`,
          // 좌상단 기준으로 확대해야 위치 계산이 필요 없다.
          // 가운데 기준이면 확대 후 좌표가 밀려 여백 계산을 따로 해야 한다.
          transformOrigin: "top left",
          willChange: "transform",
          // CSSProperties에는 커스텀 속성 키가 없어 단언이 필요하다.
        } as CSSProperties}
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
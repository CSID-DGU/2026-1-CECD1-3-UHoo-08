import { useEffect, useState, type ReactNode } from "react";

/**
 * 목업 크기(1024×600)를 고정하고 화면에 맞춰 통째로 확대한다.
 *
 * 왜 반응형으로 짜지 않는가: 목업이 1024×600 기준으로 픽셀 단위까지 잡혀
 * 있고, 아이패드 한 대에서만 돌아가면 된다. 반응형으로 다시 짜면 목업과
 * 어긋나기 시작하고, 그 차이를 맞추는 데 남은 시간을 쓰게 된다.
 *
 * 아이패드 프로 11인치 전체화면 실측은 1194×802였다.
 *   가로 배율 1194/1024 = 1.166
 *   세로 배율  802/600  = 1.337
 * 작은 쪽(1.166)을 쓰면 1194×700이 되고 위아래로 102px이 남는다.
 * 그 여백은 배경색으로 채운다. 큰 쪽을 쓰면 좌우가 잘린다.
 */
const FRAME_W = 1024;
const FRAME_H = 600;

/** 목업 body 배경과 같은 색. 위아래 여백을 이 색으로 채운다. */
const LETTERBOX_BG = "#2a2d33";

function computeScale(): number {
  // visualViewport는 iOS에서 주소창·툴바를 제외한 실제 표시 영역을 준다.
  const vw = window.visualViewport?.width ?? window.innerWidth;
  const vh = window.visualViewport?.height ?? window.innerHeight;
  return Math.min(vw / FRAME_W, vh / FRAME_H);
}

export function KioskFrame({ children }: { children: ReactNode }) {
  const [scale, setScale] = useState(computeScale);

  useEffect(() => {
    const update = () => setScale(computeScale());

    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    window.visualViewport?.addEventListener("resize", update);

    // 홈 화면에서 실행한 직후에는 표시 영역이 한 박자 늦게 확정된다.
    const t = window.setTimeout(update, 300);

    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
      window.visualViewport?.removeEventListener("resize", update);
      window.clearTimeout(t);
    };
  }, []);

  return (
    <div
      className="fixed inset-0 flex items-center justify-center overflow-hidden"
      style={{ background: LETTERBOX_BG }}
    >
      <div
        style={{
          width: FRAME_W,
          height: FRAME_H,
          transform: `scale(${scale})`,
          transformOrigin: "center center",
          // 확대해도 글자가 뭉개지지 않도록 하위 요소를 별도 레이어로 올린다
          willChange: "transform",
        }}
        className="relative overflow-hidden rounded-[14px] bg-gray-100"
      >
        {children}
      </div>
    </div>
  );
}

export const KIOSK_FRAME_SIZE = { width: FRAME_W, height: FRAME_H };
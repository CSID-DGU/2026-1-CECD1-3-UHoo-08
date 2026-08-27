import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { KioskApp } from "./kiosk/KioskApp";

/**
 * 키오스크 진입점.
 *
 * 앱(main.tsx)과 달리 react-router를 쓰지 않는다. 키오스크는 화면 하나에
 * 탭 네 개(점검 / 피부 / 추천 / 환경)를 두는 구조라 URL이 바뀌지 않고,
 * 라우터를 끼우면 홈 화면에서 실행할 때 경로가 어긋날 여지만 생긴다.
 */
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <KioskApp />
  </StrictMode>
);
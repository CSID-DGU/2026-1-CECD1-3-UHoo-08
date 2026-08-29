import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { TopBar, TabBar, ErrorPanel, StaleBanner, Loading, type TabKey } from "./ui";
import type { DashboardResponse, RecommendationsResponse } from "./lib/types";
import type { QueryState } from "./lib/useKioskQuery";

/**
 * 탭3 — 오늘의 추천.
 *
 * ── 추천 이유를 반드시 함께 보인다 ───────────────────────────
 * 제품 이름만 나열하면 광고와 구분되지 않는다. 각 카드에 "실내 절대습도
 * 10.4 g/m³ — 건조 임계 이하"처럼 어떤 측정값 때문에 골랐는지를 붙인다.
 * 이 한 줄이 이 프로젝트의 추천과 일반 쇼핑 추천을 가르는 부분이다.
 *
 * ── QR은 이어보기용이다 ──────────────────────────────────────
 * 키오스크에서 세 개를 보고, 자세한 것은 각자 휴대폰에서 본다. 키오스크는
 * 거실이나 화장대에 놓여 있고 로그인이 유지되지만, 긴 목록을 훑거나
 * 구매로 이어지는 일은 휴대폰이 낫다.
 */

type Props = {
  reco: QueryState<RecommendationsResponse>;
  dashboard: DashboardResponse | null;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  onHome: () => void;
  /** 대체 추천을 보는 중이면 평소 추천으로 돌아가는 수단. 아니면 undefined. */
  onClearReplace?: () => void;
};

export function RecoScreen({ reco, dashboard, activeTab, onTab, onHome, onClearReplace }: Props) {
  const { data, error, loading, lastUpdated } = reco;

  // 서버가 context를 주면 그것을 쓰고, 없으면 대시보드에서 만든다.
  const node =
    dashboard?.nodes.find((n) => n.node_type === "ambient" && n.online) ??
    dashboard?.nodes.find((n) => n.online) ??
    null;

  const fallbackContext =
    node && node.temperature != null
      ? `${node.location_label || node.node_id} ${node.temperature.toFixed(1)}℃ / ${
          node.humidity != null ? `${node.humidity.toFixed(0)}%` : "—"
        }`
      : "센서 응답 없음";

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onHome} className="text-[25px] font-bold">
            오늘의 추천
          </button>
        }
        right={data?.context ?? fallbackContext}
      />

      {error && data ? <StaleBanner error={error} lastUpdated={lastUpdated} /> : null}

      <div className="flex-1 overflow-hidden px-[26px] py-[18px]">
        {loading && !data ? (
          <Loading label="추천을 불러오는 중" />
        ) : error && !data ? (
          <ErrorPanel error={error} onRetry={reco.refetch} />
        ) : data ? (
          <div className="flex h-full flex-col">
            {/* 무엇을 대신하는 추천인지 밝힌다. 밝히지 않으면 평소 추천과
                구분이 안 되고, 사용자가 왜 이 목록을 보는지 알 수 없다. */}
            {data.replacing ? (
              <div className="mb-3 flex flex-none items-center gap-3 rounded-[14px] bg-primary-50 p-[13px_17px]">
                <span className="text-[17px] leading-[1.5]">
                  <b>{data.replacing}</b> 대신 쓰실 만한 제품입니다
                </span>
                {onClearReplace ? (
                  <button
                    onClick={onClearReplace}
                    className="ml-auto h-[42px] flex-none rounded-[11px] border border-gray-200 bg-white px-3.5 text-[15px] font-semibold text-gray-400"
                  >
                    오늘의 추천 보기
                  </button>
                ) : null}
              </div>
            ) : null}

            <div className="grid min-h-0 flex-1 grid-cols-[1fr_200px] gap-[18px]">
            <div className="grid grid-cols-3 gap-3">
              {data.items.slice(0, 3).map((item) => (
                <div
                  key={item.product_id}
                  className="flex flex-col rounded-[16px] bg-white p-[17px_19px]"
                >
                  <div className="mb-[11px] h-[112px] overflow-hidden rounded-[11px] bg-gradient-to-br from-primary-100 to-primary-50">
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt=""
                        className="h-full w-full object-cover"
                        // 이미지가 깨져도 카드 배치가 무너지지 않게 한다
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display = "none";
                        }}
                      />
                    ) : null}
                  </div>

                  <div className="text-[18px] leading-[1.3] font-bold">{item.name}</div>
                  {item.brand ? (
                    <div className="mt-0.5 text-[15px] text-gray-300">{item.brand}</div>
                  ) : null}

                  <div className="mt-2 text-[15px] leading-[1.45] text-gray-400">
                    {item.reason}
                  </div>
                </div>
              ))}

              {data.items.length === 0 ? (
                <div className="col-span-3 flex items-center justify-center text-[18px] text-gray-300">
                  아직 추천할 제품이 없습니다.
                </div>
              ) : null}
            </div>

              <QrPanel url={data.qr_url} />
            </div>
          </div>
        ) : null}
      </div>

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

/**
 * QR 패널.
 *
 * 외부 QR 생성 API를 쓰지 않는 이유: 시연장 네트워크가 불안하면 QR만
 * 안 뜬다. 로컬에서 그리면 서버가 죽어도 이 부분은 살아 있다.
 */
function QrPanel({ url }: { url: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(url, {
      width: 320,
      margin: 1,
      color: { dark: "#18191d", light: "#ffffff" },
      errorCorrectionLevel: "M",
    })
      .then((d) => {
        if (alive) setSrc(d);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [url]);

  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className="grid h-[160px] w-[160px] place-items-center overflow-hidden rounded-[14px] bg-white p-2">
        {src ? (
          <img src={src} alt="추천 전체 보기 QR" className="h-full w-full" />
        ) : failed ? (
          <span className="px-2 text-center text-[13px] text-gray-300">
            QR을 만들지 못했습니다
          </span>
        ) : null}
      </div>

      <div className="text-center text-[16px] leading-[1.45] text-gray-400">
        휴대폰으로 스캔하면
        <br />
        전체 추천을 볼 수 있어요
      </div>

      {/* QR을 못 읽는 상황을 대비해 주소를 함께 둔다 */}
      <div className="max-w-[180px] text-center text-[11px] break-all text-gray-300">{url}</div>
    </div>
  );
}

export default RecoScreen;
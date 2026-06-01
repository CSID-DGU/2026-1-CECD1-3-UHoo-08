import { useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/common/PageHeader";
import { PrimaryButton } from "../../components/common/PrimaryButton";
import { ProductThumbnail } from "../../components/common/ProductThumbnail";
import { Toggle } from "../../components/common/Toggle";
import AppLayout from "../../layouts/AppLayout";
import { priceHistoryStores } from "../../mocks/priceTracking";

export function PriceHistoryPage() {
  const navigate = useNavigate();

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-6 pt-10">
        <PageHeader
          onBack={() => navigate(-1)}
          rightSlot={
            <div className="flex gap-2">
              <button
                className="h-10 w-10 rounded-xl bg-gray-100 text-gray-300"
                type="button"
              >
                ↥
              </button>
              <button
                className="h-10 w-10 rounded-xl bg-gray-100 text-gray-300"
                type="button"
              >
                ···
              </button>
            </div>
          }
        />

        <section className="mt-4 flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4">
          <ProductThumbnail
            className="h-[68px] w-[68px] shrink-0 bg-primary-50"
            green
            size="lg"
          />
          <div className="flex-1">
            <p className="text-body2 text-gray-500">라네즈 네오쿠션 21N</p>
            <p className="text-caption text-gray-300">
              레티놀 대신 히알루론산 기반
            </p>
            <p className="mt-1 text-body2 text-gray-500">
              현재{" "}
              <strong className="ml-2 text-h3 text-primary-500">
                28,600원
              </strong>
            </p>
          </div>
          <span className="rounded-full bg-primary-100 px-3 py-1 text-caption text-primary-500">
            24.7% 하락
          </span>
        </section>

        <div className="mt-3 grid grid-cols-4 rounded-xl bg-gray-100 p-1">
          {["1개월", "3개월", "6개월", "전체"].map((tab, index) => (
            <button
              className={`h-9 rounded-lg text-caption ${index === 0 ? "bg-white text-gray-500" : "text-gray-300"}`}
              key={tab}
              type="button"
            >
              {tab}
            </button>
          ))}
        </div>

        <section className="mt-3 rounded-xl border border-gray-200 bg-white p-4">
          <svg
            className="h-[236px] w-full"
            viewBox="0 0 320 236"
            role="img"
            aria-label="가격 히스토리 그래프"
          >
            <line x1="48" y1="24" x2="48" y2="204" stroke="#ECEFF2" />
            {[24, 70, 116, 162].map((y) => (
              <line x1="48" x2="300" y1={y} y2={y} stroke="#ECEFF2" key={y} />
            ))}
            <path
              d="M52 64 L78 66 L104 60 L130 72 L158 58 L190 52 L214 50 L236 78 L262 64"
              fill="none"
              stroke="#5B9A8B"
              strokeWidth="3"
            />
            <path
              d="M52 70 L78 72 L104 66 L130 78 L158 64 L190 58 L214 56 L236 84 L262 70 L262 204 L52 204 Z"
              fill="#EFF7F4"
              opacity="0.8"
            />
            <line
              x1="48"
              y1="148"
              x2="300"
              y2="148"
              stroke="#8FBFB3"
              strokeDasharray="6 6"
            />
            <text x="270" y="151" fill="#5B9A8B" fontSize="11">
              목표 29,000
            </text>
            <g>
              <rect
                x="220"
                y="12"
                width="92"
                height="58"
                rx="10"
                fill="#18191D"
              />
              <text x="230" y="31" fill="#8FBFB3" fontSize="11">
                05/19 오늘
              </text>
              <text x="230" y="48" fill="white" fontSize="16">
                28,600원
              </text>
              <text x="230" y="63" fill="#5B9A8B" fontSize="11">
                ▼ 9,400원 하락
              </text>
            </g>
            <text x="4" y="28" fill="#CBD0D6" fontSize="11">
              42,000
            </text>
            <text x="4" y="74" fill="#CBD0D6" fontSize="11">
              38,000
            </text>
            <text x="4" y="120" fill="#CBD0D6" fontSize="11">
              34,000
            </text>
            <text x="4" y="152" fill="#5B9A8B" fontSize="11">
              29,000
            </text>
            <text x="48" y="226" fill="#7B818C" fontSize="11">
              04/19
            </text>
            <text x="118" y="226" fill="#7B818C" fontSize="11">
              04/26
            </text>
            <text x="188" y="226" fill="#7B818C" fontSize="11">
              05/03
            </text>
            <text x="258" y="226" fill="#7B818C" fontSize="11">
              05/10
            </text>
          </svg>
        </section>

        <section className="mt-3 rounded-xl border border-gray-200 bg-white p-4">
          {[
            ["정가", "38,000원"],
            ["현재 최저가", "28,600원"],
            ["역대 최저가", "27,400원"],
          ].map(([label, value]) => (
            <div
              className="flex justify-between border-b border-gray-100 py-2 last:border-b-0"
              key={label}
            >
              <span className="text-body2 text-gray-300">{label}</span>
              <span
                className={`text-body2 ${label === "현재 최저가" ? "text-primary-500" : "text-gray-500"}`}
              >
                {value}
              </span>
            </div>
          ))}
        </section>

        <h2 className="mt-4 text-body1 text-gray-500">구매처별 현재가</h2>
        <div className="mt-3 grid gap-2">
          {priceHistoryStores.map(([name, price, tag]) => (
            <div
              className="flex justify-between rounded-xl bg-gray-100 px-4 py-3"
              key={name}
            >
              <span className="text-body2 text-gray-500">{name}</span>
              <span className="text-body2 text-primary-500">
                {price} · {tag}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-auto grid gap-3">
          <div className="mt-3 flex items-center gap-3 rounded-xl border border-gray-200 p-4">
            <div className="flex-1">
              <p className="text-body2 text-gray-500">가격 도달 알림</p>
              <p className="text-caption text-gray-300">
                목표가 이하가 되면 즉시 알려드려요
              </p>
            </div>
            <Toggle checked />
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-gray-200 p-4">
            <div className="flex-1">
              <p className="text-caption text-gray-300">목표가</p>
              <p className="text-h2 text-gray-500">29,000원</p>
            </div>
            <button
              className="rounded-xl bg-gray-100 px-4 py-2 text-body2 text-gray-500"
              type="button"
            >
              재설정
            </button>
          </div>
          <PrimaryButton>
            정보 저장하기
          </PrimaryButton>
        </div>
      </section>
    </AppLayout>
  );
}

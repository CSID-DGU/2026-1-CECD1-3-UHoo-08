import { BAND_STYLE } from "./ui";
import type { PriorityItem, RiskBand } from "./lib/types";

/**
 * 제품 고르기 모달.
 *
 * 두 곳에서 쓴다.
 *   · 점검 탭의 "측정하기" — 어느 제품을 측정할지
 *   · 이벤트 안내의 "확인해 볼까요" — 어느 제품을 확인할지
 *
 * ── 목록을 자르지 않는다 ─────────────────────────────────────
 * 처음에는 상위 두 개만 보여줬다. 그러면 사용자가 그 둘 중에서만 고를 수
 * 있고, 세 번째 제품을 재고 싶으면 방법이 없다. 확인 순위대로 정렬해
 * 전부 보여주고 스크롤하게 한다.
 *
 * 정렬은 서버가 준 순서를 그대로 따른다. 화면에서 다시 정렬하면 서버의
 * 순위 규칙과 어긋나기 시작한다.
 */

export type PickerProduct = {
  user_product_id: string;
  name: string | null;
  brand: string | null;
  score: number | null;
  band: RiskBand | null;
  /** 사용자가 이미 확인한 항목이 있으면 함께 보여준다. */
  findings?: string[];
};

export function toPickerProduct(item: PriorityItem): PickerProduct {
  return {
    user_product_id: item.user_product_id,
    name: item.name,
    brand: item.brand,
    score: item.score,
    band: item.band,
    findings: item.inspection?.findings ?? [],
  };
}

export function ProductPicker({
  title,
  description,
  products,
  onPick,
  onClose,
  emptyText = "보관 중인 제품이 없습니다.",
}: {
  title: string;
  description?: string;
  products: PickerProduct[];
  onPick: (userProductId: string) => void;
  onClose: () => void;
  emptyText?: string;
}) {
  return (
    <div
      className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 p-6"
      onPointerDown={onClose}
    >
      <div
        className="flex max-h-full w-full max-w-[780px] flex-col rounded-[18px] bg-white p-[22px]"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="flex-none">
          <div className="text-[23px] font-bold">{title}</div>
          {description ? (
            <div className="mt-1 text-[17px] text-gray-300">{description}</div>
          ) : null}
        </div>

        {/* 목록이 길어지면 여기만 스크롤된다. 버튼은 항상 보인다. */}
        <div className="my-3 min-h-0 flex-1 overflow-y-auto pr-1">
          {products.length === 0 ? (
            <div className="py-10 text-center text-[18px] text-gray-300">{emptyText}</div>
          ) : (
            products.map((p) => <Row key={p.user_product_id} product={p} onPick={onPick} />)
          )}
        </div>

        <button
          onClick={onClose}
          className="h-[58px] flex-none rounded-[14px] border border-gray-200 text-[19px] font-semibold text-gray-400"
        >
          닫기
        </button>
      </div>
    </div>
  );
}

function Row({
  product,
  onPick,
}: {
  product: PickerProduct;
  onPick: (id: string) => void;
}) {
  const style = product.band ? BAND_STYLE[product.band] : null;

  return (
    <button
      onClick={() => onPick(product.user_product_id)}
      className="mb-2 flex w-full items-center gap-3 rounded-[14px] border border-gray-200 p-[13px_16px] text-left active:bg-primary-50"
    >
      {style ? (
        <span
          className="grid h-10 w-10 flex-none place-items-center rounded-[11px] text-[19px]"
          style={{ background: style.pill }}
        >
          {style.emoji}
        </span>
      ) : null}

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[18px] font-semibold">
          {product.name || "이름 없는 제품"}
        </span>
        <span className="block truncate text-[15px] text-gray-300">
          {product.brand}
          {product.findings?.length ? (
            <span style={{ color: BAND_STYLE.high.text }}>
              {product.brand ? " · " : ""}
              {product.findings.join(" · ")} 확인됨
            </span>
          ) : null}
        </span>
      </span>

      {product.score != null && style ? (
        <span className="flex-none text-right">
          <span
            className="block text-[22px] font-bold tabular-nums"
            style={{ color: style.text }}
          >
            {Math.round(product.score)}
          </span>
          <span className="block text-[13px] text-gray-300">점검 순위</span>
        </span>
      ) : null}
    </button>
  );
}

export default ProductPicker;
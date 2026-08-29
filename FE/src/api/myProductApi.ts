import { care } from "../lib/careBase";

/**
 * 보유 화장품 등록.
 *
 * BE(Spring)가 아니라 AI 서버로 간다. BE의 UserProduct 엔티티에는
 * opened_at·storage_node_id가 없는데, 그 둘이 점검 순위를 내는 데 반드시
 * 필요한 값이다. 값을 실제로 쓰는 쪽이 쓰기도 맡는 편이 어긋날 여지가 적다.
 */
export interface ProductSearchItem {
  product_id: string;
  name: string;
  brand: string | null;
  category: string | null;
  image_url: string | null;
  price: number | null;
}

export interface StorageOption {
  node_id: string;
  label: string;
  /** 화장품은 대개 화장대에 둔다. 서버가 기본으로 잡아 준 곳. */
  default: boolean;
}

/** 색으로 변화를 재는 게 의미 있는 제형인지. */
export interface OpticalGuide {
  recommended: boolean;
  note: string;
  has_baseline: boolean;
}

/** 점검 순위에 들어가려면 아직 무엇이 필요한지. */
export interface MissingInfo {
  field: string;
  title: string;
  action: string;
}

export interface RegisterResult {
  user_product_id: string | null;
  name: string | null;
  opened_at: string | null;
  /** 일을 몰라 서버가 월 중간으로 잡았는지. 화면이 이 사실을 밝힌다. */
  opened_estimated: boolean;
  optical: OpticalGuide | null;
  missing: MissingInfo[];
  message: string;
}

export interface MyProduct {
  user_product_id: string;
  product_id: string | null;
  name: string | null;
  brand: string | null;
  opened_at: string | null;
  storage_node_id: string | null;
  storage_label: string | null;
  missing: MissingInfo[];
}

export const searchProductsForRegister = (q: string) =>
  care.get<ProductSearchItem[]>(
    `/api/care/products/search?q=${encodeURIComponent(q)}&limit=20`,
  );

export const getRegisterOptions = (userId: string) =>
  care.get<{ storages: StorageOption[] }>(
    `/api/care/products/register-options?user_id=${encodeURIComponent(userId)}`,
  );

export const registerMyProduct = (
  userId: string,
  body: {
    product_id: string;
    /** "YYYY-MM" 또는 "YYYY-MM-DD". 필수다. */
    opened_at: string;
    storage_node_id?: string | null;
  },
) =>
  care.post<RegisterResult>(
    `/api/care/products?user_id=${encodeURIComponent(userId)}`,
    body,
  );

export const getMyProducts = (userId: string) =>
  care.get<MyProduct[]>(
    `/api/care/products/mine?user_id=${encodeURIComponent(userId)}`,
  );

export const updateMyProduct = (
  userId: string,
  userProductId: string,
  body: { opened_at?: string; storage_node_id?: string },
) =>
  care.patch<MyProduct>(
    `/api/care/products/${userProductId}?user_id=${encodeURIComponent(userId)}`,
    body,
  );

export const deleteMyProduct = (userId: string, userProductId: string) =>
  care.delete<void>(
    `/api/care/products/${userProductId}?user_id=${encodeURIComponent(userId)}`,
  );

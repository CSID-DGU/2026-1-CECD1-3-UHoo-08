import { api } from "../lib/api";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string;

export function getProfileImageUrl(stored: string | null): string | null {
  if (!stored) return null;
  if (stored.startsWith("http")) {
    return stored.replace("/profile_image/", "/profile-image/");
  }
  const path = stored.startsWith("/") ? stored.slice(1) : stored;
  return `${SUPABASE_URL}/storage/v1/object/public/profile-image/${path}`;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface SkinProfileInfo {
  personalColor: string | null;
  skinType: string | null;
  skinConcerns: string[];
  notes: string[] | null;
}

export interface UserMeResponse {
  id: string;
  name: string | null;
  email: string | null;
  profileImageUrl: string | null;
  gender: string | null;
  onboardingCompleted: boolean;
  skinProfile: SkinProfileInfo | null;
  stats: { wishlistCount: number; trackingCount: number; registeredCount: number } | null;
}

export const getMyProfile = () =>
  api.get<ApiResponse<UserMeResponse>>("/users/profile");

// 역방향 매핑 (API enum → 화면 표시)
export const PERSONAL_COLOR_LABEL: Record<string, string> = {
  SPRING_WARM: "웜톤\n봄 웜",
  SUMMER_COOL: "쿨톤\n여름 쿨",
  AUTUMN_MUTE: "뮤트\n가을 뮤트",
  WINTER_COOL: "쿨톤\n겨울 쿨",
  UNKNOWN: "잘 모르겠어요",
};

export const SKIN_TYPE_LABEL: Record<string, string> = {
  DRY: "건성",
  NORMAL: "중성",
  OILY: "지성",
  COMBINATION: "복합성",
  DEHYDRATED_OILY: "수부지",
};

export const CONCERN_LABEL: Record<string, string> = {
  SENSITIVITY: "민감성",
  ACNE: "여드름",
  ATOPY: "아토피",
  WHITENING: "미백/잡티",
  SEBUM: "피지/블랙헤드",
  PORE: "모공",
  DARK_CIRCLE: "다크서클",
  REDNESS: "홍조",
  TEXTURE: "각질",
  WRINKLE: "주름/탄력",
};

// ── 프로필 ──────────────────────────────────────────────────────────

export interface ProfileUpdateResponse {
  id: string;
  name: string;
  gender: string | null;
  profileImageUrl: string | null;
}

export const updateProfile = (
  name: string | null,
  gender: string | null,
  image: File | null,
) => {
  const form = new FormData();
  if (name) form.append("name", name);
  if (gender) form.append("gender", gender);
  if (image) form.append("image", image);
  return api.patchForm<ApiResponse<ProfileUpdateResponse>>("/users/profile", form);
};

// ── 피부 프로필 ──────────────────────────────────────────────────────

// 프론트 label → 백엔드 enum 매핑
const PERSONAL_COLOR_MAP: Record<string, string> = {
  "spring-warm": "SPRING_WARM",
  "summer-cool": "SUMMER_COOL",
  "autumn-warm": "AUTUMN_MUTE",
  "winter-cool": "WINTER_COOL",
  "unknown":     "UNKNOWN",
};

const SKIN_TYPE_MAP: Record<string, string> = {
  "건성":  "DRY",
  "중성":  "NORMAL",
  "지성":  "OILY",
  "복합성": "COMBINATION",
  "수부지": "DEHYDRATED_OILY",
};

const CONCERN_MAP: Record<string, string> = {
  "민감성":      "SENSITIVITY",
  "여드름":      "ACNE",
  "아토피":      "ATOPY",
  "미백/잡티":   "WHITENING",
  "피지/블랙헤드": "SEBUM",
  "모공":        "PORE",
  "다크서클":    "DARK_CIRCLE",
  "홍조":        "REDNESS",
  "각질":        "TEXTURE",
  "주름/탄력":   "WRINKLE",
};

export const saveOnboardingProducts = (productIds: string[]) =>
  api.post<ApiResponse<number>>("/onboarding/favorites/items/batch", { productIds });

export const completeOnboarding = () =>
  api.patch<ApiResponse<unknown>>("/onboarding");

export const updateSkinProfile = (
  personalColor: string,
  skinType: string,
  concerns: string[],
  notes?: string[],
) =>
  api.patch<ApiResponse<unknown>>("/users/me/skin-profile", {
    personalColor: PERSONAL_COLOR_MAP[personalColor] ?? null,
    skinType:      SKIN_TYPE_MAP[skinType] ?? null,
    skinConcerns:  concerns.map((c) => CONCERN_MAP[c]).filter(Boolean),
    notes:         notes ?? null,
  });

// display label → API enum (피부정보 수정 페이지 전용)
const PERSONAL_COLOR_MAP_LABEL: Record<string, string> = {
  "웜톤\n봄 웜":    "SPRING_WARM",
  "쿨톤\n여름 쿨":  "SUMMER_COOL",
  "뮤트\n가을 뮤트": "AUTUMN_MUTE",
  "쿨톤\n겨울 쿨":  "WINTER_COOL",
  "잘 모르겠어요":  "UNKNOWN",
};

const SKIN_TYPE_MAP_LABEL: Record<string, string> = {
  "건성": "DRY", "중성": "NORMAL", "지성": "OILY", "복합성": "COMBINATION", "수부지": "DEHYDRATED_OILY",
};

const CONCERN_MAP_LABEL: Record<string, string> = {
  "민감성": "SENSITIVITY", "여드름": "ACNE", "아토피": "ATOPY",
  "미백/잡티": "WHITENING", "피지/블랙헤드": "SEBUM", "모공": "PORE",
  "다크서클": "DARK_CIRCLE", "홍조": "REDNESS", "각질": "TEXTURE", "주름/탄력": "WRINKLE",
};

export const updateSkinProfileByLabel = (
  personalColorLabel: string,
  skinTypeLabel: string,
  concernLabels: string[],
  notes: string[],
) =>
  api.patch<ApiResponse<unknown>>("/users/me/skin-profile", {
    personalColor: PERSONAL_COLOR_MAP_LABEL[personalColorLabel] ?? null,
    skinType:      SKIN_TYPE_MAP_LABEL[skinTypeLabel] ?? null,
    skinConcerns:  concernLabels.map((c) => CONCERN_MAP_LABEL[c]).filter(Boolean),
    notes:         notes.length > 0 ? notes : null,
  });

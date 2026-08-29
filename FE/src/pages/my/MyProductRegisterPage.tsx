import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Search } from "lucide-react";
import { OpenedDateInput } from "../../components/my/OpenedDateInput";
import { toOpenedAt } from "../../components/my/openedDate";
import {
  type MissingInfo,
  type OpticalGuide,
  type ProductSearchItem,
  type StorageOption,
  getRegisterOptions,
  registerMyProduct,
  searchProductsForRegister,
} from "../../api/myProductApi";
import { getMyProfile } from "../../api/userApi";
import { isUserFixable } from "../../components/my/missing";
import AppLayout from "../../layouts/AppLayout";

/**
 * 보유 화장품 등록.
 *
 * 제품만 필수고 나머지는 선택이다. 모르는 값을 강제로 받으면 아무거나 넣게
 * 되고, 그렇게 들어온 개봉일은 점검 순서를 통째로 틀리게 만든다.
 *
 * 대신 등록 직후에 무엇이 비었는지 그 자리에서 알려준다. 나중에 점검
 * 목록에서 "정보가 더 필요한 제품"으로 발견하게 두면 이유를 알 수 없다.
 */
export function MyProductRegisterPage() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState<string | null>(null);
  const [storages, setStorages] = useState<StorageOption[]>([]);

  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<ProductSearchItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState<ProductSearchItem | null>(null);

  // 년·월은 필수, 일은 선택. 캘린더 대신 직접 입력한다.
  const [opened, setOpened] = useState({ year: "", month: "", day: "" });
  const [storage, setStorage] = useState("");

  const openedAt = toOpenedAt(opened.year, opened.month, opened.day);

  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState<{
    name: string;
    missing: MissingInfo[];
    message: string;
    optical: OpticalGuide | null;
  } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    getMyProfile()
      .then((res) => {
        setUserId(res.data.id);
        return getRegisterOptions(res.data.id);
      })
      .then((r) => {
        setStorages(r.storages);
        // 화장품은 대개 화장대에 둔다. 매번 고르게 하지 않는다.
        setStorage(r.storages.find((x) => x.default)?.node_id ?? "");
      })
      .catch(() => setStorages([]));
  }, []);

  const search = async () => {
    const q = keyword.trim();
    if (!q) return;
    setSearching(true);
    setFailed(null);
    try {
      setResults(await searchProductsForRegister(q));
    } catch {
      setFailed("제품을 찾지 못했어요");
    } finally {
      setSearching(false);
    }
  };

  const submit = async () => {
    if (!picked || !userId || !openedAt) return;
    setSaving(true);
    setFailed(null);
    try {
      const res = await registerMyProduct(userId, {
        product_id: picked.product_id,
        opened_at: openedAt,
        storage_node_id: storage || null,
      });
      setDone({
        name: res.name ?? picked.name,
        missing: res.missing,
        message: res.message,
        optical: res.optical,
      });
    } catch {
      setFailed("등록하지 못했어요");
    } finally {
      setSaving(false);
    }
  };

  if (done) {
    return (
      <AppLayout className="pb-10">
        <Header onBack={() => navigate(-1)} title="등록 완료" />
        <div className="px-4">
          <div className="mt-4 rounded-2xl border border-gray-100 bg-white p-4">
            <p className="text-body1 text-gray-500">{done.name}</p>
            <p className="mt-1 text-caption text-gray-300">{done.message}</p>

            {/* 사용자가 넣을 수 있는 항목만 보여준다. 성분 민감도·PAO는
                제품 자체의 성질이라 사용자가 넣을 곳이 없는데, 그것까지
                "미등록"이라 띄우면 어디서 고치라는 건지 알 수 없다. */}
            {done.missing.filter(isUserFixable).length > 0 && (
              <div className="mt-3 flex flex-col gap-2">
                {done.missing.filter(isUserFixable).map((m) => (
                  <div
                    className="rounded-xl p-3"
                    key={m.field}
                    style={{ background: "#FDF3E7" }}
                  >
                    <p className="text-body2" style={{ color: "#8A5A12" }}>
                      {m.title}
                    </p>
                    <p className="mt-0.5 text-caption text-gray-400">{m.action}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 색 기준값 안내.
              AS7341은 키오스크에 달려 있어 앱에서는 잴 수 없다. 그래서
              "가서 재세요"까지만 말한다. 투명 제형이면 권하지 않는다 —
              쓸모없는 측정을 시키고 그 숫자를 근거처럼 보여주게 된다. */}
          {done.optical && !done.optical.has_baseline && (
            <div
              className="mt-3 rounded-2xl p-4"
              style={{ background: "#F0F5FD", border: "1px solid #DBE6F8" }}
            >
              <p className="text-body2 text-gray-500">
                {done.optical.recommended
                  ? "키오스크에서 첫 색을 재두세요"
                  : "색 측정은 건너뛰셔도 됩니다"}
              </p>
              <p className="mt-1 text-caption leading-[1.5] text-gray-400">
                {done.optical.note}
                {done.optical.recommended &&
                  " 지금 색을 기록해두면, 나중에 잰 색과 비교해 얼마나 변했는지 알 수 있어요."}
              </p>
            </div>
          )}

          <button
            className="mt-4 h-[52px] w-full rounded-2xl bg-primary-500 text-body1 text-white"
            onClick={() => {
              setDone(null);
              setPicked(null);
              setResults(null);
              setKeyword("");
              setOpened({ year: "", month: "", day: "" });
              // 기본 보관 위치는 유지한다. 빈 값으로 되돌리면 두 번째
              // 제품부터 화장대가 풀린 채로 등록된다.
              setStorage(storages.find((x) => x.default)?.node_id ?? "");
            }}
            type="button"
          >
            제품 더 등록하기
          </button>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout className="pb-10">
      <Header onBack={() => navigate(-1)} title="보유 화장품 등록" />

      <div className="px-4">
        {/* 1. 제품 고르기 — 유일한 필수 항목 */}
        <div className="mt-3 flex gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-2xl border border-gray-100 bg-white px-3">
            <Search className="h-4 w-4 shrink-0 text-gray-300" strokeWidth={1.8} />
            <input
              className="h-[48px] w-full text-body2 text-gray-500 outline-none"
              placeholder="제품명 또는 브랜드"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void search()}
            />
          </div>
          <button
            className="h-[48px] shrink-0 rounded-2xl bg-primary-500 px-4 text-body2 text-white disabled:bg-gray-200"
            disabled={searching || !keyword.trim()}
            onClick={() => void search()}
            type="button"
          >
            {searching ? "검색 중" : "검색"}
          </button>
        </div>

        {picked ? (
          <div className="mt-3 flex items-center gap-3 rounded-2xl border border-primary-300 bg-primary-50 p-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-body2 text-gray-500">{picked.name}</p>
              <p className="truncate text-caption text-gray-300">{picked.brand}</p>
            </div>
            <button
              className="shrink-0 text-caption text-primary-500"
              onClick={() => setPicked(null)}
              type="button"
            >
              변경
            </button>
          </div>
        ) : results ? (
          <div className="mt-3 flex flex-col gap-2">
            {results.length === 0 && (
              <p className="text-caption text-gray-300">검색 결과가 없어요</p>
            )}
            {results.map((p) => (
              <button
                className="flex items-center gap-3 rounded-2xl border border-gray-100 bg-white p-3 text-left"
                key={p.product_id}
                onClick={() => setPicked(p)}
                type="button"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body2 text-gray-500">{p.name}</p>
                  <p className="truncate text-caption text-gray-300">
                    {p.brand}
                    {p.price != null && ` · ${p.price.toLocaleString()}원`}
                  </p>
                </div>
              </button>
            ))}
          </div>
        ) : null}

        {/* 2. 선택 항목 — 제품을 고른 뒤에만 묻는다 */}
        {picked && (
          <div className="mt-5">
            <Field label="개봉일">
              <OpenedDateInput
                year={opened.year}
                month={opened.month}
                day={opened.day}
                onChange={setOpened}
              />
            </Field>

            <Field label="보관 위치 (선택)">
              {storages.length === 0 ? (
                <p className="text-caption text-gray-300">
                  등록된 보관함이 없어요
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {storages.map((s) => (
                    <button
                      className={`h-[44px] rounded-2xl border px-4 text-body2 ${
                        storage === s.node_id
                          ? "border-primary-500 bg-primary-50 text-primary-600"
                          : "border-gray-100 bg-white text-gray-400"
                      }`}
                      key={s.node_id}
                      onClick={() =>
                        setStorage(storage === s.node_id ? "" : s.node_id)
                      }
                      type="button"
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              )}
            </Field>
          </div>
        )}

        {failed && <p className="mt-3 text-caption text-[#E05A5A]">{failed}</p>}

        <button
          className="mt-5 h-[52px] w-full rounded-2xl bg-primary-500 text-body1 text-white disabled:bg-gray-200 disabled:text-gray-300"
          disabled={!picked || !openedAt || saving}
          onClick={() => void submit()}
          type="button"
        >
          {saving
            ? "등록하는 중…"
            : !picked
              ? "제품을 먼저 골라주세요"
              : !openedAt
                ? "개봉일을 입력해 주세요"
                : "등록하기"}
        </button>
      </div>
    </AppLayout>
  );
}

function Header({ onBack, title }: { onBack: () => void; title: string }) {
  return (
    <header className="flex items-center gap-2 px-4 pt-4 pb-2">
      <button onClick={onBack} type="button" aria-label="뒤로">
        <ChevronLeft className="h-6 w-6 text-gray-500" strokeWidth={1.8} />
      </button>
      <h1 className="text-body1 text-gray-500">{title}</h1>
    </header>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-caption text-gray-400">{label}</p>
      {children}
    </div>
  );
}

export default MyProductRegisterPage;

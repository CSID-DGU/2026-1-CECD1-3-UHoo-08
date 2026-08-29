import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import {
  type MyProduct,
  getMyProducts,
  deleteMyProduct,
  getRegisterOptions,
  updateMyProduct,
  type StorageOption,
} from "../../api/myProductApi";
import { getMyProfile } from "../../api/userApi";
import { OpenedDateInput } from "../../components/my/OpenedDateInput";
import { fromOpenedAt, toOpenedAt } from "../../components/my/openedDate";
import { isUserFixable } from "../../components/my/missing";
import AppLayout from "../../layouts/AppLayout";

/**
 * 등록한 보유 화장품 목록과 수정.
 *
 * 등록만 해두고 개봉일을 안 넣으면 점검 목록에 안 뜬다. 그 이유를 볼 곳이
 * 없으면 사용자는 "등록했는데 왜 안 보이지"에서 막힌다. 그래서 빠진 값을
 * 목록에서 바로 보여주고, 그 자리에서 고칠 수 있게 한다.
 */
export function MyProductListPage() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState<string | null>(null);
  const [items, setItems] = useState<MyProduct[] | null>(null);
  const [storages, setStorages] = useState<StorageOption[]>([]);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  /** 삭제는 되돌릴 수 없어 한 번 더 묻는다. */
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => {
    getMyProfile()
      .then(async (res) => {
        setUserId(res.data.id);
        const [list, opts] = await Promise.all([
          getMyProducts(res.data.id),
          getRegisterOptions(res.data.id),
        ]);
        setItems(list);
        setStorages(opts.storages);
      })
      .catch(() => setFailed(true));
  }, []);

  const applyUpdate = (updated: MyProduct) => {
    setItems((prev) =>
      (prev ?? []).map((x) =>
        x.user_product_id === updated.user_product_id ? updated : x,
      ),
    );
    setEditing(null);
  };

  const remove = async (id: string) => {
    if (!userId) return;
    try {
      await deleteMyProduct(userId, id);
      setItems((prev) => (prev ?? []).filter((x) => x.user_product_id !== id));
    } catch {
      setFailed(true);
    } finally {
      setConfirming(null);
    }
  };

  return (
    <AppLayout className="pb-10">
      <header className="flex items-center gap-2 px-4 pt-4 pb-2">
        <button onClick={() => navigate(-1)} type="button" aria-label="뒤로">
          <ChevronLeft className="h-6 w-6 text-gray-500" strokeWidth={1.8} />
        </button>
        <h1 className="flex-1 text-body1 text-gray-500">보유 화장품</h1>
        <button
          className="flex items-center gap-1 text-body2 text-primary-500"
          onClick={() => navigate("/my/products/new")}
          type="button"
        >
          <Plus className="h-4 w-4" strokeWidth={2} />
          등록
        </button>
      </header>

      <div className="px-4">
        {failed ? (
          <Empty text="목록을 불러오지 못했어요" />
        ) : !items ? (
          <Empty text="불러오는 중이에요" />
        ) : items.length === 0 ? (
          <Empty text="아직 등록한 화장품이 없어요" />
        ) : (
          <div className="mt-2 flex flex-col gap-2">
            {items.map((item) => (
              <div
                className="rounded-2xl border border-gray-100 bg-white p-3"
                key={item.user_product_id}
              >
                <p className="truncate text-body2 text-gray-500">{item.name}</p>
                <p className="mt-0.5 truncate text-caption text-gray-300">
                  {item.brand}
                </p>

                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  <Meta label="개봉일" value={item.opened_at ?? "미등록"} />
                  <Meta
                    label="보관 위치"
                    value={item.storage_label ?? "미지정"}
                  />
                </div>

                {/* 왜 점검 목록에 안 뜨는지 여기서 보여준다 */}
                {item.missing.filter(isUserFixable).length > 0 && (
                  <div
                    className="mt-2 rounded-xl p-2.5"
                    style={{ background: "#FDF3E7" }}
                  >
                    {item.missing.filter(isUserFixable).map((m) => (
                      <p
                        className="text-caption"
                        key={m.field}
                        style={{ color: "#8A5A12" }}
                      >
                        {m.title}
                      </p>
                    ))}
                  </div>
                )}

                {editing === item.user_product_id && userId ? (
                  <EditForm
                    item={item}
                    storages={storages}
                    userId={userId}
                    onCancel={() => setEditing(null)}
                    onSaved={applyUpdate}
                  />
                ) : confirming === item.user_product_id ? (
                  <div className="mt-3 border-t border-gray-100 pt-3">
                    <p className="text-caption text-gray-400">
                      목록에서 뺄까요? 지난 측정·확인 기록은 남습니다.
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button
                        className="h-[40px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
                        onClick={() => setConfirming(null)}
                        type="button"
                      >
                        취소
                      </button>
                      <button
                        className="h-[40px] flex-1 rounded-xl text-body2 text-white"
                        style={{ background: "#E05A5A" }}
                        onClick={() => void remove(item.user_product_id)}
                        type="button"
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 flex gap-2">
                    <button
                      className="h-[40px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
                      onClick={() => setEditing(item.user_product_id)}
                      type="button"
                    >
                      수정
                    </button>
                    <button
                      className="grid h-[40px] w-[48px] place-items-center rounded-xl border border-gray-100"
                      onClick={() => setConfirming(item.user_product_id)}
                      type="button"
                      aria-label="목록에서 빼기"
                    >
                      <Trash2 className="h-4 w-4 text-gray-300" strokeWidth={1.8} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

function EditForm({
  item,
  storages,
  userId,
  onCancel,
  onSaved,
}: {
  item: MyProduct;
  storages: StorageOption[];
  userId: string;
  onCancel: () => void;
  onSaved: (updated: MyProduct) => void;
}) {
  const [opened, setOpened] = useState(fromOpenedAt(item.opened_at));
  const [storage, setStorage] = useState(item.storage_node_id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openedAt = toOpenedAt(opened.year, opened.month, opened.day);

  const save = async () => {
    if (!openedAt) {
      setError("개봉일의 년·월을 입력해 주세요");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onSaved(
        await updateMyProduct(userId, item.user_product_id, {
          opened_at: openedAt,
          storage_node_id: storage,
        }),
      );
    } catch {
      setError("수정하지 못했어요");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <p className="mb-1.5 text-caption text-gray-400">개봉일</p>
      <OpenedDateInput
        year={opened.year}
        month={opened.month}
        day={opened.day}
        onChange={setOpened}
      />

      <p className="mt-3 mb-1.5 text-caption text-gray-400">보관 위치</p>
      <div className="flex flex-wrap gap-2">
        {storages.map((s) => (
          <button
            className={`h-[40px] rounded-xl border px-3 text-body2 ${
              storage === s.node_id
                ? "border-primary-500 bg-primary-50 text-primary-600"
                : "border-gray-100 bg-white text-gray-400"
            }`}
            key={s.node_id}
            onClick={() => setStorage(storage === s.node_id ? "" : s.node_id)}
            type="button"
          >
            {s.label}
          </button>
        ))}
      </div>

      {error && <p className="mt-2 text-caption text-[#E05A5A]">{error}</p>}

      <div className="mt-3 flex gap-2">
        <button
          className="h-[44px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
          onClick={onCancel}
          type="button"
        >
          취소
        </button>
        <button
          className="h-[44px] flex-1 rounded-xl bg-primary-500 text-body2 text-white disabled:bg-gray-200"
          disabled={saving}
          onClick={() => void save()}
          type="button"
        >
          {saving ? "저장 중…" : "저장"}
        </button>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-caption text-gray-400">
      {label} <span className="text-gray-500">{value}</span>
    </p>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div
      className="mt-4 flex h-[120px] items-center justify-center rounded-2xl"
      style={{ background: "#F0F5FD", border: "1px dashed #C5DDF5" }}
    >
      <p className="text-caption text-gray-300">{text}</p>
    </div>
  );
}

export default MyProductListPage;

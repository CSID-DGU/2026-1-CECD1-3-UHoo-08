import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Smile, Layers, Sun, Droplets, Folder, Plus, X, LayoutGrid } from "lucide-react";
import { type WishlistItem, getWishlists } from "../../api/wishlistApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

const CUSTOM_FOLDERS_KEY = "wishlist-custom-folders";

const DEFAULT_FOLDERS = [
  { key: "lip", label: "Lip", Icon: Smile },
  { key: "base", label: "Base", Icon: Layers },
  { key: "sun", label: "Sun", Icon: Sun },
  { key: "skincare", label: "Skincare", Icon: Droplets },
];

function loadCustomFolders(): string[] {
  try {
    return JSON.parse(localStorage.getItem(CUSTOM_FOLDERS_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveCustomFolders(folders: string[]) {
  localStorage.setItem(CUSTOM_FOLDERS_KEY, JSON.stringify(folders));
}

export function WishlistPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [customFolders, setCustomFolders] = useState<string[]>(loadCustomFolders);
  const [showAddSheet, setShowAddSheet] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  useEffect(() => {
    getWishlists()
      .then((res) => setItems(res.data.wishlists ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function countForCategory(category: string) {
    return items.filter(
      (i) => (i.product.category ?? "").toLowerCase() === category.toLowerCase(),
    ).length;
  }

  function handleAddFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    const updated = [...customFolders, name];
    setCustomFolders(updated);
    saveCustomFolders(updated);
    setNewFolderName("");
    setShowAddSheet(false);
  }

  function handleRemoveCustomFolder(name: string) {
    const updated = customFolders.filter((f) => f !== name);
    setCustomFolders(updated);
    saveCustomFolders(updated);
  }

  const totalCount = items.length;

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-32 pt-10">
        <PageHeader title="찜한 제품" onBack={() => navigate(-1)} />

        {loading ? (
          <p className="mt-16 text-center text-body2 text-gray-300">불러오는 중...</p>
        ) : (
          <>
            {totalCount > 0 && (
              <div className="mt-4 rounded-xl bg-primary-50 px-4 py-3">
                <p className="text-body2 text-primary-500">총 {totalCount}개 제품을 찜했어요</p>
              </div>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <FolderCard
                key="all"
                label="전체"
                count={totalCount}
                Icon={LayoutGrid}
                onClick={() => navigate("/wishlist/all")}
              />

              {DEFAULT_FOLDERS.map(({ key, label, Icon }) => {
                const count = countForCategory(key);
                return (
                  <FolderCard
                    key={key}
                    label={label}
                    count={count}
                    Icon={Icon}
                    onClick={() => navigate(`/wishlist/${key}`)}
                  />
                );
              })}

              {customFolders.map((name) => {
                const count = countForCategory(name);
                return (
                  <FolderCard
                    key={name}
                    label={name}
                    count={count}
                    Icon={Folder}
                    onClick={() => navigate(`/wishlist/${encodeURIComponent(name)}`)}
                    onRemove={() => handleRemoveCustomFolder(name)}
                  />
                );
              })}
            </div>

            <button
              className="mt-4 flex h-[72px] w-full items-center justify-center gap-2 rounded-2xl text-body2 text-primary-500"
              style={{ border: "1.5px dashed #4A90D9", background: "#F0F7FF" }}
              onClick={() => setShowAddSheet(true)}
              type="button"
            >
              <Plus className="h-4 w-4" strokeWidth={2} />
              폴더 추가하기
            </button>
          </>
        )}
      </section>

      {showAddSheet && (
        <div
          className="fixed inset-0 z-40 bg-black/30"
          onClick={() => setShowAddSheet(false)}
        />
      )}

      <div
        className="fixed inset-x-0 bottom-0 z-50 mx-auto max-w-[430px] rounded-t-2xl bg-white p-6 shadow-xl transition-transform duration-300"
        style={{ transform: showAddSheet ? "translateY(0)" : "translateY(100%)" }}
      >
        <div className="mx-auto mb-5 h-1 w-10 rounded-full bg-gray-200" />
        <h2 className="text-h3 text-gray-500">폴더 이름 입력</h2>
        <div className="mt-5 flex h-14 items-center gap-2 rounded-xl border border-gray-200 px-4 focus-within:border-primary-500">
          <input
            className="flex-1 text-body1 text-gray-500 outline-none placeholder:text-gray-200"
            type="text"
            placeholder="예: toner, eyeshadow"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddFolder()}
          />
        </div>
        <button
          className="mt-4 h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white disabled:opacity-50"
          disabled={!newFolderName.trim()}
          onClick={handleAddFolder}
          type="button"
        >
          추가하기
        </button>
      </div>
    </AppLayout>
  );
}

function FolderCard({
  label,
  count,
  Icon,
  onClick,
  onRemove,
}: {
  label: string;
  count: number;
  Icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  onClick: () => void;
  onRemove?: () => void;
}) {
  return (
    <button
      className="relative flex flex-col items-center gap-3 rounded-2xl py-6 text-primary-700"
      style={{ background: "linear-gradient(135deg, #9DBFEE, #C5DDF5)" }}
      onClick={onClick}
      type="button"
    >
      {onRemove && (
        <span
          className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-white/30"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          role="button"
          aria-label="폴더 삭제"
        >
          <X className="h-3 w-3 text-primary-700" strokeWidth={2.5} />
        </span>
      )}

      <span
        className="flex h-12 w-12 items-center justify-center rounded-full"
        style={{ background: "rgba(255,255,255,0.5)" }}
      >
        <Icon className="h-6 w-6 text-primary-600" strokeWidth={1.8} />
      </span>

      <div className="text-center">
        <p className="text-body2 font-semibold capitalize">{label}</p>
        <p className="text-caption opacity-80">{count}개</p>
      </div>
    </button>
  );
}

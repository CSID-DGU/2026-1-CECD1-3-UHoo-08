import { useNavigate } from "react-router-dom";
import { Badge } from "../../components/common/Badge";
import { PageHeader } from "../../components/common/PageHeader";
import { ProductThumbnail } from "../../components/common/ProductThumbnail";
import AppLayout from "../../layouts/AppLayout";
import { favoriteProducts } from "../../mocks/products";

export function FavoriteProductsPage() {
  const navigate = useNavigate();

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-8 pt-10">
        <PageHeader title="관심 제품" onBack={() => navigate(-1)} rightSlot={<button className="text-body2 text-primary-500" type="button">정렬</button>} />

        <section className="mt-5 rounded-xl bg-primary-50 p-4">
          <p className="text-body2 text-primary-500">찜한 제품 6개</p>
          <p className="mt-1 text-caption text-gray-500">평균 적합도 90% · 평균 가격 25,000원</p>
        </section>

        <div className="mt-4 grid gap-3">
          {favoriteProducts.map(([name, desc, price]) => (
            <button className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 text-left" key={name} type="button">
              <ProductThumbnail className="h-[60px] w-[60px] shrink-0 bg-primary-50" green size="sm" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-body2 text-gray-500">{name}</p>
                <p className="truncate text-caption text-gray-300">{desc}</p>
                <p className="mt-2 text-body2 text-gray-500">{price}</p>
              </div>
              <Badge>85% 적합</Badge>
            </button>
          ))}
        </div>
      </section>
    </AppLayout>
  );
}

import { ProductThumbnail } from "./ProductThumbnail";

type ProductMiniCardProps = {
  name: string;
  subtitle?: string;
  price?: string;
  green?: boolean;
  selected?: boolean;
  onClick?: () => void;
};

export function ProductMiniCard({ green, name, onClick, price, selected, subtitle }: ProductMiniCardProps) {
  return (
    <button
      className={`min-w-[90px] rounded-xl border p-3 text-center ${
        selected ? "border-primary-500 bg-primary-50" : "border-gray-200 bg-white"
      }`}
      onClick={onClick}
      type="button"
    >
      <ProductThumbnail className="mx-auto h-11 w-11 bg-primary-50" green={green} size="sm" />
      <p className="mt-2 truncate text-caption text-primary-500">{name}</p>
      {subtitle && <p className="truncate text-[10px] text-gray-300">{subtitle}</p>}
      {price && <p className="text-caption text-primary-500">{price}</p>}
    </button>
  );
}

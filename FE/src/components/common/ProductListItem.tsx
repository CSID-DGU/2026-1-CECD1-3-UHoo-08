import { Badge } from "./Badge";
import { ProductThumbnail } from "./ProductThumbnail";

type ProductListItemProps = {
  name: string;
  meta: string;
  price?: string;
  match?: string;
  best?: boolean;
  green?: boolean;
  selected?: boolean;
  actionLabel?: string;
  onClick?: () => void;
};

export function ProductListItem({
  actionLabel,
  best,
  green,
  match,
  meta,
  name,
  onClick,
  price,
  selected,
}: ProductListItemProps) {
  const content = (
    <>
      <ProductThumbnail className="h-[70px] w-[70px] shrink-0" green={green} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-body2 text-gray-500">{name}</p>
        <p className="truncate text-caption text-gray-300">{meta}</p>
        {price && <p className="mt-2 text-body1 text-gray-500">{price}</p>}
      </div>
      <div className="grid shrink-0 gap-2">
        {match && <Badge>{match}</Badge>}
        {best && <Badge className="px-5 text-center">BEST</Badge>}
        {actionLabel && (
          <span className="rounded-xl bg-primary-500 px-4 py-2 text-caption text-white">
            {actionLabel}
          </span>
        )}
      </div>
    </>
  );

  const className = `flex w-full items-center gap-4 rounded-xl border p-3 text-left ${
    selected ? "border-primary-500 bg-primary-50" : "border-gray-200 bg-white"
  }`;

  if (onClick) {
    return (
      <button className={className} onClick={onClick} type="button">
        {content}
      </button>
    );
  }

  return <div className={className}>{content}</div>;
}

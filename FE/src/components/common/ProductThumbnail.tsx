type ProductThumbnailProps = {
  className?: string;
  green?: boolean;
  size?: "sm" | "md" | "lg" | "wide";
};

const sizeClass = {
  sm: "h-10 w-10",
  md: "h-11 w-11",
  lg: "h-14 w-14",
  wide: "h-[68px] w-[108px]",
};

export function ProductThumbnail({ className = "", green = false, size = "md" }: ProductThumbnailProps) {
  return (
    <div className={`flex items-center justify-center rounded-xl bg-gray-100 ${className}`}>
      <div className={`rounded-md ${green ? "bg-primary-100" : "bg-gray-200"} ${sizeClass[size]}`} />
    </div>
  );
}

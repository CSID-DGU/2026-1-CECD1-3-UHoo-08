import { useNavigate } from "react-router-dom";

interface WishlistButtonProps {
  className?: string;
  style?: React.CSSProperties;
  iconColor?: string;
}

export function WishlistButton({ className, style, iconColor = "white" }: WishlistButtonProps) {
  const navigate = useNavigate();
  return (
    <button
      className={`relative flex h-11 w-11 items-center justify-center rounded-full ${className ?? ""}`}
      style={style}
      onClick={() => navigate("/wishlist")}
      type="button"
      aria-label="찜한 제품"
    >
      <svg fill="none" height="20" viewBox="0 0 24 24" width="20" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M12 21C12 21 3 14.5 3 8.5C3 5.42 5.42 3 8.5 3C10.24 3 11.91 3.81 13 5.08C14.09 3.81 15.76 3 17.5 3C20.58 3 23 5.42 23 8.5C23 14.5 12 21 12 21Z"
          stroke={iconColor}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    </button>
  );
}

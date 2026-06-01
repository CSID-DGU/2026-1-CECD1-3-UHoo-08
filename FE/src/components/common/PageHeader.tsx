import type { ReactNode } from "react";

type PageHeaderProps = {
  title?: string;
  rightSlot?: ReactNode;
  onBack?: () => void;
};

export function PageHeader({ onBack, rightSlot, title }: PageHeaderProps) {
  return (
    <header className="relative flex h-6 items-center justify-center">
      {onBack && (
        <button
          className="absolute left-0 text-h3 text-gray-500"
          onClick={onBack}
          type="button"
          aria-label="뒤로가기"
        >
          ←
        </button>
      )}
      {title && <h1 className="text-body1 text-gray-500">{title}</h1>}
      {rightSlot && <div className="absolute right-0">{rightSlot}</div>}
    </header>
  );
}

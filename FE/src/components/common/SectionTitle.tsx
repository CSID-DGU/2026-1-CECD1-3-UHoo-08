import type { ReactNode } from "react";

type SectionTitleProps = {
  title: string;
  action?: ReactNode;
  description?: string;
  className?: string;
};

export function SectionTitle({ action, className = "", description, title }: SectionTitleProps) {
  return (
    <div className={`flex items-end justify-between gap-3 ${className}`}>
      <div>
        <h2 className="text-body1 text-gray-500">{title}</h2>
        {description && <p className="mt-1 text-caption text-gray-300">{description}</p>}
      </div>
      {action}
    </div>
  );
}

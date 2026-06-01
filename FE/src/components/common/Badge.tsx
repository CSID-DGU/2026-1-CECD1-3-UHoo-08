import type { ReactNode } from "react";

type BadgeProps = {
  children: ReactNode;
  className?: string;
};

export function Badge({ children, className = "" }: BadgeProps) {
  return (
    <span className={`rounded-full bg-primary-100 px-3 py-1 text-caption text-primary-500 ${className}`}>
      {children}
    </span>
  );
}

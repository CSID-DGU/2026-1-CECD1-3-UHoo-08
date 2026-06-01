import type { ButtonHTMLAttributes, ReactNode } from "react";

type PrimaryButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  className?: string;
};

export function PrimaryButton({ children, className = "", type = "button", ...props }: PrimaryButtonProps) {
  return (
    <button
      className={`h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white ${className}`}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}

import { useState } from "react";

type SearchFieldProps = {
  value?: string;
  placeholder?: string;
  editable?: boolean;
  variant?: "filled" | "outlined";
  onClick?: () => void;
  onClear?: () => void;
  onSubmit?: (value: string) => void;
};

export function SearchField({
  editable = false,
  onClear,
  onClick,
  onSubmit,
  placeholder,
  value = "",
  variant = "filled",
}: SearchFieldProps) {
  const [inputValue, setInputValue] = useState(value);

  const colorClass =
    variant === "outlined"
      ? "border border-primary-500 bg-primary-50"
      : "bg-gray-100";

  const SearchIcon = (
    <span className="h-5 w-5 shrink-0 rounded bg-primary-100" />
  );

  if (editable) {
    return (
      <div className={`flex h-12 w-full items-center gap-3 rounded-xl px-4 ${colorClass}`}>
        {SearchIcon}
        <input
          className="min-w-0 flex-1 bg-transparent text-body2 text-gray-500 outline-none placeholder:text-gray-300"
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && onSubmit) onSubmit(inputValue.trim());
          }}
          placeholder={placeholder}
          value={inputValue}
        />
        {inputValue && (
          <span
            className="grid h-6 w-6 shrink-0 cursor-pointer place-items-center rounded-full bg-gray-200 text-gray-300"
            onClick={() => setInputValue("")}
            role="button"
            tabIndex={0}
          >
            ×
          </span>
        )}
      </div>
    );
  }

  return (
    <button
      className={`flex h-12 w-full items-center gap-3 rounded-xl px-4 text-left text-body2 ${colorClass}`}
      onClick={onClick}
      type="button"
    >
      {SearchIcon}
      <span className="min-w-0 flex-1 truncate text-gray-300">
        {placeholder || value}
      </span>
      {onClear && (
        <span
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gray-200 text-gray-300"
          onClick={(e) => {
            e.stopPropagation();
            onClear();
          }}
          role="button"
          tabIndex={0}
        >
          ×
        </span>
      )}
    </button>
  );
}

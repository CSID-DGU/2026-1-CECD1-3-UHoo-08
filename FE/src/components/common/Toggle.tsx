type ToggleProps = {
  checked?: boolean;
};

export function Toggle({ checked = false }: ToggleProps) {
  return (
    <span
      className={`flex h-7 w-12 shrink-0 items-center rounded-full p-1 ${
        checked ? "justify-end bg-primary-500" : "justify-start bg-gray-200"
      }`}
    >
      <span className="h-5 w-5 rounded-full bg-white" />
    </span>
  );
}

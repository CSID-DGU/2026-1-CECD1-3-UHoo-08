type CameraMarkProps = {
  className?: string;
};

export function CameraMark({ className = "" }: CameraMarkProps) {
  return (
    <div className={`flex items-center justify-center rounded-xl bg-primary-100 ${className}`}>
      <div className="flex h-10 w-12 items-center justify-center rounded-lg bg-primary-300">
        <div className="h-5 w-5 rounded-full border-4 border-primary-700" />
      </div>
    </div>
  );
}

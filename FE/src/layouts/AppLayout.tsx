interface AppLayoutProps {
  children: React.ReactNode;
  className?: string;
}

function AppLayout({ children, className = "" }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-100">
      <main
        className={`
          mx-auto min-h-screen w-full max-w-[430px] bg-white page-enter
          ${className}
        `}
      >
        {children}
      </main>
    </div>
  );
}

export default AppLayout;

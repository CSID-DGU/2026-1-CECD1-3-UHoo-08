interface AppLayoutProps {
  children: React.ReactNode;
  className?: string;
}

function AppLayout({ children, className = "" }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-100">
      {/*
        app-safe: 홈 화면 앱으로 실행했을 때 상태 표시줄과 내용이 겹치지
        않게 위쪽만 안전영역만큼 띄운다(index.css). 배경은 그대로 화면 맨
        위까지 올라간다.
      */}
      <main
        className={`
          app-safe mx-auto min-h-screen w-full max-w-[430px] bg-white page-enter
          ${className}
        `}
      >
        {children}
      </main>
    </div>
  );
}

export default AppLayout;

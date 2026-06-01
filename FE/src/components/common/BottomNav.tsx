import { useLocation, useNavigate } from "react-router-dom";

const HomeIcon = ({ active }: { active: boolean }) => (
  <svg fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M3 9.5L12 3L21 9.5V20C21 20.5523 20.5523 21 20 21H15V15H9V21H4C3.44772 21 3 20.5523 3 20V9.5Z"
      fill={active ? "currentColor" : "none"}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
    />
  </svg>
);

const SearchIcon = ({ active }: { active: boolean }) => (
  <svg fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg">
    <circle
      cx="11"
      cy="11"
      fill={active ? "currentColor" : "none"}
      opacity={active ? 0.2 : 1}
      r="7"
      stroke="currentColor"
      strokeWidth="1.8"
    />
    <path d="M16.5 16.5L21 21" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
  </svg>
);

const UserIcon = ({ active }: { active: boolean }) => (
  <svg fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg">
    <circle
      cx="12"
      cy="8"
      fill={active ? "currentColor" : "none"}
      opacity={active ? 0.3 : 1}
      r="4"
      stroke="currentColor"
      strokeWidth="1.8"
    />
    <path
      d="M4 20C4 16.6863 7.58172 14 12 14C16.4183 14 20 16.6863 20 20"
      stroke="currentColor"
      strokeLinecap="round"
      strokeWidth="1.8"
    />
  </svg>
);

export function BottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const homeActive = pathname === "/home";
  const myActive = pathname === "/my";
  const centerActive = pathname.startsWith("/recommendation");

  return (
    <nav className="fixed bottom-0 left-1/2 grid h-[72px] w-full max-w-[430px] -translate-x-1/2 grid-cols-3 items-center border-t border-gray-100 bg-white px-4">
      <button
        className={`mx-auto flex flex-col items-center gap-1 ${homeActive ? "text-primary-500" : "text-gray-300"}`}
        onClick={() => navigate("/home")}
        type="button"
      >
        <HomeIcon active={homeActive} />
        <span className="text-[10px] leading-none">홈</span>
      </button>

      <button
        className={`mx-auto grid h-14 w-14 place-items-center rounded-full shadow-md ${centerActive ? "bg-primary-600" : "bg-primary-500"} text-white`}
        onClick={() => navigate("/recommendation/lookup")}
        type="button"
        aria-label="상품 조회"
      >
        <SearchIcon active={false} />
      </button>

      <button
        className={`mx-auto flex flex-col items-center gap-1 ${myActive ? "text-primary-500" : "text-gray-300"}`}
        onClick={() => navigate("/my")}
        type="button"
      >
        <UserIcon active={myActive} />
        <span className="text-[10px] leading-none">마이페이지</span>
      </button>
    </nav>
  );
}

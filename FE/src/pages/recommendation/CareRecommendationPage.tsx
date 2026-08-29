import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Thermometer } from "lucide-react";
import {
  type CareRecoFull,
  getCareRecommendations,
} from "../../api/careRecoApi";
import { getMyProfile } from "../../api/userApi";
import AppLayout from "../../layouts/AppLayout";

/**
 * 화담 CARE 추천 전체.
 *
 * 홈의 가로 목록은 앞의 몇 개만 보여준다. 여기서는 전부 보여주되 **섞지
 * 않는다.** 확인 결과 이상이 있던 제품의 대체 후보와, 보관 장소별 환경
 * 추천은 근거가 전혀 다르다. 한 줄에 섞으면 왜 추천됐는지가 흐려진다.
 *
 * 제품마다 이유를 한 줄씩 붙이는 것도 같은 이유다. 목록만 보여주면
 * 사용자가 납득할 방법이 없다.
 */
export function CareRecommendationPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<CareRecoFull | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getMyProfile()
      .then((res) => getCareRecommendations(res.data.id))
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  return (
    <AppLayout className="pb-10">
      <header className="flex items-center gap-2 px-4 pt-4 pb-2">
        <button onClick={() => navigate(-1)} type="button" aria-label="뒤로">
          <ChevronLeft className="h-6 w-6 text-gray-500" strokeWidth={1.8} />
        </button>
        <div>
          <h1 className="text-body1 text-gray-500">오늘의 환경 맞춤 추천</h1>
          {data?.context && (
            <p className="text-caption text-gray-300">{data.context}</p>
          )}
        </div>
      </header>

      <div className="px-4">
        {failed ? (
          <Empty text="추천을 불러오지 못했어요" />
        ) : !data ? (
          <Empty text="환경을 확인하는 중이에요" />
        ) : data.groups.length === 0 ? (
          <Empty text="아직 추천할 제품이 없어요" />
        ) : (
          data.groups.map((group) => (
            <section className="mt-5" key={group.key}>
              <h2 className="text-body1 text-gray-500">{group.title}</h2>
              {group.note && (
                <p className="mt-0.5 text-caption text-gray-300">{group.note}</p>
              )}

              <div className="mt-2 flex flex-col gap-2">
                {group.items.map((item) => (
                  <button
                    className="flex gap-3 rounded-2xl border border-gray-100 bg-white p-3 text-left"
                    key={`${group.key}:${item.product_id}`}
                    onClick={() => navigate(`/product/${item.product_id}`)}
                    type="button"
                  >
                    <div className="h-[72px] w-[72px] shrink-0 overflow-hidden rounded-xl bg-primary-50">
                      {item.image_url && (
                        <img
                          src={item.image_url}
                          alt={item.name}
                          className="h-full w-full object-cover"
                        />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body2 text-gray-500">
                        {item.name}
                      </p>
                      <p className="mt-0.5 truncate text-caption text-gray-300">
                        {item.brand}
                        {item.price != null &&
                          ` · ${item.price.toLocaleString()}원`}
                      </p>
                      {/* 이 한 줄이 이 화면의 핵심이다. 왜 이 제품인지. */}
                      <p className="mt-1.5 text-caption leading-[1.5] text-primary-600">
                        {item.reason}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </AppLayout>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div
      className="mt-5 flex h-[120px] flex-col items-center justify-center gap-2 rounded-2xl"
      style={{ background: "#F0F5FD", border: "1px dashed #C5DDF5" }}
    >
      <Thermometer className="h-7 w-7 text-primary-300" strokeWidth={1.5} />
      <p className="text-caption text-gray-300">{text}</p>
    </div>
  );
}

export default CareRecommendationPage;

# Cosmetics Recommender AI

> AI 기반 화장품 추천 시스템 — 사용자의 피부 타입, 퍼스널 컬러, 단기 취향을 결합해 화장품을 추천합니다.

본 프로젝트는 사용자가 상품 이미지를 촬영하거나 URL을 입력하면, **VLM이 상품 정보를 추출**하고, **LLM이 가격·리뷰·성분을 분석**한 뒤, **벡터 DB 기반 협업 필터링과 콘텐츠 기반 추천**을 통해 개인화된 결과를 제공하는 시스템입니다.

장기 취향(피부 타입, 퍼스널 컬러)과 단기 취향(트렌드, 계절감)을 함께 반영하며, RAG를 활용해 추천 근거를 자연어로 설명합니다.

---

## 팀 구성

| 이름 | 역할 |
|------|------|
|      |      |
|      |      |
|      |      |
|      |      |

---

## 기술 스택

| 분야 | 사용 기술 |
|------|----------|
| AI Server | Python 3.11+, FastAPI |
| Database | Supabase Cloud (PostgreSQL 16 + pgvector) |
| LLM | Ollama, EXAONE 3.5, Qwen 2.5, Llama 3.1 |
| VLM | Qwen2-VL, Llama 3.2 Vision |
| Embedding | bge-m3, Ko-SRoBERTa |
| Backend | _TBD_ |
| Frontend | _TBD_ |
| Infra | Docker, Docker Compose |

---

## 레포지토리 구조

```
DGU-Capston1/
├── AI/                                  # Python FastAPI 단일 프로젝트
│   ├── main.py                          # FastAPI 앱 진입점
│   ├── config.py                        # 환경변수 (API 키, Supabase URL 등)
│   ├── api/
│   │   └── internal/                    # Spring 전용 내부 라우터
│   │       ├── recognize_router.py      # POST /internal/recognize
│   │       └── agent_router.py          # POST /internal/agent/run
│   ├── graph/                           # LangGraph 오케스트레이션
│   │   ├── action_model.py              # create_react_agent + @tool 등록 진입점
│   │   └── state.py                     # AgentState TypedDict
│   ├── agents/                          # 에이전트 모듈 (각 @tool)
│   │   ├── input_agent/                 # IMAGE/NFC/TEXT → ExtractedProduct
│   │   │   ├── image_parser.py
│   │   │   ├── nfc_parser.py
│   │   │   └── text_parser.py
│   │   ├── product_agent/               # DB 조회 + stale 시 Gemini 보강
│   │   │   ├── product_repository.py
│   │   │   └── gemini_enricher.py
│   │   ├── discovery_agent.py           # 자연어 → intent_vector → 후보 탐색
│   │   ├── score_agent/                 # 4요소 점수 → 0~100점
│   │   │   ├── budget_scorer.py
│   │   │   ├── price_scorer.py
│   │   │   ├── review_scorer.py
│   │   │   └── personalization_scorer.py
│   │   ├── alternative_agent.py         # pgvector 유사도 → 대체 상품
│   │   └── collaborative_agent/         # 협업 필터링 + 콜드스타트 폴백
│   │       └── fallback.py
│   ├── services/                        # 공통 서비스
│   │   ├── embedding_service.py         # bge-m3 임베딩
│   │   ├── unified_text_builder.py      # query + profile + RAG → 통합 자연어
│   │   ├── job_updater.py               # recommendation_jobs step/progress 업데이트
│   │   └── weight_validator.py
│   ├── db/                              # Supabase + pgvector
│   │   ├── supabase_client.py
│   │   ├── vector_search.py             # RPC 래퍼 (match_products 등)
│   │   └── migrations/                  # 마이그레이션 SQL
│   ├── models/                          # Pydantic 모델
│   │   ├── extracted_product.py
│   │   ├── product_response.py
│   │   ├── agent_context.py
│   │   └── recommendation_result.py
│   ├── prompts/                         # LLM 시스템 프롬프트
│   │   ├── gemini_extraction.py
│   │   ├── weight_adjustment.py
│   │   └── collaborative_strategy.py
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── BE/                                  # Spring Boot 백엔드
│   ├── src/main/java/com/beautymatch/
│   │   ├── BeautyMatchApplication.java
│   │   ├── common/
│   │   │   ├── config/
│   │   │   │   ├── SecurityConfig.java          # JWT 필터체인, CORS 설정
│   │   │   │   ├── WebClientConfig.java         # FastAPI 호출용 WebClient 빈
│   │   │   │   └── JpaConfig.java               # AuditingEntityListener
│   │   │   ├── exception/
│   │   │   │   ├── GlobalExceptionHandler.java  # @RestControllerAdvice
│   │   │   │   ├── ErrorCode.java               # Enum (PRODUCT_NOT_FOUND 등)
│   │   │   │   └── BusinessException.java
│   │   │   ├── response/
│   │   │   │   └── ApiResponse.java             # { success, data, meta }
│   │   │   └── util/
│   │   │       └── JwtUtil.java
│   │   ├── domain/
│   │   │   ├── auth/                        # 인증 (로그인·회원가입·토큰)
│   │   │   │   ├── controller/
│   │   │   │   │   └── AuthController.java          # POST /auth/login, /signup, /social, /token/refresh
│   │   │   │   ├── service/
│   │   │   │   │   ├── AuthService.java
│   │   │   │   │   └── OAuthService.java            # Kakao / Google / Apple 토큰 교환
│   │   │   │   ├── dto/
│   │   │   │   │   ├── LoginRequest.java
│   │   │   │   │   ├── SignupRequest.java
│   │   │   │   │   ├── SocialLoginRequest.java      # { provider, accessToken, fcmToken }
│   │   │   │   │   └── TokenResponse.java
│   │   │   │   └── repository/
│   │   │   │       └── UserRepository.java
│   │   │   ├── user/                        # 사용자 정보·피부·통계
│   │   │   │   ├── controller/
│   │   │   │   │   └── UserController.java          # GET /users/me, PATCH /users/me, /skin-profile
│   │   │   │   ├── service/
│   │   │   │   │   ├── UserService.java
│   │   │   │   │   └── UserProfileService.java
│   │   │   │   ├── entity/
│   │   │   │   │   ├── User.java
│   │   │   │   │   ├── UserProfile.java
│   │   │   │   │   └── UserBrandPreference.java
│   │   │   │   ├── dto/
│   │   │   │   │   ├── UserResponse.java
│   │   │   │   │   ├── SkinProfileRequest.java
│   │   │   │   │   └── PreferencesRequest.java
│   │   │   │   └── repository/
│   │   │   │       ├── UserProfileRepository.java
│   │   │   │       └── UserBrandPreferenceRepository.java
│   │   │   ├── product/                     # 상품 조회 (읽기 전용. FastAPI가 write)
│   │   │   │   ├── controller/
│   │   │   │   │   ├── ProductController.java       # GET /products, /products/{id}
│   │   │   │   │   └── ProductRecognizeController.java # POST /products/recognize → FastAPI 위임
│   │   │   │   ├── service/
│   │   │   │   │   ├── ProductQueryService.java     # DB 조회 + 응답 조합
│   │   │   │   │   └── ProductRecognizeService.java # FastAPI 동기 호출
│   │   │   │   ├── entity/
│   │   │   │   │   └── Product.java
│   │   │   │   ├── dto/
│   │   │   │   │   ├── ProductResponse.java         # 상품 상세 응답 (geminiPrice, matchScore 포함)
│   │   │   │   │   ├── ProductListResponse.java
│   │   │   │   │   └── RecognizeResponse.java
│   │   │   │   └── repository/
│   │   │   │       └── ProductRepository.java
│   │   │   ├── wishlist/                    # 찜 목록
│   │   │   │   ├── controller/
│   │   │   │   │   └── WishlistController.java      # GET / POST / DELETE /users/me/wishlists
│   │   │   │   ├── service/
│   │   │   │   │   └── WishlistService.java
│   │   │   │   ├── entity/
│   │   │   │   │   └── Wishlist.java
│   │   │   │   ├── dto/
│   │   │   │   │   └── WishlistResponse.java
│   │   │   │   └── repository/
│   │   │   │       └── WishlistRepository.java
│   │   │   ├── registered/                  # 등록 제품 (온보딩용)
│   │   │   │   ├── controller/
│   │   │   │   │   └── RegisteredProductController.java
│   │   │   │   ├── service/
│   │   │   │   │   └── RegisteredProductService.java
│   │   │   │   ├── entity/
│   │   │   │   │   └── RegisteredProduct.java
│   │   │   │   └── repository/
│   │   │   │       └── RegisteredProductRepository.java
│   │   │   ├── recommendation/              # 에이전트 요청·상태 관리
│   │   │   │   ├── controller/
│   │   │   │   │   └── RecommendationController.java  # POST /recommendations, GET /recommendations/{jobId}, /status
│   │   │   │   ├── service/
│   │   │   │   │   ├── RecommendationService.java   # job INSERT + FastAPI 비동기 위임
│   │   │   │   │   └── AgentClient.java             # WebClient 래퍼: POST /internal/agent/run
│   │   │   │   ├── entity/
│   │   │   │   │   └── RecommendationJob.java
│   │   │   │   ├── dto/
│   │   │   │   │   ├── RecommendationRequest.java
│   │   │   │   │   ├── RecommendationStatusResponse.java
│   │   │   │   │   └── RecommendationResultResponse.java
│   │   │   │   └── repository/
│   │   │   │       └── RecommendationJobRepository.java
│   │   │   ├── pricetracking/               # 가격 추적
│   │   │   │   ├── controller/
│   │   │   │   │   └── PriceTrackingController.java # GET/POST/PATCH/DELETE /users/me/price-trackings, /history, /alert-settings
│   │   │   │   ├── service/
│   │   │   │   │   ├── PriceTrackingService.java
│   │   │   │   │   └── PriceAlertService.java       # FCM 푸시 알림 속도 로직
│   │   │   │   ├── entity/
│   │   │   │   │   ├── PriceTracking.java
│   │   │   │   │   └── PriceTrackingAlertSettings.java
│   │   │   │   ├── dto/
│   │   │   │   │   ├── PriceTrackingResponse.java
│   │   │   │   │   ├── PriceHistoryResponse.java
│   │   │   │   │   └── AlertSettingsRequest.java
│   │   │   │   └── repository/
│   │   │   │       ├── PriceTrackingRepository.java
│   │   │   │       └── PriceTrackingAlertSettingsRepository.java
│   │   │   └── notification/                # 알림
│   │   │       ├── controller/
│   │   │       │   └── NotificationController.java  # GET /users/me/notifications, PATCH 읽음
│   │   │       ├── service/
│   │   │       │   ├── NotificationService.java
│   │   │       │   └── FcmService.java              # Firebase Admin SDK 래퍼
│   │   │       ├── entity/
│   │   │       │   └── Notification.java
│   │   │       ├── dto/
│   │   │       │   └── NotificationResponse.java
│   │   │       └── repository/
│   │   │           └── NotificationRepository.java
│   └── src/main/resources/
│       ├── application.yml
│       ├── application-local.yml
│       └── application-prod.yml
├── FE/                                  # 모바일 앱 프론트엔드
├── .gitignore
├── LICENSE
└── README.md
```

---

## AI

## 시작하기

### 사전 요구사항

- Git, Docker, Docker Compose
- Python 3.11+ (AI 모듈 로컬 작업 시)

### 설치 및 실행

```bash
# 1. 레포 클론
git clone https://github.com/kelly0819/DGU-Capston1.git
cd DGU-Capston1

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일을 본인 환경에 맞게 수정

# 3. AI 모듈 실행
cd AI
docker compose up -d
```

> ⚠️ `.env` 와 `venv/` 는 절대 커밋하지 마세요.

---
## Backend 

## 시작하기

### 사전 요구사항

- Git, Docker, Docker Compose

### 설치 및 실행

```bash                                                                                           
  # 1. 레포 클론 (이미 클론했다면 생략)                                                               
  git clone https://github.com/kelly0819/DGU-Capston1.git   
  cd DGU-Capston1/BE
  # 2. BE/docker-compose.yml 파일 생성
  내용은 노션에 있습니다.                                                                                 
                    
  # 3. 빌드 및 실행 (최초 실행 또는 코드 변경 후)                                                     
  docker compose up --build -d                              
                                                                                                      
  # 이후 재실행 시 (코드 변경 없을 때)                      
  docker compose up -d                                                                                
                                                                                                      
  ▎ 최초 빌드는 내부에서 Gradle 빌드가 함께 진행되므로 5~10분 소요됩니다.                           
                                                                                       
 ---
  Swagger 접속

  서버 실행 후 아래 주소로 접속합니다.

  http://localhost:8080/swagger-ui.html

  ---
  로그 확인 / 종료

  # 로그 확인
  docker compose logs -f

  # 서버 종료
  docker compose down

---

## 개발 컨벤션

### 1. 브랜치 전략

```
main (시연·발표 가능한 안정 버전)
 ↑   ← develop → main PR (마일스톤 시점)
 │
develop (모든 개발 작업의 통합 브랜치)
 ↑   ← 작업 브랜치 → develop PR
 │
 ├── feature/vectordb-product-upsert
 ├── fix/login-crash
 └── docs/readme-update
```

#### 브랜치 역할

| 브랜치 | 역할 |
|--------|------|
| `main` | 시연·발표 가능한 안정 상태. 마일스톤 시점에만 머지됨 |
| `develop` | 모든 개발 작업의 통합 지점. 항상 CI 통과 상태 유지 |
| `feature/*`, `fix/*` 등 | 개인 작업 브랜치. `develop`에서 분기 |
| `hotfix/*` | `main` 긴급 수정용. `main`에서 분기 후 `main`과 `develop` 양쪽에 반영 |

#### 브랜치 명명 규칙

```
<type>/<짧은-설명>
```

| Type | 용도 | 베이스 |
|------|------|--------|
| `feature` | 새 기능 개발 | `develop` |
| `fix` | 버그 수정 | `develop` |
| `refactor` | 기능 변화 없는 리팩토링 | `develop` |
| `docs` | 문서 작업 | `develop` |
| `chore` | 빌드, 설정, 의존성 | `develop` |
| `test` | 테스트 추가/수정 | `develop` |
| `hotfix` | 긴급 버그 수정 | `main` |

#### 작업 흐름

```bash
# develop에서 분기
git checkout develop
git pull origin develop
git checkout -b feature/my-task

# 작업, 커밋, 푸시
git add .
git commit -m "feat: 기능 추가"
git push -u origin feature/my-task

# GitHub에서 develop 대상으로 PR 생성
```

#### 브랜치 규칙

- `main`과 `develop`으로의 **직접 푸시 금지** (PR 필수)
- 머지 후 작업 브랜치 **즉시 삭제**
- 작업 브랜치는 **3~5일 이내로 짧게** 유지
- 작업 도중 `develop`이 갱신되면 자주 동기화:

```bash
git fetch origin
git rebase origin/develop
```

---

### 2. 커밋 메시지 규칙

[Conventional Commits](https://www.conventionalcommits.org/ko/) 형식을 따릅니다.

#### 형식

```
<type>: <subject>
```

#### Type

| Type | 설명 |
|------|------|
| `feat` | 새 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 코드 의미에 영향 없는 변경 (포매팅, 세미콜론 등) |
| `refactor` | 기능 변화 없는 코드 리팩토링 |
| `perf` | 성능 개선 |
| `test` | 테스트 코드 추가/수정 |
| `chore` | 빌드, 패키지, 설정 등 |

---

### 3. Pull Request

코드 리뷰의 대부분은 **`develop` 대상 PR**에서 이루어집니다. `main` 대상 PR은 마일스톤 시점의 통합 점검 성격입니다.

| PR 방향 | 시점 | 리뷰 | 머지 전략 |
|---------|------|------|----------|
| 작업 브랜치 → `develop` | 상시 | **1명 승인** (코드 리뷰) | **Squash and merge** |
| `develop` → `main` | 마일스톤 (MVP/중간/최종 발표 등) | **전원 승인** (릴리스 점검) | **Merge commit** |

#### 공통 규칙

- CI 통과 후 머지 가능
- 머지 후 작업 브랜치 자동 삭제
- `main`, `develop` 으로의 직접 푸시 금지 (PR 필수)

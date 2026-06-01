import { createBrowserRouter } from "react-router-dom";
import { AuthGuard } from "./components/common/AuthGuard";
import { LoginPage } from "./pages/auth/LoginPage";
import { KakaoCallbackPage } from "./pages/auth/KakaoCallbackPage";
import { ProfileSetupPage } from "./pages/onboarding/ProfileSetupPage";
import { PreferenceSetupPage } from "./pages/onboarding/PreferenceSetupPage";
import { KnownProductSetupPage } from "./pages/onboarding/KnownProductSetupPage";
import { PhotoRegisterPage } from "./pages/onboarding/PhotoRegisterPage";
import { ProductSearchSetupPage } from "./pages/onboarding/ProductSearchSetupPage";
import { SearchEmptyPage } from "./pages/onboarding/SearchEmptyPage";
import { OnboardingCompletePage } from "./pages/onboarding/OnboardingCompletePage";
import { HomePage } from "./pages/home/HomePage";
import { SearchResultPage } from "./pages/search/SearchResultPage";
import { ProductDetailPage } from "./pages/product/ProductDetailPage";
import { ProductRecognizePage } from "./pages/product/ProductRecognizePage";
import { NotificationPage } from "./pages/notification/NotificationPage";
import { ProductLookupPage } from "./pages/recommendation/ProductLookupPage";
import { NfcScanPage } from "./pages/recommendation/NfcScanPage";
import { ExtraInfoPage } from "./pages/recommendation/ExtraInfoPage";
import { RecommendationLoadingPage } from "./pages/recommendation/RecommendationLoadingPage";
import { RecommendationResultPage } from "./pages/recommendation/RecommendationResultPage";
import { MyPage } from "./pages/my/MyPage";
import { ProfileEditPage } from "./pages/my/ProfileEditPage";
import { SkinInfoEditPage } from "./pages/my/SkinInfoEditPage";
import { SettingsPage } from "./pages/my/SettingsPage";
import { FavoriteTrackingPage } from "./pages/my/FavoriteTrackingPage";
import { FavoriteProductsPage } from "./pages/my/FavoriteProductsPage";
import { PriceTrackingAddPage } from "./pages/priceTracking/PriceTrackingAddPage";
import { PriceHistoryPage } from "./pages/priceTracking/PriceHistoryPage";

export const router = createBrowserRouter([
  // 인증 불필요
  { path: "/", element: <LoginPage /> },
  { path: "/auth/social", element: <KakaoCallbackPage /> },

  // 인증 필요
  {
    element: <AuthGuard />,
    children: [
      { path: "/onboarding/profile", element: <ProfileSetupPage /> },
      { path: "/onboarding/preference", element: <PreferenceSetupPage /> },
      { path: "/onboarding/products", element: <KnownProductSetupPage /> },
      { path: "/onboarding/photo", element: <PhotoRegisterPage /> },
      { path: "/onboarding/product-search", element: <ProductSearchSetupPage /> },
      { path: "/onboarding/search-empty", element: <SearchEmptyPage /> },
      { path: "/onboarding/complete", element: <OnboardingCompletePage /> },
      { path: "/home", element: <HomePage /> },
      { path: "/search", element: <SearchResultPage /> },
      { path: "/product/recognize", element: <ProductRecognizePage /> },
      { path: "/product/:productId", element: <ProductDetailPage /> },
      { path: "/notifications", element: <NotificationPage /> },
      { path: "/recommendation/lookup", element: <ProductLookupPage /> },
      { path: "/recommendation/nfc-scan", element: <NfcScanPage /> },
      { path: "/recommendation/extra-info", element: <ExtraInfoPage /> },
      { path: "/recommendation/loading", element: <RecommendationLoadingPage /> },
      { path: "/recommendation/result", element: <RecommendationResultPage /> },
      { path: "/my", element: <MyPage /> },
      { path: "/my/profile", element: <ProfileEditPage /> },
      { path: "/my/skin", element: <SkinInfoEditPage /> },
      { path: "/my/settings", element: <SettingsPage /> },
      { path: "/favorites", element: <FavoriteTrackingPage /> },
      { path: "/favorites/products", element: <FavoriteProductsPage /> },
      { path: "/price-tracking/add", element: <PriceTrackingAddPage /> },
      { path: "/price-tracking/:productId", element: <PriceHistoryPage /> },
    ],
  },
]);

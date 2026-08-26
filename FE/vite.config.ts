import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(), 
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      // 키오스크용 manifest는 /kiosk 페이지에서 런타임에 갈아끼운다.
      // 프리캐시에 포함시켜야 오프라인에서도 홈 화면 추가가 동작한다.
      includeAssets: ["favicon.svg", "apple-touch-icon.png", "kiosk.webmanifest"],
      manifest: {
        name: "화담(HWADAM) — 스마트 화장품 보관 관리 및 추천",
        short_name: "화담",
        description: "센서로 보관 환경을 감지를 통한 화장품 상태 관리 및 화장품 추천 서비스",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#ffffff",
        theme_color: "#E8E4FF",
        lang: "ko",
        icons: [
          { src: "/pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "/pwa-512x512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/pwa-maskable-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2,webmanifest}"],
        // Spline 3D 번들이 2MB를 넘어 기본 한도(2MiB)에 걸린다
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [
          {
            // 구글 폰트는 오래 캐싱해도 안전하다
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\//,
            handler: "CacheFirst",
            options: {
              cacheName: "google-fonts",
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  server: {
    proxy: {
      "/auth": {
        target: "http://localhost:8080",
        changeOrigin: true,
        bypass: (req) => {
          if (req.method === "GET") return req.url;
        },
      },
      "/products": "http://localhost:8080",
      "/recommendations": "http://localhost:8080",
      "/users": "http://localhost:8080",
      "/notifications": "http://localhost:8080",
      "/onboarding": "http://localhost:8080",
      "/wishlists": "http://localhost:8080",
      "/wishlist": "http://localhost:8080",
      "/price-trackings": "http://localhost:8080",
      "/price-tracking": "http://localhost:8080",
      "/ai": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai/, ""),
      },
    },
  },
});

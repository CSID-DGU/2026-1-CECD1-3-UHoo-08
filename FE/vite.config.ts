import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

/**
 * dev 서버에서도 /kiosk 가 kiosk.html 을 받게 한다.
 * 배포에서는 vercel.json의 rewrite가 같은 일을 한다. 둘을 맞춰두지 않으면
 * 로컬에서 확인한 화면과 아이패드에서 열리는 화면이 달라진다.
 */
function kioskDevEntry(): Plugin {
  return {
    name: "kiosk-dev-entry",
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        const url = req.url ?? "";
        // /kiosk.webmanifest 같은 실제 파일은 건드리지 않는다.
        if (url === "/kiosk" || url === "/kiosk/" || url.startsWith("/kiosk?")) {
          req.url = "/kiosk.html" + url.slice(url.indexOf("?") === -1 ? url.length : url.indexOf("?"));
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    kioskDevEntry(),
    VitePWA({
      registerType: "autoUpdate",
      // 키오스크용 manifest는 kiosk.html이 직접 선언한다.
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
        // /kiosk 는 Vercel rewrite로 kiosk.html을 받는다. 서비스워커가
        // navigateFallback(index.html)로 가로채면 앱 셸이 떠버린다.
        navigateFallbackDenylist: [/^\/api/, /^\/kiosk/],
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
  build: {
    rollupOptions: {
      // 앱과 키오스크는 엔트리를 나눈다. 키오스크는 react-router를 쓰지
      // 않고 화면 하나만 그리므로 앱 번들을 함께 받을 이유가 없다.
      input: {
        main: "index.html",
        kiosk: "kiosk.html",
      },
    },
  },
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

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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

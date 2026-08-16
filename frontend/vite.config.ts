/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    watch: {
      // Docker/WSL 等 bind mount 场景下 inotify 事件可能不可靠，
      // 设 VITE_WATCH_POLLING=true（compose 开发覆盖文件已设置）时改为轮询，
      // 保证容器内前端源码改动能稳定触发 HMR。
      usePolling: process.env.VITE_WATCH_POLLING === "true",
    },
  },
  build: {
    // 不需要 Vite 在构建时计算 gzip 体积：dist 已由 precompress 脚本
    // 生成 .gz 文件，关闭可减少构建期内存与耗时。
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        // 三方库按更新频率拆成两组：React 运行时与路由库独立缓存，
        // 避免升级任一库时另一部分也一起失效。
        manualChunks(id) {
          if (
            id.includes("node_modules/react/") ||
            id.includes("node_modules/react-dom/")
          ) {
            return "react-vendor";
          }
          if (
            id.includes("node_modules/react-router") ||
            id.includes("node_modules/react-router-dom")
          ) {
            return "router-vendor";
          }
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});

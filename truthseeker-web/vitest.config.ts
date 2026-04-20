import path from "node:path"

import { defineConfig } from "vitest/config"

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  server: {
    host: "127.0.0.1",
  },
  test: {
    environment: "node",
    globals: true,
  },
})

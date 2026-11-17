import type { NextConfig } from "next";

const api = (process.env.QUIZFORGE_API_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const config: NextConfig = {
  poweredByHeader: false,
  experimental: { proxyTimeout: 55000 },
  async rewrites() {
    return ["health", "quizzes/generate", "quizzes/grade"].map(path => ({
      source: `/api/${path}`, destination: `${api}/api/${path}`,
    }));
  },
};
export default config;

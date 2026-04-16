import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    serverActions: {
      allowedOrigins: ["localhost:3000"],
    },
  },
  transpilePackages: ["echarts", "zrender"],
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "xtzravihjspffqpxqzwe.supabase.co" },
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },
};

export default nextConfig;

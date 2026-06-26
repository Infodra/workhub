import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "export",   // Generates a fully static site — no Node.js server needed
  trailingSlash: true, // Required for static hosting (Azure SWA, Vercel, Cloudflare)
};

export default nextConfig;

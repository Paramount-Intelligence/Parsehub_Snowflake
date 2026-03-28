/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
    NEXT_PUBLIC_BACKEND_API_KEY: process.env.NEXT_PUBLIC_BACKEND_API_KEY,
  },

  /**
   * Rewrite /api/:path* → backend /api/:path*
   *
   * IMPORTANT: Do NOT rewrite batch endpoints. They have local route handlers in:
   * - app/api/projects/batch/*
   * - app/api/projects/[token]/batch/*
   * - app/api/projects/[token]/checkpoint
   *
   * Route handlers are matched before rewrites, so these paths bypass rewrites.
   * The route handlers use proxyToBackend() to forward to Flask as needed.
   *
   * Only rewrite paths without local route handlers.
   */
  async rewrites() {
    const backend =
      process.env.NEXT_PUBLIC_BACKEND_URL ||
      process.env.BACKEND_URL ||
      process.env.BACKEND_API_URL ||
      '';

    if (!backend) {
      console.warn(
        '[next.config] NEXT_PUBLIC_BACKEND_URL is not set — /api/* rewrites disabled. ' +
        'Set NEXT_PUBLIC_BACKEND_URL in Railway → frontend service → Variables.'
      );
      return [];
    }

    const base = backend.replace(/\/$/, '');

    return [
      {
        source: '/api/:path*',
        destination: `${base}/api/:path*`,
      },
    ];
  },

  typescript: {
    ignoreBuildErrors: true,
  },
};

module.exports = nextConfig;

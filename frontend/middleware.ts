import { NextRequest, NextResponse } from 'next/server';

/**
 * Middleware to handle routing logic before rewrites/handlers.
 * 
 * This middleware ensures that batch endpoints and token-specific handlers
 * are NOT intercepted by rewrites. Batch operations have local route handlers
 * that use proxyToBackend() to forward to Flask.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check if this is a batch endpoint that should be handled locally
  const isBatchPath = 
    pathname.startsWith('/api/projects/batch/') ||
    pathname.includes('/api/projects/') && pathname.includes('/batch/') ||
    pathname.includes('/api/projects/') && pathname.includes('/checkpoint');

  if (isBatchPath) {
    // Don't rewrite batch paths - let the route handler process them
    // Return undefined to continue to default routing (handlers)
    return undefined;
  }

  // Allow rewrites to handle other API paths
  return undefined;
}

export const config = {
  matcher: [
    // Match all API routes
    '/api/:path*',
  ],
};

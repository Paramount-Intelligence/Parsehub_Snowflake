import { NextRequest } from 'next/server';
import { proxyToBackend } from '../_proxy';

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const params = new URLSearchParams();

  // Forward all query params the UI sends
  for (const [key, value] of sp.entries()) params.append(key, value);

  // Defaults
  if (!params.has('page')) params.set('page', '1');
  if (!params.has('limit')) params.set('limit', '50');

  // Add ParseHub API key (server-side only, never exposed to browser)
  const apiKey = process.env.PARSEHUB_API_KEY;
  if (apiKey && !params.has('api_key')) {
    params.set('api_key', apiKey);
  }

  return proxyToBackend(request, '/api/projects', params);
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/api/projects');
}

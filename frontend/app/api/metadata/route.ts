import { getApiBaseUrl } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = getApiBaseUrl();
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 't_hmXetfMCq3';
const REQUEST_TIMEOUT = 30000; // 30 seconds timeout

/**
 * GET /api/metadata
 * Fetches metadata records with optional filtering
 * Proxies to Flask backend: GET /api/metadata
 */
export async function GET(request: NextRequest) {
  try {
    // Extract query parameters
    const searchParams = request.nextUrl.searchParams;
    const projectToken = searchParams.get('project_token');
    const region = searchParams.get('region');
    const country = searchParams.get('country');
    const brand = searchParams.get('brand');
    const limit = searchParams.get('limit') || '100';
    const offset = searchParams.get('offset') || '0';

    // Build backend URL
    const params = new URLSearchParams();
    if (projectToken) params.append('project_token', projectToken);
    if (region) params.append('region', region);
    if (country) params.append('country', country);
    if (brand) params.append('brand', brand);
    params.append('limit', limit);
    params.append('offset', offset);

    const backendUrl = `${BACKEND_URL}/api/metadata?${params.toString()}`;

    console.log(`[API] GET /api/metadata - Proxying to: ${backendUrl}`);

    // Call Flask backend with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    
    try {
      const response = await fetch(backendUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      
      const data = await response.json();

      if (!response.ok) {
        console.error(`[API] Backend returned ${response.status}:`, data);
        return NextResponse.json(
          { error: data.error || 'Failed to fetch metadata' },
          { status: response.status }
        );
      }

      console.log(`[API] Successfully fetched ${data.count} metadata records`);
      return NextResponse.json(data, { status: 200 });
    } finally {
      clearTimeout(timeoutId);
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.error('[API] Metadata request timeout (30s exceeded)');
      return NextResponse.json(
        { error: 'Metadata request timeout' },
        { status: 504 }
      );
    }
    console.error('[API] Error fetching metadata:', error);
    return NextResponse.json(
      { error: 'Failed to fetch metadata', details: String(error) },
      { status: 500 }
    );
  }
}

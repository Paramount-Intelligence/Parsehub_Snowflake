import { getApiBaseUrl } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = getApiBaseUrl();
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 't_hmXetfMCq3';

/**
 * GET /api/projects/search
 * Searches projects from database with optional filtering
 * Query parameters: region, country, brand, limit, offset
 * Proxies to Flask backend: GET /api/projects/search
 */
export async function GET(request: NextRequest) {
  try {
    // Extract query parameters
    const searchParams = request.nextUrl.searchParams;
    const region = searchParams.get('region');
    const country = searchParams.get('country');
    const brand = searchParams.get('brand');
    const website = searchParams.get('website');
    const groupByWebsite = searchParams.get('group_by_website');
    const limit = searchParams.get('limit') || '100';
    const offset = searchParams.get('offset') || '0';

    // Build backend URL with query params
    const params = new URLSearchParams();
    if (region) params.append('region', region);
    if (country) params.append('country', country);
    if (brand) params.append('brand', brand);
    if (website) params.append('website', website);
    if (groupByWebsite) params.append('group_by_website', groupByWebsite);
    params.append('limit', limit);
    params.append('offset', offset);

    const backendUrl = `${BACKEND_URL}/api/projects/search?${params.toString()}`;

    console.log(`[API] GET /api/projects/search - Proxying to: ${backendUrl}`);

    // Create abort controller for 300 second timeout (5 minutes)
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 300000);

    // Call Flask backend
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      },
      signal: abortController.signal,
    }).finally(() => clearTimeout(timeoutId));

    const data = await response.json();

    if (!response.ok) {
      console.error(`[API] Backend returned ${response.status}:`, data);
      return NextResponse.json(
        { error: data.error || 'Failed to search projects' },
        { status: response.status }
      );
    }

    console.log(`[API] Successfully searched projects - ${data.projects?.length} results`);
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error('[API] Error searching projects:', error);
    return NextResponse.json(
      { error: 'Failed to search projects', details: String(error) },
      { status: 500 }
    );
  }
}

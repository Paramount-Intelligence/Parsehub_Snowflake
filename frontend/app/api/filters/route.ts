import { getApiBaseUrl } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = getApiBaseUrl();
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || 't_hmXetfMCq3';

/**
 * GET /api/filters
 * Get all available filters (regions, countries, brands, websites)
 * OR GET /api/filters?field=region|country|brand for individual filter values
 */
export async function GET(request: NextRequest) {
  try {
    const field = request.nextUrl.searchParams.get('field');

    // If field is specified, get individual filter values
    if (field) {
      const backendUrl = `${BACKEND_URL}/api/filters/values?field=${encodeURIComponent(field)}`;
      console.log(`[API] Getting filter values for field: ${field}`);

      const response = await fetch(backendUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${BACKEND_API_KEY}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        console.error(`[API] Backend returned ${response.status}:`, data);
        return NextResponse.json(
          { error: data.error || 'Failed to fetch filter values' },
          { status: response.status }
        );
      }

      console.log(`[API] Successfully fetched ${data.values?.length || 0} filter values for ${field}`);
      return NextResponse.json(data, { status: 200 });
    }

    // Otherwise get all filters (regions, countries, brands, websites)
    const backendUrl = `${BACKEND_URL}/api/filters`;
    console.log('[API] Getting all filter options');

    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${BACKEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    if (!response.ok) {
      console.error(`[API] Backend returned ${response.status}:`, data);
      return NextResponse.json(
        { error: data.error || 'Failed to fetch filters' },
        { status: response.status }
      );
    }

    console.log('[API] Successfully fetched all filters');
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error('[API] Error fetching filters:', error);
    return NextResponse.json(
      { error: 'Failed to fetch filters', details: String(error) },
      { status: 500 }
    );
  }
}

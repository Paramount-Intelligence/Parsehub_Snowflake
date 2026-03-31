import { NextResponse } from 'next/server';
import { getApiBaseUrl, getApiHeaders } from '@/lib/apiBase';

/**
 * GET /api/scraped-records/ingest/status
 * Proxies to Flask: GET /api/scraped-records/ingest/status
 */
export async function GET() {
  try {
    const backendUrl = `${getApiBaseUrl()}/api/scraped-records/ingest/status`;
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: getApiHeaders(),
    });

    const contentType = response.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
      const text = await response.text();
      return NextResponse.json(
        { error: text.slice(0, 200) || 'Backend returned non-JSON' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[API] scraped-records/ingest/status:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Status request failed' },
      { status: 500 }
    );
  }
}

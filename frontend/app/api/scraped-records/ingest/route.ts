import { NextRequest, NextResponse } from 'next/server';
import { getApiBaseUrl, getApiHeaders } from '@/lib/apiBase';

/**
 * POST /api/scraped-records/ingest
 * Proxies to Flask: POST /api/scraped-records/ingest (202 + job_id)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const backendUrl = `${getApiBaseUrl()}/api/scraped-records/ingest`;
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getApiHeaders(),
      },
      body: JSON.stringify(body),
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
    console.error('[API] scraped-records/ingest:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Ingest request failed' },
      { status: 500 }
    );
  }
}

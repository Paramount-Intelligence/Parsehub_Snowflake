import { getApiBaseUrl } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = getApiBaseUrl();
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 't_hmXetfMCq3';

/**
 * POST /api/projects/sync
 * Syncs projects from ParseHub API to database
 * Proxies to Flask backend: POST /api/projects/sync
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));

    const backendUrl = `${BACKEND_URL}/api/projects/sync`;

    console.log(`[API] POST /api/projects/sync - Proxying to: ${backendUrl}`);

    // Call Flask backend
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error(`[API] Backend returned ${response.status}:`, data);
      return NextResponse.json(
        { error: data.error || 'Failed to sync projects' },
        { status: response.status }
      );
    }

    console.log(`[API] Successfully synced projects - ${data.message}`);
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error('[API] Error syncing projects:', error);
    return NextResponse.json(
      { error: 'Failed to sync projects', details: String(error) },
      { status: 500 }
    );
  }
}

import { getApiBaseUrl } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = getApiBaseUrl();
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 't_hmXetfMCq3';

/**
 * POST /api/runs/[run_token]/cancel
 * Cancels a ParseHub run
 * Proxies to Flask backend: POST /api/runs/{run_token}/cancel
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { run_token: string } }
) {
  try {
    const { run_token } = params;

    if (!run_token) {
      return NextResponse.json(
        { error: 'Missing run_token parameter' },
        { status: 400 }
      );
    }

    const backendUrl = `${BACKEND_URL}/api/runs/${run_token}/cancel`;

    console.log(`[API] POST /api/runs/${run_token}/cancel - Proxying to: ${backendUrl}`);

    // Call Flask backend
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    if (!response.ok) {
      console.error(`[API] Backend returned ${response.status}:`, data);
      return NextResponse.json(
        { error: data.error || 'Failed to cancel run' },
        { status: response.status }
      );
    }

    console.log(`[API] Successfully cancelled run: ${run_token}`);
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error('[API] Error cancelling run:', error);
    return NextResponse.json(
      { error: 'Failed to cancel run', details: String(error) },
      { status: 500 }
    );
  }
}

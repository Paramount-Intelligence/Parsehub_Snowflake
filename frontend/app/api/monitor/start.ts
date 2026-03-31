import { getApiBaseUrl, getApiHeaders } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { projectToken, runToken, pages } = await request.json();

    if (!projectToken || !runToken) {
      return NextResponse.json(
        { error: 'Missing required fields: projectToken, runToken' },
        { status: 400 }
      );
    }

    // Allow 0 (unknown / not yet loaded total_pages)
    const pagesRaw = pages ?? 0;
    const n = typeof pagesRaw === 'number' ? pagesRaw : Number(pagesRaw);
    const pageCount = Number.isFinite(n) ? n : 0;

    // Call Python backend API to start monitoring
    const backendUrl = getApiBaseUrl();
    
    const response = await fetch(`${backendUrl}/api/monitor/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getApiHeaders(),
      },
      body: JSON.stringify({
        run_token: runToken,
        pages: pageCount,
        project_token: projectToken,
      }),
    });

    const bodyText = await response.text();
    let backendJson: { error?: string; session_id?: number } = {};
    try {
      backendJson = bodyText ? JSON.parse(bodyText) : {};
    } catch {
      backendJson = {};
    }

    if (response.status !== 200) {
      console.error('Backend error:', bodyText);
      return NextResponse.json(
        {
          error:
            backendJson.error ||
            bodyText ||
            'Failed to start monitoring on backend',
        },
        { status: response.status }
      );
    }

    const data = backendJson;

    return NextResponse.json({
      success: true,
      sessionId: data.session_id,
      runToken: runToken,
      startedAt: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error starting monitoring:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

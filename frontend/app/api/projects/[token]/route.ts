import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '../../_proxy';
import axios from 'axios';

const PARSEHUB_API_KEY = process.env.PARSEHUB_API_KEY || '';
const PARSEHUB_BASE_URL = process.env.PARSEHUB_BASE_URL || 'https://www.parsehub.com/api/v2';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params;
  if (!token) {
    return NextResponse.json({ error: 'Project token is required' }, { status: 400 });
  }

  // Try Flask backend first (has richer stored data)
  try {
    const result = await proxyToBackend(request, `/api/projects/${token}`);
    if (result.status < 400) return result;
  } catch {
    console.log(`[API] Flask lookup failed for token ${token}, falling back to ParseHub`);
  }

  // Fallback: direct ParseHub API
  try {
    const response = await axios.get(`${PARSEHUB_BASE_URL}/projects/${token}`, {
      params: { api_key: PARSEHUB_API_KEY },
      timeout: 8000,
    });
    return NextResponse.json(response.data);
  } catch (error) {
    console.error('[API] ParseHub fallback also failed:', error);
    return NextResponse.json({ error: 'Failed to fetch project details' }, { status: 502 });
  }
}

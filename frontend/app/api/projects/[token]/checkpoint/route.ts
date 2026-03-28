import { NextRequest } from 'next/server';
import { proxyToBackend } from '../../../_proxy';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params;
  return proxyToBackend(request, `/api/projects/${token}/checkpoint`);
}

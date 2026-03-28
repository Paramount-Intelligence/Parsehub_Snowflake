import { NextRequest } from 'next/server';
import { proxyToBackend } from '../../../_proxy';

export async function DELETE(
  request: NextRequest,
  { params }: { params: { jobId: string } }
) {
  const { jobId } = params;
  return proxyToBackend(request, `/api/scheduled-runs/${jobId}`);
}

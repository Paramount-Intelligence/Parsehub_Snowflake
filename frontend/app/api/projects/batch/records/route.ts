import { NextRequest } from 'next/server';
import { proxyToBackend } from '../../../_proxy';

export async function GET(request: NextRequest) {
  return proxyToBackend(request, '/api/projects/batch/records');
}

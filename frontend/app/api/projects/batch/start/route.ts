import { NextRequest } from 'next/server';
import { proxyToBackend } from '../../../_proxy';

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/api/projects/batch/start');
}

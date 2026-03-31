import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/app/api/_proxy';

export async function POST(request: NextRequest) {
    return proxyToBackend(request, '/api/projects/sync-msa');
}

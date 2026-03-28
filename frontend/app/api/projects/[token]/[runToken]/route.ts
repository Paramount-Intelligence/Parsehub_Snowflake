import { NextRequest, NextResponse } from 'next/server'
import axios from 'axios'

const API_KEY = process.env.PARSEHUB_API_KEY || ''
const BASE_URL = process.env.PARSEHUB_BASE_URL || 'https://www.parsehub.com/api/v2'

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ token: string; runToken: string }> }
) {
  try {
    const { token, runToken } = await params

    const response = await axios.get(
      `${BASE_URL}/projects/${token}/runs/${runToken}/data`,
      { params: { api_key: API_KEY } }
    )

    return NextResponse.json(response.data)
  } catch (error) {
    console.error('API Error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch run data' },
      { status: 500 }
    )
  }
}

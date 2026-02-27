import { getApiBaseUrl } from "@/lib/apiBase";
import { NextRequest, NextResponse } from 'next/server'
import axios from 'axios'

const API_KEY = process.env.PARSEHUB_API_KEY || ''
const BASE_URL = process.env.PARSEHUB_BASE_URL || 'https://www.parsehub.com/api/v2'
const BACKEND_URL = getApiBaseUrl();

export async function GET(
  _request: NextRequest,
  { params }: { params: { token: string } }
) {
  try {
    const token = params.token

    if (!token) {
      return NextResponse.json(
        { error: 'Project token is required' },
        { status: 400 }
      )
    }

    // Try to get project from backend database first (has more info)
    try {
      const backendResponse = await axios.get(`${BACKEND_URL}/api/projects/${token}`, {
        timeout: 5000
      })
      
      if (backendResponse.data && backendResponse.data.success) {
        return NextResponse.json(backendResponse.data.data || backendResponse.data)
      }
    } catch (backendError) {
      console.log('[API] Backend project lookup failed, trying ParseHub API:', backendError)
    }

    // Fallback to ParseHub API
    const response = await axios.get(`${BASE_URL}/projects/${token}`, {
      params: { api_key: API_KEY },
    })

    const project = response.data

    return NextResponse.json(project)
  } catch (error) {
    console.error('[API] Error fetching project details:', error)
    return NextResponse.json(
      { error: 'Failed to fetch project details' },
      { status: 500 }
    )
  }
}

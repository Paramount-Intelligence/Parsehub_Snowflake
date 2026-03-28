import { NextRequest, NextResponse } from 'next/server'
import axios from 'axios'
import { getApiBaseUrl, getApiHeaders } from "@/lib/apiBase";

export async function POST(request: NextRequest) {
  try {
    const { token, project_token, pages } = await request.json()
    
    // Accept either 'token' or 'project_token' field name
    const projectToken = token || project_token

    if (!projectToken) {
      return NextResponse.json(
        { error: 'Project token is required' },
        { status: 400 }
      )
    }

    console.log(`[API] Running project via backend: ${projectToken} with ${pages || 1} pages`)

    // Call Flask backend instead of ParseHub directly
    // This ensures auto-complete service monitors the run
    const backendUrl = getApiBaseUrl();
    const response = await axios.post(
      `${backendUrl}/api/projects/${projectToken}/run`,
      { pages: pages || 1 },
      { headers: getApiHeaders() }
    )

    console.log(`[API] ✅ Project run started via backend: ${projectToken}, run_token: ${response.data.run_token}`)

    return NextResponse.json({
      success: true,
      run_token: response.data.run_token,
      status: response.data.status || 'started',
      pages: pages || 1,
      message: response.data.message || 'Project started successfully',
    })
  } catch (error) {
    console.error('[API] Error running project:', error)
    
    if (axios.isAxiosError(error)) {
      console.error('[API] Error response:', error.response?.data)
      return NextResponse.json(
        { error: error.response?.data?.error || error.message || 'Failed to run project' },
        { status: error.response?.status || 500 }
      )
    }

    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to run project' },
      { status: 500 }
    )
  }
}

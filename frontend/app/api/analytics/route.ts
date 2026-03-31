import { NextRequest, NextResponse } from 'next/server'
import axios from 'axios'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const token = searchParams.get('token')

    if (!token) {
      console.error(`[API] Error: No token provided`)
      return NextResponse.json(
        { error: 'Token is required' },
        { status: 400 }
      )
    }

    const { getApiBaseUrl, getApiHeaders } = await import('@/lib/apiBase')
    const backendUrl = getApiBaseUrl()

    console.log(`[API] Fetching analytics for token=${token} from backend Snowflake sync...`)

    // We only poll Snowflake now — no more live ParseHub calls or frontend CSV parsing
    const response = await axios.get(`${backendUrl}/api/get-analytics`, {
      params: { project_token: token },
      headers: getApiHeaders(),
      timeout: 15000,
    })

    const result = response.data

    if (!result.success || !result.found) {
      console.log(`[API] No data found in database for token=${token}`)
      return NextResponse.json({
        overview: {
          total_runs: 0,
          completed_runs: 0,
          total_records_scraped: 0,
          progress_percentage: 0,
        },
        performance: {
          items_per_minute: 0,
          estimated_total_items: 0,
          average_run_duration_seconds: 0,
          current_items_count: 0,
        },
        recovery: {
          in_recovery: false,
          status: 'no_data',
          total_recovery_attempts: 0,
        },
        data_quality: {
          average_completion_percentage: 0,
          total_fields: 0,
        },
        timeline: [],
        columns: [],
        rows: [],
        message: 'No data available yet. Please complete a run and wait up to 5 minutes for background sync.',
      })
    }

    console.log(`✅ [API] analytics returned successfully with ${result.records_count} normalized rows for ${token}`)
    return NextResponse.json(result.data)

  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error)
    console.error(`[API] Exception fetching analytics:`, errMsg)

    // Detailed Axios errors
    if (axios.isAxiosError(error) && error.response) {
      console.error(`[API] Server responded with status ${error.response.status}:`, error.response.data)
    }

    return NextResponse.json(
      { error: 'Internal server error fetching analytics backend' },
      { status: 500 }
    )
  }
}

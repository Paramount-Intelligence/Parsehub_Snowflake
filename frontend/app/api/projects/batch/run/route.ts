import { NextRequest, NextResponse } from 'next/server'
import axios from 'axios'

const API_KEY = process.env.PARSEHUB_API_KEY || ''
const BASE_URL = process.env.PARSEHUB_BASE_URL || 'https://www.parsehub.com/api/v2'

export async function POST(request: NextRequest) {
  try {
    const { project_tokens } = await request.json()

    if (!project_tokens || !Array.isArray(project_tokens) || project_tokens.length === 0) {
      return NextResponse.json(
        { error: 'project_tokens array is required' },
        { status: 400 }
      )
    }

    console.log(`[BATCH] Running ${project_tokens.length} projects`)

    const results = []
    let successful = 0
    let failed = 0

    // Run each project sequentially
    for (let i = 0; i < project_tokens.length; i++) {
      const token = project_tokens[i]

      if (!token || typeof token !== 'string' || !token.trim()) {
        console.warn(`[BATCH] Skipping invalid token at index ${i}`)
        results.push({
          token,
          success: false,
          error: 'Invalid token format'
        })
        failed++
        continue
      }

      try {
        console.log(`[BATCH] [${i + 1}/${project_tokens.length}] Running token: ${token}`)

        // Call ParseHub directly - same as single project run
        const response = await axios.post(
          `${BASE_URL}/projects/${token}/run`,
          {},
          { 
            params: { 
              api_key: API_KEY,
              pages: 1
            },
            timeout: 10000
          }
        )

        if (response.data && response.data.run_token) {
          console.log(`[BATCH] ✓ Success: ${token} -> ${response.data.run_token}`)
          results.push({
            token,
            success: true,
            run_token: response.data.run_token,
            status: response.data.status
          })
          successful++
        } else {
          console.warn(`[BATCH] ✗ Failed: ${token} - No run_token in response`)
          results.push({
            token,
            success: false,
            error: 'No run_token in response'
          })
          failed++
        }
      } catch (error: any) {
        const errorMsg = error.response?.data?.error || 
                        error.message ||
                        'Unknown error'
        console.error(`[BATCH] ✗ Error for ${token}: ${errorMsg}`)
        results.push({
          token,
          success: false,
          error: errorMsg
        })
        failed++
      }
    }

    console.log(`[BATCH] Complete: ${successful} successful, ${failed} failed`)

    return NextResponse.json({
      success: failed === 0,
      total_projects: project_tokens.length,
      successful,
      failed,
      results
    }, { status: 200 })

  } catch (error: any) {
    console.error('[BATCH] Error:', error.message)
    return NextResponse.json(
      { 
        error: error.message || 'Failed to execute batch run',
        success: false 
      },
      { status: 500 }
    )
  }
}

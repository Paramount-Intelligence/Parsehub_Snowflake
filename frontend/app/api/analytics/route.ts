import { NextRequest, NextResponse } from 'next/server'
import axios from 'axios'

const API_KEY = process.env.PARSEHUB_API_KEY || ''
const BASE_URL = process.env.PARSEHUB_BASE_URL || 'https://www.parsehub.com/api/v2'

// Parse CSV string to JSON records
function parseCSV(csvText: string): any[] {
  const lines = csvText.trim().split('\n')
  if (lines.length === 0) return []

  // Parse header
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))

  // Parse rows
  const records = []
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue

    // Simple CSV parsing - handles quoted fields
    const values: string[] = []
    let current = ''
    let inQuotes = false

    for (let j = 0; j < lines[i].length; j++) {
      const char = lines[i][j]
      if (char === '"') {
        inQuotes = !inQuotes
      } else if (char === ',' && !inQuotes) {
        values.push(current.trim().replace(/^"|"$/g, ''))
        current = ''
      } else {
        current += char
      }
    }
    values.push(current.trim().replace(/^"|"$/g, ''))

    // Create record object
    const record: any = {}
    headers.forEach((header, index) => {
      record[header] = values[index] || ''
    })
    records.push(record)
  }

  return records
}

// Store analytics data to database via backend API
async function storeAnalyticsDataToDB(
  projectToken: string,
  runToken: string,
  analyticsData: any,
  records: any[],
  csvData?: string
): Promise<{ success: boolean; message: string; error?: string; records_stored?: number }> {
  try {
    console.log(`[DB STORE] Storing data for project ${projectToken} via backend API, records: ${records.length}`)

    // Import getApiBaseUrl at the top of the file
    const { getApiBaseUrl, getApiHeaders } = await import('@/lib/apiBase')
    const backendUrl = getApiBaseUrl()

    const response = await axios.post(
      `${backendUrl}/api/store-analytics`,
      {
        project_token: projectToken,
        run_token: runToken,
        analytics_data: analyticsData,
        records: records,
        csv_data: csvData || null,
      },
      {
        headers: getApiHeaders(),
        timeout: 60000, // 60 second timeout for large datasets
      }
    )

    const result = response.data

    if (result.success) {
      console.log(`✅ [DB STORE] SUCCESS: Data stored for ${projectToken}, records: ${result.records_stored}`)
    } else {
      console.error(`❌ [DB STORE] FAILED: ${result.error}`)
    }

    return result

  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error)
    console.error(`❌ [DB STORE] Exception: ${errMsg}`)
    
    // Handle axios errors with more detail
    if (axios.isAxiosError(error)) {
      const serverError = error.response?.data?.error || error.message
      console.error(`❌ [DB STORE] Server error: ${serverError}`)
      return { 
        success: false, 
        message: serverError, 
        error: serverError 
      }
    }
    
    return { success: false, message: errMsg, error: errMsg }
  }
}

// Retrieve analytics data from database via backend API
async function getAnalyticsDataFromDB(projectToken: string): Promise<any> {
  try {
    console.log(`[DB RETRIEVE] Looking for cached data for ${projectToken} via backend API...`)

    // Import getApiBaseUrl
    const { getApiBaseUrl, getApiHeaders } = await import('@/lib/apiBase')
    const backendUrl = getApiBaseUrl()

    const response = await axios.get(
      `${backendUrl}/api/get-analytics`,
      {
        params: { project_token: projectToken },
        headers: getApiHeaders(),
        timeout: 15000,
      }
    )

    const result = response.data

    if (!result.success) {
      console.error(`❌ [DB RETRIEVE] API error: ${result.error}`)
      return null
    }

    if (!result.found) {
      console.log(`[DB RETRIEVE] No cached data found for ${projectToken}`)
      return null
    }

    const recordCount = result.data?.raw_data ? result.data.raw_data.length : 0
    console.log(`✅ [DB RETRIEVE] Retrieved cached data: ${recordCount} records for ${projectToken}`)
    return result.data

  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error)
    console.error(`❌ [DB RETRIEVE] Error retrieving analytics from DB:`, errMsg)
    
    if (axios.isAxiosError(error)) {
      const serverError = error.response?.data?.error || error.message
      console.error(`❌ [DB RETRIEVE] Server error: ${serverError}`)
    }
    
    return null
  }
}

// Fetch project data directly from ParseHub API
async function fetchProjectDataFromParseHub(projectToken: string) {
  try {
    console.log(`Fetching data for project ${projectToken} from ParseHub...`)

    // Get project info
    const projectResponse = await axios.get(`${BASE_URL}/projects/${projectToken}`, {
      params: { api_key: API_KEY },
      timeout: 15000,
    })

    const project = projectResponse.data
    if (!project) return null

    console.log(`Project found: ${project.title}, last_run status: ${project.last_run?.status}`)

    // Get the last run's data
    if (project.last_run && project.last_run.run_token) {
      const runToken = project.last_run.run_token
      console.log(`Fetching data for run ${runToken}...`)

      // Try to fetch CSV format first (preferred for data completeness)
      console.log(`Attempting CSV format...`)
      try {
        const csvResponse = await axios.get(`${BASE_URL}/runs/${runToken}/data`, {
          params: { api_key: API_KEY, format: 'csv' },
          timeout: 15000,
          headers: { 'Accept-Encoding': 'gzip' },
        })

        const csvText = csvResponse.data
        console.log(`CSV data fetched, parsing...`)

        // Parse CSV to records
        const records = parseCSV(csvText)
        const totalRecords = records.length

        console.log(`Parsed ${totalRecords} records from CSV`)

        // Return data in analytics format
        return {
          overview: {
            total_runs: 1,
            completed_runs: project.last_run.status === 'succeeded' || project.last_run.status === 'complete' ? 1 : 0,
            total_records_scraped: totalRecords,
            progress_percentage: (project.last_run.status === 'succeeded' || project.last_run.status === 'complete') ? 100 : 50,
          },
          performance: {
            items_per_minute: 0,
            estimated_total_items: totalRecords,
            average_run_duration_seconds: 0,
            current_items_count: totalRecords,
          },
          recovery: {
            in_recovery: false,
            status: 'normal',
            total_recovery_attempts: 0,
          },
          data_quality: {
            average_completion_percentage: 100,
            total_fields: records && records[0] ? Object.keys(records[0]).length : 0,
          },
          timeline: [],
          source: 'parsehub',
          raw_data: records,
          csv_data: csvText,
          run_token: runToken,
        }
      } catch (csvError) {
        console.log('CSV fetch failed, trying JSON...', csvError instanceof Error ? csvError.message : '')

        // Fallback to JSON format
        const jsonResponse = await axios.get(`${BASE_URL}/runs/${runToken}/data`, {
          params: { api_key: API_KEY },
          timeout: 15000,
        })

        const runData = jsonResponse.data
        console.log(`JSON data fetched`)

        // Extract records from the response
        let records = []
        let totalRecords = 0
        let dataKeys = Object.keys(runData).filter(k => !['offset', 'brand'].includes(k))

        // Look for array fields
        for (const key of dataKeys) {
          if (Array.isArray(runData[key])) {
            records = runData[key]
            totalRecords = records.length
            console.log(`Found ${totalRecords} records in field "${key}"`)
            break
          }
        }

        // Return data in analytics format
        return {
          overview: {
            total_runs: 1,
            completed_runs: project.last_run.status === 'succeeded' || project.last_run.status === 'complete' ? 1 : 0,
            total_records_scraped: totalRecords,
            progress_percentage: (project.last_run.status === 'succeeded' || project.last_run.status === 'complete') ? 100 : 50,
          },
          performance: {
            items_per_minute: 0,
            estimated_total_items: totalRecords,
            average_run_duration_seconds: 0,
            current_items_count: totalRecords,
          },
          recovery: {
            in_recovery: false,
            status: 'normal',
            total_recovery_attempts: 0,
          },
          data_quality: {
            average_completion_percentage: 100,
            total_fields: records && records[0] ? Object.keys(records[0]).length : 0,
          },
          timeline: [],
          source: 'parsehub',
          raw_data: records,
          run_token: runToken,
        }
      }
    }

    return null
  } catch (error) {
    console.error('Error fetching from ParseHub:', error instanceof Error ? error.message : error)
    return null
  }
}

// Fetch and store project data from ParseHub
async function fetchAndStoreProjectData(projectToken: string) {
  try {
    console.log(`[FETCH_STORE] Fetching and storing data for project ${projectToken}...`)

    // First try to get data from ParseHub
    let parseHubData = await fetchProjectDataFromParseHub(projectToken)

    if (!parseHubData) {
      console.log(`[FETCH_STORE] ParseHub API unavailable or returned null`)
      return null
    }

    console.log(`[FETCH_STORE] Got ParseHub data: ${parseHubData.overview?.total_records_scraped || 0} records`)

    if (parseHubData) {
      // ✅ Store to database SYNCHRONOUSLY and wait for completion
      const recordsToStore = parseHubData.raw_data || []
      console.log(`[FETCH_STORE] Storing ${recordsToStore.length} records to database...`)

      const storageResult = await storeAnalyticsDataToDB(
        projectToken,
        parseHubData.run_token || 'unknown',
        parseHubData,
        recordsToStore,
        parseHubData.csv_data
      )

      // ✅ Verify storage succeeded BEFORE returning response
      if (storageResult.success) {
        console.log(`✅ [FETCH_STORE] Data successfully stored to database for ${projectToken}`)
      } else {
        console.error(`❌ [FETCH_STORE] Database storage FAILED: ${storageResult.error}`)
        console.warn(`[FETCH_STORE] Returning data anyway, but data will be lost on next refresh!`)
      }

      // Return with raw_data included for display
      const response = {
        overview: parseHubData.overview,
        performance: parseHubData.performance,
        recovery: parseHubData.recovery,
        data_quality: parseHubData.data_quality,
        timeline: parseHubData.timeline,
        raw_data: parseHubData.raw_data,
        csv_data: parseHubData.csv_data,
        source: parseHubData.source,
        stored: storageResult.success,
        storage_message: storageResult.message,
      }

      console.log(`[FETCH_STORE] Returning response with ${recordsToStore.length} records`)
      return response
    }

    return null
  } catch (error) {
    console.error(`❌ [FETCH_STORE] Exception:`, error instanceof Error ? error.message : error)
    return null
  }
}


export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const token = searchParams.get('token') || process.env.PARSEHUB_API_KEY
    const force = searchParams.get('force') === 'true'

    console.log(`\n[API] GET /api/analytics token=${token}, force=${force}`)

    if (!token) {
      console.error(`[API] Error: No token provided`)
      return NextResponse.json(
        { error: 'Token is required' },
        { status: 400 }
      )
    }

    let analytics = null

    // ✅ ALWAYS check database first (fast response)
    console.log(`[API] Step 1: Checking database for ${token}...`)
    try {
      const dbResult = await Promise.race([
        getAnalyticsDataFromDB(token),
        new Promise<null>(resolve => setTimeout(() => resolve(null), 5000)) // 5 sec timeout
      ])

      analytics = dbResult
      if (analytics && analytics.raw_data && analytics.raw_data.length > 0) {
        console.log(`✅ [API] Step 1 SUCCESS: Found ${analytics.raw_data.length} records in database`)

        // Background update if force=true
        if (force) {
          console.log(`[API] Background: Queuing ParseHub update...`)
          // Don't await, let it run in background
          fetchAndStoreProjectData(token).catch(err => {
            console.warn(`[API] Background update failed (non-critical):`, err instanceof Error ? err.message : err)
          })
        }

        return NextResponse.json(analytics)
      } else {
        console.log(`[API] Step 1: No valid data in database, continuing...`)
      }
    } catch (err) {
      console.warn(`[API] Step 1 warning:`, err instanceof Error ? err.message : err)
    }

    // ✅ Second: Fetch from ParseHub with timeout (only if database is empty)
    if (!analytics) {
      console.log(`[API] Step 2: Fetching from ParseHub for token ${token} (with timeout)...`)
      try {
        // Use Promise.race with timeout for faster failure
        const result = await Promise.race([
          fetchAndStoreProjectData(token),
          new Promise<null>((_, reject) =>
            setTimeout(() => reject(new Error('ParseHub request timeout')), 12000) // 12 sec timeout
          )
        ])

        analytics = result
        if (analytics) {
          console.log(`✅ [API] Step 2 SUCCESS: Got data from ParseHub, stored=${(analytics as any).stored}`)
        }
      } catch (error) {
        console.warn(`[API] Step 2: ParseHub failed or timed out:`, error instanceof Error ? error.message : error)
        analytics = null
      }
    }

    // Return empty response with status message
    if (!analytics) {
      console.log(`[API] No data found, returning empty response`)
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
        message: 'No data available. Try running the project first.',
      })
    }

    console.log(`[API] Returning response for ${token}`)
    return NextResponse.json(analytics)
  } catch (error) {
    console.error(`[API] Exception:`, error instanceof Error ? error.message : error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

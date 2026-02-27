import { getApiBaseUrl } from "@/lib/apiBase";
import { NextResponse, NextRequest } from 'next/server'
import axios from 'axios'

const BACKEND_URL = getApiBaseUrl();
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || 't_hmXetfMCq3'
const REQUEST_TIMEOUT = 30000 // 30 seconds for paginated requests (NOT 300 seconds!)

export async function GET(request: NextRequest) {
  try {
    // Get pagination and filter parameters from query string
    const searchParams = request.nextUrl.searchParams
    const page = searchParams.get('page') || '1'
    const limit = searchParams.get('limit') || '20'
    const filterKeyword = searchParams.get('filter_keyword') || ''
    
    // NEW: Get filter parameters
    const region = searchParams.get('region') || ''
    const country = searchParams.get('country') || ''
    const brand = searchParams.get('brand') || ''
    const website = searchParams.get('website') || ''
    
    console.log(`[API] Fetching projects: page=${page}, limit=${limit}, filter=${filterKeyword || 'none'}`)
    console.log(`[API] Filters: region=${region}, country=${country}, brand=${brand}, website=${website}`)
    console.log(`[API] Backend URL: ${BACKEND_URL}`)

    // Build paginated URL with pagination parameters
    const backendUrl = new URL(`${BACKEND_URL}/api/projects`)
    backendUrl.searchParams.append('page', page)
    backendUrl.searchParams.append('limit', limit)
    if (filterKeyword) {
      backendUrl.searchParams.append('filter_keyword', filterKeyword)
    }
    
    // NEW: Add filter parameters to backend URL
    if (region) {
      backendUrl.searchParams.append('region', region)
    }
    if (country) {
      backendUrl.searchParams.append('country', country)
    }
    if (brand) {
      backendUrl.searchParams.append('brand', brand)
    }
    if (website) {
      backendUrl.searchParams.append('website', website)
    }
    
    console.log(`[API] Calling backend: ${backendUrl.toString()}`)

    // Backend will use its own API key - don't pass frontend's API key
    const response = await axios.get(backendUrl.toString(), {
      headers: {
        'Authorization': `Bearer ${BACKEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      timeout: REQUEST_TIMEOUT
    })

    const data = response.data
    console.log(`[API] Backend response status: ${response.status}`)
    console.log(`[API] Backend response keys: ${Object.keys(data)}`)
    
    // Handle new grouped format (by_website) or old flat format (projects)
    let projects = []
    let by_website = []
    let pagination = data.pagination || { page: 1, total: 0, total_pages: 1, has_more: false }
    
    if (data.by_website && Array.isArray(data.by_website)) {
      // New grouped format
      by_website = data.by_website
      console.log(`[API] Processing grouped format with ${by_website.length} website groups`)
      
      // Get projects from the current page (already paginated by backend)
      projects = data.projects || []
    } else if (data.projects && Array.isArray(data.projects)) {
      // Old flat format (full dataset)
      projects = data.projects
      by_website = data.by_website || []
    }
    
    console.log(`[API] Page ${pagination.page}/${pagination.total_pages}: ${projects.length} projects`)
    console.log(`[API] Total projects in system: ${pagination.total}`)
    console.log(`[API] Website groups: ${by_website.length}`)
    
    if (projects.length > 0) {
      console.log(`[API] Sample: ${projects.slice(0, 3).map((p: any) => p.title || p.name || 'Unknown').join(', ')}`)
    }

    console.log(`[API] ✅ Successfully fetched page ${pagination.page}`)
    
    // Return paginated response
    const responsePayload = {
      success: true,
      pagination: pagination,  // Include pagination info
      total: pagination.total,  // For backward compatibility
      page: pagination.page,     // For backward compatibility
      project_count: projects.length,
      by_website: by_website,
      projects: projects,
      metadata_matches: data.metadata_matches || 0,
      sync_result: data.sync_result || null,
      metadata_sync_result: data.metadata_sync_result || null
    }
    
    console.log(`[API] Returning page ${pagination.page} with ${projects.length} projects and ${by_website.length} groups`)
    
    return NextResponse.json(responsePayload)

  } catch (error) {
    console.error('[API] Error fetching projects:', error)
    
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNREFUSED') {
        console.error('[API] ❌ Backend server not running on', BACKEND_URL)
        return NextResponse.json(
          { error: 'Backend server not running. Please start the Flask server.' },
          { status: 503 }
        )
      }
      if (error.response?.status === 401) {
        console.error('[API] ❌ Unauthorized - check API key')
        return NextResponse.json(
          { error: 'Unauthorized - invalid API key' },
          { status: 401 }
        )
      }
      if (error.code === 'ECONNABORTED') {
        console.error('[API] ❌ Request timeout - took longer than 30 seconds')
        return NextResponse.json(
          { error: 'Request timeout - pagination took too long' },
          { status: 504 }
        )
      }
    }

    return NextResponse.json(
      { error: 'Failed to fetch projects from backend' },
      { status: 500 }
    )

  }
}


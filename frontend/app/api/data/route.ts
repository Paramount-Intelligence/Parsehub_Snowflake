import { NextRequest, NextResponse } from 'next/server'
import { getApiBaseUrl, getApiHeaders } from "@/lib/apiBase";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const token = searchParams.get('token')
    const projectId = searchParams.get('projectId')

    if (!token && !projectId) {
      return NextResponse.json(
        { error: 'Token or Project ID is required' },
        { status: 400 }
      )
    }

    const backendUrl = getApiBaseUrl();

    // Use the new scraped-data endpoint by token if available
    if (token) {
      try {
        const response = await fetch(
          `${backendUrl}/api/projects/${token}/scraped-data?limit=1000`,
          { headers: getApiHeaders() }
        );

        if (response.ok) {
          const data = await response.json();
          return NextResponse.json({
            success: true,
            data: data.data || [],
            count: data.count || 0,
            total: data.total || 0,
            timestamp: new Date().toISOString(),
          });
        }
      } catch (err) {
        console.error('Error fetching scraped data by token:', err);
      }
    }

    // Fallback to project_id endpoint
    if (projectId) {
      try {
        const response = await fetch(
          `${backendUrl}/api/projects/${projectId}/scraped-data?limit=1000`,
          { headers: getApiHeaders() }
        );

        if (response.ok) {
          const data = await response.json();
          return NextResponse.json({
            success: true,
            data: data.data || [],
            count: data.count || 0,
            total: data.total || 0,
            timestamp: new Date().toISOString(),
          });
        }
      } catch (err) {
        console.error('Error fetching scraped data by project ID:', err);
      }
    }

    // Final fallback: return empty
    return NextResponse.json({
      success: true,
      data: [],
      count: 0,
      timestamp: new Date().toISOString(),
    });

  } catch (error) {
    console.error('API Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch data' },
      { status: 500 }
    );
  }
}

import { getApiBaseUrl, getApiHeaders } from "@/lib/apiBase";
import { NextRequest, NextResponse } from "next/server";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ token: string }> },
) {
  try {
    const BACKEND_URL = getApiBaseUrl();
    const { token } = await params;

    const response = await fetch(
      `${BACKEND_URL}/api/projects/${token}/runs/live`,
      {
        headers: {
          "Content-Type": "application/json",
          ...getApiHeaders(),
        },
      },
    );

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("runs/live proxy error:", error);
    return NextResponse.json(
      { success: false, error: "Failed to fetch live run status" },
      { status: 500 },
    );
  }
}

import { getFrontendApiUrl } from "./apiBase";
export const API_URL = getFrontendApiUrl();

export async function fetchProjects() {
  const response = await fetch(`${API_URL}/api/projects`)
  if (!response.ok) throw new Error('Failed to fetch projects')
  return response.json()
}

export async function runProject(token: string) {
  const response = await fetch(`${API_URL}/api/projects/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!response.ok) throw new Error('Failed to run project')
  return response.json()
}

export async function runAllProjects() {
  const response = await fetch(`${API_URL}/api/projects/run-all`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('Failed to run all projects')
  return response.json()
}

export async function getRunData(token: string, runToken: string) {
  const response = await fetch(
    `${API_URL}/api/projects/${token}/${runToken}`
  )
  if (!response.ok) throw new Error('Failed to fetch run data')
  return response.json()
}

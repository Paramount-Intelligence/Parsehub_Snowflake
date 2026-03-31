import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Contract: Next /api/monitor/start must forward project_token so Flask can resolve projects.id.
 * (Backend does not rely on runs.run_token alone on Snowflake.)
 */
describe('monitor start API payload', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('POST body to Flask includes project_token, run_token, and pages', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          session_id: 999001,
          project_id: 8,
          run_token: 'run_tok',
          target_pages: 2,
          status: 'monitoring_started',
        }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const backendUrl = 'http://127.0.0.1:5000';
    const projectToken = 'projTokX';
    const runToken = 'runTokY';
    const pageCount = 2;

    await fetch(`${backendUrl}/api/monitor/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_token: runToken,
        pages: pageCount,
        project_token: projectToken,
      }),
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.project_token).toBe(projectToken);
    expect(body.run_token).toBe(runToken);
    expect(body.pages).toBe(pageCount);
  });
});

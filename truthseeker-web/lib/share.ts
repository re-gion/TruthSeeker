"use client"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
const TRANSIENT_RETRY_STATUSES = new Set([404, 409, 425, 429, 500, 502, 503, 504])
const RETRY_DELAYS_MS = [300, 900, 1500]

type FetchLike = typeof fetch

function requestOptions(authToken?: string | null): RequestInit {
    return {
        method: "POST",
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
    }
}

function waitForRetry(attempt: number) {
    const delay = RETRY_DELAYS_MS[Math.min(attempt - 1, RETRY_DELAYS_MS.length - 1)] ?? 0
    if (delay <= 0) return Promise.resolve()
    return new Promise((resolve) => globalThis.setTimeout(resolve, delay))
}

export async function createReportShareLink(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
    attempts = 3,
) {
    let lastStatus = 0
    let lastError: unknown = null

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        try {
            const response = await fetchImpl(`${API_BASE}/api/v1/share/${taskId}`, requestOptions(authToken))
            if (response.ok) {
                const payload = await response.json()
                if (typeof payload.share_url === "string" && payload.share_url) {
                    return payload.share_url
                }
                throw new Error("分享接口未返回链接")
            }

            lastStatus = response.status
            if (attempt < attempts && TRANSIENT_RETRY_STATUSES.has(response.status)) {
                await waitForRetry(attempt)
                continue
            }
            break
        } catch (error) {
            lastError = error
            if (attempt < attempts) {
                await waitForRetry(attempt)
                continue
            }
        }
    }

    if (lastError) throw lastError
    throw new Error(`生成分享链接失败: ${lastStatus}`)
}

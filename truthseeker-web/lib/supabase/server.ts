import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
    const cookieStore = await cookies()

    return createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
        {
            cookies: {
                getAll() {
                    return cookieStore.getAll()
                },
                setAll(cookiesToSet) {
                    try {
                        cookiesToSet.forEach(({ name, value, options }) =>
                            cookieStore.set(name, value, options)
                        )
                    } catch {
                        // Server Component 中 set 无效，由 middleware 处理
                    }
                },
            },
        }
    )
}

export type ServerSupabase = Awaited<ReturnType<typeof createClient>>

/**
 * 安全获取会话：Supabase 不可达（瞬时网络失败等）时按未登录处理，
 * 避免 fetch failed 异常打穿页面渲染导致整页报错。
 */
export async function getSessionSafe(supabase: ServerSupabase) {
    try {
        const { data } = await supabase.auth.getSession()
        return data.session
    } catch (error) {
        console.warn("[auth] 获取会话失败（Supabase 网络不可达？），按未登录处理：", (error as Error)?.message ?? error)
        return null
    }
}

/**
 * 安全获取用户：Supabase 不可达时按未登录处理，同上。
 */
export async function getUserSafe(supabase: ServerSupabase) {
    try {
        const { data } = await supabase.auth.getUser()
        return data.user
    } catch (error) {
        console.warn("[auth] 获取用户失败（Supabase 网络不可达？），按未登录处理：", (error as Error)?.message ?? error)
        return null
    }
}

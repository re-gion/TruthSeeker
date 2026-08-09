import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
    let supabaseResponse = NextResponse.next({ request })

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
        {
            cookies: {
                getAll() {
                    return request.cookies.getAll()
                },
                setAll(cookiesToSet) {
                    cookiesToSet.forEach(({ name, value }) =>
                        request.cookies.set(name, value)
                    )
                    supabaseResponse = NextResponse.next({ request })
                    cookiesToSet.forEach(({ name, value, options }) =>
                        supabaseResponse.cookies.set(name, value, options)
                    )
                },
            },
        }
    )

    let user = null
    try {
        const { data } = await supabase.auth.getUser()
        user = data.user
    } catch (error) {
        // Supabase 不可达（瞬时网络失败等）时按未登录处理，避免全站 500
        console.warn("[middleware] 获取用户失败（Supabase 网络不可达？），按未登录处理：", (error as Error)?.message ?? error)
    }

    const pathname = request.nextUrl.pathname
    const isAuthPage = pathname === '/login' || pathname === '/signup'
    const isPublicSharePage = pathname.startsWith('/report/')
    const isPublicCasesPage = pathname === '/cases' || pathname.startsWith('/cases/')

    // 未登录用户：除登录/注册页外，全部重定向到 /login
    if (!user && !isAuthPage && !isPublicSharePage && !isPublicCasesPage) {
        const url = request.nextUrl.clone()
        url.pathname = '/login'
        return NextResponse.redirect(url)
    }

    // 已登录用户：访问登录/注册页时重定向到首页
    if (user && isAuthPage) {
        const url = request.nextUrl.clone()
        url.pathname = '/'
        return NextResponse.redirect(url)
    }

    return supabaseResponse
}

export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
}

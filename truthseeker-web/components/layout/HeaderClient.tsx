"use client"

import Image from "next/image"
import Link from "next/link"
import { ThemeToggle } from "@/components/landing/ThemeToggle"
import ShinyText from "@/components/ui/ShinyText"

interface HeaderClientProps {
    user: { email: string } | null
}

export function HeaderClient({ user }: HeaderClientProps) {
    return (
        <header className="px-6 py-4 flex items-center justify-between border-b border-border/30 backdrop-blur-md fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-black/80">
            <Link href="/" className="flex items-center gap-3 group">
                <div className="w-10 h-10 flex items-center justify-center relative transition-transform duration-500 group-hover:scale-110">
                    <svg width="32" height="32" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="drop-shadow-sm">
                        {/* The "S" curve */}
                        <path d="M 45 25 C 10 30 15 70 45 80" stroke="currentColor" className="text-[#6366F1]" strokeWidth="10" strokeLinecap="round" />
                        {/* The dot */}
                        <circle cx="48" cy="18" r="8" fill="currentColor" className="text-[#6366F1]" />
                        {/* The "T" cap and stem */}
                        <path d="M 40 38 L 85 38" stroke="currentColor" className="text-[#6366F1]" strokeWidth="10" strokeLinecap="round" />
                        <path d="M 60 38 L 65 75" stroke="currentColor" className="text-[#6366F1]" strokeWidth="10" strokeLinecap="round" />
                        {/* The right arc */}
                        <path d="M 65 80 C 85 75 90 55 85 45" stroke="currentColor" className="text-[#6366F1]" strokeWidth="10" strokeLinecap="round" />
                    </svg>
                </div>
                <div className="flex flex-col">
                    <ShinyText
                        text="TruthSeeker"
                        className="text-foreground font-black tracking-tighter text-xl leading-none"
                        speed={3}
                    />
                </div>
            </Link>
            <nav className="flex items-center gap-6">
                <Link
                    href="/detect"
                    className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2"
                >
                    <Image src="/nav-icons/detect.svg" alt="检测控制台图标" width={16} height={16} className="size-4" />
                    检测控制台
                </Link>
                <Link
                    href="/cases"
                    className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2"
                >
                    <Image src="/nav-icons/cases.svg" alt="演示案例库图标" width={16} height={16} className="size-4" />
                    演示案例库
                </Link>
                <Link
                    href="/dashboard"
                    className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2"
                >
                    <Image src="/nav-icons/dashboard.svg" alt="数据大屏图标" width={16} height={16} className="size-4" />
                    数据大屏
                </Link>

                <div className="h-4 w-px bg-border/50" />

                <ThemeToggle />

                <div className="h-4 w-px bg-border/50" />

                {user ? (
                    <div className="flex items-center gap-4">
                        <span className="text-muted-foreground text-sm font-mono">{user.email}</span>
                        <Link
                            href="/api/auth/signout"
                            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                            退出
                        </Link>
                    </div>
                ) : (
                    <div className="flex items-center gap-4">
                        <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                            登录
                        </Link>
                        <Link
                            href="/signup"
                            className="text-sm px-4 py-1.5 rounded-lg bg-gradient-to-r from-[#6366F1] to-[#4F46E5] hover:opacity-90 text-white transition-opacity font-medium shadow-[0_4px_14px_rgba(99,102,241,0.39)]"
                        >
                            注册
                        </Link>
                    </div>
                )}
            </nav>
        </header>
    )
}

"use client"

import Link from "next/link"
import { BrandLogo } from "@/components/logo/BrandLogo"

export function LandingFooter() {
    return (
        <footer className="w-full relative overflow-hidden bg-background pt-20 pb-10">
            {/* Huge Background Text */}
            <div className="absolute bottom-0 inset-x-0 w-full flex justify-center pointer-events-none overflow-hidden opacity-10 dark:opacity-[0.03] z-0">
                <span className="text-[12vw] font-bold tracking-tighter leading-none bg-clip-text text-transparent bg-gradient-to-b from-foreground to-background flex select-none uppercase translate-y-[15%]">
                    TRUTHSEEKER
                </span>
            </div>

            <div className="absolute inset-x-0 top-0 h-px w-full bg-gradient-to-r from-transparent via-[#6366F1]/50 to-transparent" />

            <div className="container mx-auto px-6 max-w-7xl relative z-10">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
                    <div className="col-span-1 md:col-span-2">
                        <Link href="/" className="flex items-center gap-3 mb-6">
                            <div className="w-10 h-10 flex items-center justify-center">
                                <BrandLogo className="h-9 w-9" imageClassName="drop-shadow-sm" size={36} />
                            </div>
                            <span className="font-bold tracking-tight text-xl">TruthSeeker</span>
                        </Link>
                        <p className="text-muted-foreground text-sm leading-relaxed max-w-sm">
                            基于鲁棒联邦学习与多智能体交叉验证的跨模态鉴伪与溯源系统。
                            不是另一个 Deepfake 检测工具，而是具备专家团队思维的智能研判中枢。
                        </p>
                    </div>

                    <div>
                        <h4 className="font-semibold mb-4 text-foreground">快速链接</h4>
                        <ul className="space-y-2">
                            <li><Link href="#features" className="text-sm text-muted-foreground hover:text-primary transition-colors">核心能力</Link></li>
                            <li><Link href="#workflow" className="text-sm text-muted-foreground hover:text-primary transition-colors">检测流程</Link></li>
                            <li><Link href="#technology" className="text-sm text-muted-foreground hover:text-primary transition-colors">联邦学习</Link></li>
                            <li><Link href="#cases" className="text-sm text-muted-foreground hover:text-primary transition-colors">应用场景</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="font-semibold mb-4 text-foreground"></h4>
                        <ul className="space-y-2">
                            <li><Link href="/detect" className="text-sm text-[#D4FF12] hover:text-[#D4FF12]/80 transition-colors dark:text-[#D4FF12] text-emerald-600 font-medium">进入工作台 →</Link></li>
                            <li><Link href="/detect" className="text-sm text-muted-foreground hover:text-primary transition-colors">项目文档</Link></li>
                            <li><Link href="/dashboard" className="text-sm text-muted-foreground hover:text-primary transition-colors">技术架构图</Link></li>
                            <li><Link href="/cases" className="text-sm text-muted-foreground hover:text-primary transition-colors">联系我们</Link></li>
                        </ul>
                    </div>
                </div>

                <div className="pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4">
                    <p className="text-xs text-foreground/70 font-mono">
                        TruthSeeker © 2026 · 构建安全可信的数字未来
                    </p>
                    <div className="flex gap-4">
                        <span className="text-xs text-[#6366F1] font-mono opacity-80 uppercase px-2 py-1 rounded bg-[#6366F1]/10">
                            #FedPaRS
                        </span>
                        <span className="text-xs dark:text-[#D4FF12] text-emerald-600 font-mono opacity-80 uppercase px-2 py-1 rounded dark:bg-[#D4FF12]/10 bg-emerald-600/10">
                            #LangGraph
                        </span>
                    </div>
                </div>
            </div>
        </footer>
    )
}

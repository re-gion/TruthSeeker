import Header from "@/components/layout/Header"
import { DemoCaseSelector } from "@/components/demo/DemoCaseSelector"

export default function CasesPage() {
    return (
        <main className="min-h-screen grid-bg flex flex-col relative pt-16 bg-background text-foreground">
            {/* Dynamic background elements for depth */}
            <div className="absolute top-0 left-0 w-full h-[500px] bg-gradient-to-br from-[#6366F1]/10 to-transparent pointer-events-none -translate-y-1/2 rounded-full blur-[120px]" />
            <div className="absolute bottom-0 right-0 w-[800px] h-[800px] bg-gradient-to-tl from-[#D4FF12]/5 to-transparent pointer-events-none translate-y-1/3 translate-x-1/3 rounded-full blur-[150px]" />

            <Header />

            <div className="flex-1 container mx-auto px-6 py-16 max-w-6xl flex flex-col relative z-10">
                <div className="mb-12 text-center">
                    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-black/20 dark:border-[#D4FF12]/30 bg-black/5 dark:bg-[#D4FF12]/5 text-black/80 dark:text-[#D4FF12] text-xs font-mono tracking-wider mb-6 dark:shadow-[0_0_15px_rgba(212,255,18,0.1)]">
                        <span className="w-2 h-2 rounded-full bg-[#10B981] dark:bg-[#D4FF12] animate-pulse dark:shadow-[0_0_8px_rgba(212,255,18,0.8)]" />
                        LIVE DEMO VAULT
                    </div>
                    <h1 className="text-4xl md:text-6xl font-bold text-foreground mb-6 tracking-tight drop-shadow-sm">
                        全模态演示案例库
                    </h1>
                    <p className="text-muted-foreground text-lg max-w-3xl mx-auto leading-relaxed">
                        涵盖"音、视、图、文"四大高危场景，体验真实业务环境下多智能体协同辩论流程。针对新型深度伪造攻击，一键体验溯源侦查的魅力。
                    </p>
                </div>

                <div className="flex-1 flex flex-col">
                    <DemoCaseSelector />
                </div>
            </div>
        </main>
    )
}

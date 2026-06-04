import Header from "@/components/layout/Header"
import { ExperienceLibraryClient } from "@/components/experiences/ExperienceLibraryClient"

export default function ExperiencesPage() {
    return (
        <main className="min-h-screen grid-bg bg-background pt-16 text-foreground">
            <Header />

            <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10">
                <div className="flex flex-col gap-4 border-b border-white/10 pb-8 md:flex-row md:items-end md:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-lg border border-[#06B6D4]/25 bg-[#06B6D4]/10 px-3 py-1.5 text-xs font-mono text-[#67E8F9]">
                            PERSONAL EXPERIENCE LIBRARY
                        </div>
                        <h1 className="mt-5 text-4xl font-bold text-white md:text-5xl">
                            个人经验库
                        </h1>
                        <p className="mt-3 max-w-3xl text-base leading-7 text-white/58">
                            保存你确认入库的会诊经验，只对当前账号可见，用于后续取证、溯源和质询研判参考。
                        </p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/55">
                        会诊后编辑确认才会入库
                    </div>
                </div>

                <ExperienceLibraryClient />
            </div>
        </main>
    )
}

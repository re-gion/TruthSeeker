import { FileUploader } from "@/components/upload/FileUploader"
import Header from "@/components/layout/Header"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { FeaturePills } from "@/components/detect/FeaturePills"
import ShinyText from "@/components/ui/ShinyText"
import GradientText from "@/components/ui/GradientText"
import { DetectBackground } from "./DetectBackground"

export default async function Home() {
  return (
    <main className="min-h-screen grid-bg flex flex-col pt-16 bg-background text-foreground relative overflow-hidden" style={{ isolation: 'isolate' }}>
      {/* PixelBlast Background */}
      <DetectBackground />

      {/* Header */}
      <div className="relative z-20">
        <Header />
      </div>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-20 pb-10 relative z-10" style={{ willChange: 'transform' }}>
        {/* 去除遮罩，让 PixelBlast 背景动效清晰可见 */}
        {/* Badge */}


        {/* Title */}
        <h1 className="text-5xl md:text-7xl font-bold text-center mb-6 leading-tight drop-shadow-sm font-serif tracking-tighter" style={{ textShadow: 'none' }}>
          <GradientText
            colors={["#D4FF12", "#c084fc", "#D4FF12", "#c084fc", "#D4FF12"]}
            animationSpeed={16}
            showBorder={false}
            className="drop-shadow-[0_0_40px_rgba(212,255,18,0.4)] px-4"
          >
            TruthSeeker
          </GradientText>
        </h1>
        <p className="text-black dark:text-white text-lg md:text-xl text-center max-w-2xl mb-4 leading-relaxed font-semibold">
          <ShinyText 
            text="基于多智能体交叉验证的跨模态鉴伪与溯源" 
            speed={4} 
            shineColor="var(--color-cyber-lime)"
          />
        </p>
        <p className="text-black dark:text-white/80 opacity-90 text-sm md:text-base text-center max-w-2xl mb-12 leading-relaxed font-medium">
          电子取证 Agent × 情报溯源 Agent × 逻辑质询 Agent × 研判指挥 Agent —— 多智能体 LangGraph 架构下四阶闭环，实时对抗分析，精准发现真相
        </p>

        {/* Uploader */}
        <div className="w-full max-w-5xl xl:max-w-6xl mb-16 relative z-10">
          <div className="absolute -inset-4 bg-gradient-to-r from-[#6366F1]/10 via-[#A855F7]/10 to-[#D4FF12]/10 blur-xl opacity-50 rounded-[3rem] -z-10" />
          <FileUploader />
        </div>

        {/* Feature pills */}
        <FeaturePills />
      </div>

      {/* Footer */}
      <div className="relative z-10">
        <LandingFooter />
      </div>
    </main>
  )
}

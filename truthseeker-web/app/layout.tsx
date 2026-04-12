import type { Metadata } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import localFont from "next/font/local"
import { ScrollToTop } from "@/components/layout/ScrollToTop"
import { PageTransition } from "@/components/layout/PageTransition"
import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
})

const zhengKaiTi = localFont({
  src: "../public/fonts/ZhengKaiTi.ttf",
  variable: "--font-zhengkai",
  display: "swap",
})

const siyuanSong = localFont({
  src: "../public/fonts/思源宋体SemiBold.otf",
  variable: "--font-siyuan",
  weight: "600",
  display: "swap",
})

export const metadata: Metadata = {
  title: "TruthSeeker | AI 深度伪造鉴定系统",
  description:
    "基于多智能体辩论的跨模态 Deepfake 检测与溯源系统 - CISCN 2026",
  keywords: ["deepfake", "AI检测", "视频鉴伪", "CISCN", "TruthSeeker"],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} ${zhengKaiTi.variable} ${siyuanSong.variable} ${siyuanSong.className} antialiased bg-background text-foreground`}>
        <PageTransition>
          {children}
        </PageTransition>
        <ScrollToTop />
      </body>
    </html>
  )
}

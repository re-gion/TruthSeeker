import type { Metadata } from "next"
import localFont from "next/font/local"
import { ScrollToTop } from "@/components/layout/ScrollToTop"
import { PageTransition } from "@/components/layout/PageTransition"
import "./globals.css"

const interfaceSans = localFont({
  src: "../public/fonts/思源宋体SemiBold.otf",
  variable: "--font-geist-sans",
  display: "swap",
  weight: "600",
})

const interfaceMono = localFont({
  src: "../public/fonts/ZhengKaiTi.ttf",
  variable: "--font-geist-mono",
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
  icons: {
    icon: "/icon.png?v=20260505-white",
    shortcut: "/favicon.ico?v=20260505-white",
    apple: "/apple-icon.png?v=20260505-white",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" className="dark" suppressHydrationWarning>
      <body className={`${interfaceSans.variable} ${interfaceMono.variable} ${siyuanSong.variable} ${siyuanSong.className} antialiased bg-background text-foreground`}>
        <PageTransition>
          {children}
        </PageTransition>
        <ScrollToTop />
      </body>
    </html>
  )
}

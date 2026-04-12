import { LandingNavbar } from "@/components/landing/LandingNavbar"

export default function LandingLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <div className="relative min-h-screen bg-background text-foreground flex flex-col selection:bg-[#6366F1]/30">
            <LandingNavbar />
            <main className="flex-1">
                {children}
            </main>
        </div>
    )
}

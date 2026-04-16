import Header from "@/components/layout/Header"
import { DashboardClient } from "@/components/dashboard/DashboardClient"
import { getDashboardViewModel } from "@/lib/dashboard"

export default async function Dashboard() {
    const viewModel = await getDashboardViewModel()

    return (
        <div className="min-h-screen bg-background text-foreground selection:bg-[#6366F1]/30 font-sans relative pt-20 pb-10">
            <Header />
            <DashboardClient viewModel={viewModel} />
        </div>
    )
}

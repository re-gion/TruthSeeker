import Header from "@/components/layout/Header"
import { DashboardClient } from "@/components/dashboard/DashboardClient"
import { getDashboardViewModel } from "@/lib/dashboard"
import { createClient } from "@/lib/supabase/server"

export default async function Dashboard() {
    const supabase = await createClient()
    const { data: { session } } = await supabase.auth.getSession()
    const viewModel = await getDashboardViewModel(fetch, session?.access_token)

    return (
        <div className="min-h-screen bg-background text-foreground selection:bg-[#6366F1]/30 font-sans relative pt-20 pb-10">
            <Header />
            <DashboardClient viewModel={viewModel} />
        </div>
    )
}

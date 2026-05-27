import Header from "@/components/layout/Header"
import { CaseDetailClient } from "@/components/cases/CaseDetailClient"

interface CaseDetailPageProps {
    params: Promise<{ caseId: string }>
}

export default async function CaseDetailPage({ params }: CaseDetailPageProps) {
    const { caseId } = await params

    return (
        <main className="min-h-screen grid-bg bg-background pt-16 text-foreground">
            <Header />
            <div className="px-6 py-10">
                <CaseDetailClient caseId={caseId} />
            </div>
        </main>
    )
}

import Header from "@/components/layout/Header"
import { ExperienceDetailClient } from "@/components/experiences/ExperienceDetailClient"

interface ExperienceDetailPageProps {
    params: Promise<{ entryId: string }>
}

export default async function ExperienceDetailPage({ params }: ExperienceDetailPageProps) {
    const { entryId } = await params

    return (
        <main className="min-h-screen grid-bg bg-background pt-16 text-foreground">
            <Header />
            <div className="px-6 py-10">
                <ExperienceDetailClient entryId={entryId} />
            </div>
        </main>
    )
}

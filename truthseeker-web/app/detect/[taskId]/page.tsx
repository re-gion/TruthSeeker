import { Suspense } from "react"
import { DetectConsole } from "@/components/detect/DetectConsole"

interface DetectPageProps {
    params: Promise<{ taskId: string }>
}

export default async function DetectPage({ params }: DetectPageProps) {
    const { taskId } = await params

    return (
        <Suspense
            fallback={
                <div className="min-h-screen grid-bg flex items-center justify-center">
                    <div className="text-center space-y-3">
                        <div className="flex justify-center">
                            <img src="/loading-icon.svg" alt="loading" className="w-16 h-16 animate-spin" />
                        </div>
                        <p className="text-[#C0C0C0] text-sm">正在加载检测控制台...</p>
                    </div>
                </div>
            }
        >
            <DetectConsole taskId={taskId} />
        </Suspense>
    )
}

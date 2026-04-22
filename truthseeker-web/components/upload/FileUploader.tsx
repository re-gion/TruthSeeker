"use client"

import { useCallback, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "motion/react"
import { createClient } from "@/lib/supabase/client"

const ACCEPTED_TYPES = [
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "audio/mpeg",
    "audio/wav",
    "audio/mp4",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "text/plain",
]
const ACCEPTED_EXT = ".mp4,.mov,.webm,.mp3,.wav,.m4a,.aac,.ogg,.flac,.jpg,.jpeg,.png,.gif,.webp,.txt"
const MAX_FILES = 5
const MAX_SIZE = 250 * 1024 * 1024

const promptTemplates = [
    "请判断该内容是否存在 AI 伪造、拼接或篡改痕迹，并给出关键依据。",
    "请从画面、音频、文本一致性、来源可信度和传播风险三个角度展开分析。",
    "请优先识别是否涉及诈骗、舆情操纵或深度伪造传播链，并输出处置建议。",
]
const aspectOptions = ["多模态取证优先", "跨模态一致性", "传播链溯源", "高风险案件"]

const focusMapping: Record<string, "balanced" | "visual" | "audio" | "text"> = {
    "多模态取证优先": "balanced",
    "跨模态一致性": "visual",
    "传播链溯源": "text",
    "高风险案件": "balanced",
}

interface UploadedEvidenceFile {
    id: string
    name: string
    mime_type: string
    size_bytes: number
    modality: "video" | "audio" | "image" | "text"
    storage_path: string
    file_url?: string
}

function formatSize(bytes: number): string {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function deriveInputType(files: UploadedEvidenceFile[]) {
    const modalities = new Set(files.map((file) => file.modality))
    return modalities.size === 1 ? Array.from(modalities)[0] : "mixed"
}

async function getAuthToken(): Promise<string | null> {
    try {
        const supabase = createClient()
        const { data } = await supabase.auth.getSession()
        return data.session?.access_token ?? null
    } catch {
        return null
    }
}

export function FileUploader() {
    const router = useRouter()
    const [isDragging, setIsDragging] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [progress, setProgress] = useState(0)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const [error, setError] = useState<string | null>(null)
    const [casePrompt, setCasePrompt] = useState("")
    const [shareToCasebase, setShareToCasebase] = useState(false)
    const [selectedFocus, setSelectedFocus] = useState("多模态取证优先")

    const totalSize = useMemo(
        () => selectedFiles.reduce((sum, file) => sum + file.size, 0),
        [selectedFiles],
    )

    const addFiles = useCallback((incoming: FileList | File[]) => {
        setError(null)
        const nextFiles = Array.from(incoming)
        const invalid = nextFiles.find((file) => !ACCEPTED_TYPES.includes(file.type))
        if (invalid) {
            setError(`不支持的文件类型：${invalid.type || invalid.name}`)
            return
        }
        const oversize = nextFiles.find((file) => file.size > MAX_SIZE)
        if (oversize) {
            setError(`${oversize.name} 超过大小限制（视频 250MB / 音频 20MB / 图片 50MB / 文本 5MB）`)
            return
        }

        setSelectedFiles((current) => {
            const merged = [...current]
            for (const file of nextFiles) {
                if (merged.length >= MAX_FILES) break
                const exists = merged.some((item) => item.name === file.name && item.size === file.size)
                if (!exists) merged.push(file)
            }
            if (current.length + nextFiles.length > MAX_FILES) {
                setError(`最多一次上传 ${MAX_FILES} 个文件`)
            }
            return merged
        })
    }, [])

    const removeFile = useCallback((index: number) => {
        setSelectedFiles((current) => current.filter((_, i) => i !== index))
    }, [])

    const launchAnalysis = useCallback(async () => {
        setError(null)
        if (selectedFiles.length === 0) {
            setError("请至少上传 1 个待检测文件，提示词只作为全局检测目标")
            return
        }

        const authToken = await getAuthToken()
        if (!authToken) {
            setError("请先登录后再提交检测任务")
            return
        }

        setUploading(true)
        setProgress(0)
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        const priorityFocus = focusMapping[selectedFocus] || "balanced"

        try {
            const uploadedFiles: UploadedEvidenceFile[] = []

            for (let index = 0; index < selectedFiles.length; index += 1) {
                const file = selectedFiles[index]
                const formData = new FormData()
                formData.append("file", file)

                const uploadResp = await fetch(`${apiBase}/api/v1/upload/`, {
                    method: "POST",
                    body: formData,
                    headers: { Authorization: `Bearer ${authToken}` },
                })
                if (!uploadResp.ok) {
                    const err = await uploadResp.json().catch(() => ({}))
                    throw new Error(err.detail || `${file.name} 上传失败`)
                }
                const uploadData = await uploadResp.json()
                uploadedFiles.push({
                    id: uploadData.id || `file-${index + 1}`,
                    name: uploadData.name || file.name,
                    mime_type: uploadData.mime_type || file.type,
                    size_bytes: uploadData.size_bytes || file.size,
                    modality: uploadData.modality,
                    storage_path: uploadData.storage_path,
                    file_url: uploadData.file_url,
                })
                setProgress(Math.round(((index + 1) / selectedFiles.length) * 70))
            }

            const inputType = deriveInputType(uploadedFiles)
            const taskHeaders: Record<string, string> = {
                "Content-Type": "application/json",
                Authorization: `Bearer ${authToken}`,
            }
            const title = selectedFiles.length === 1
                ? selectedFiles[0].name
                : `${selectedFiles[0].name} 等 ${selectedFiles.length} 个检材`

            const taskResp = await fetch(`${apiBase}/api/v1/tasks`, {
                method: "POST",
                headers: taskHeaders,
                body: JSON.stringify({
                    title,
                    input_type: inputType,
                    description: casePrompt.trim(),
                    priority_focus: priorityFocus,
                    metadata: {
                        share_to_casebase: shareToCasebase,
                        analysis_focus: selectedFocus,
                        case_prompt: casePrompt.trim(),
                        files: uploadedFiles,
                    },
                    storage_paths: {
                        files: uploadedFiles.map((file) => ({
                            id: file.id,
                            name: file.name,
                            mime_type: file.mime_type,
                            size_bytes: file.size_bytes,
                            modality: file.modality,
                            storage_path: file.storage_path,
                        })),
                    },
                }),
            })

            if (!taskResp.ok) {
                const errBody = await taskResp.json().catch(() => ({}))
                throw new Error(errBody.detail || "任务创建失败，请重试")
            }

            const taskData = await taskResp.json()
            setProgress(100)
            await new Promise((resolve) => setTimeout(resolve, 250))
            router.push(`/detect/${taskData.id}?focus=${priorityFocus}`)
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "上传失败，请重试"
            setError(msg)
            setUploading(false)
            setProgress(0)
        }
    }, [casePrompt, router, selectedFiles, selectedFocus, shareToCasebase])

    const onDrop = useCallback((event: React.DragEvent) => {
        event.preventDefault()
        setIsDragging(false)
        if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files)
    }, [addFiles])

    const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files?.length) addFiles(event.target.files)
        event.target.value = ""
    }

    return (
        <div className="w-full max-w-5xl mx-auto">
            <div className="relative overflow-hidden rounded-[2rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(245,243,239,0.98)_100%)] shadow-[0_30px_90px_rgba(15,23,42,0.10)] backdrop-blur-xl dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(30,30,34,0.94)_0%,rgba(18,18,22,0.98)_100%)] dark:shadow-[0_30px_120px_rgba(0,0,0,0.45)]">
                <div className="relative p-6 md:p-8 lg:p-10 space-y-6">
                    <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                        <div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-black/8 bg-black/[0.04] px-4 py-1.5 text-[11px] font-mono uppercase tracking-[0.22em] text-black/45 dark:border-white/10 dark:bg-white/5 dark:text-white/50">
                                AI Forensics Intake
                            </div>
                            <h2 className="mt-4 text-2xl md:text-3xl font-bold text-[#1B1B1F] tracking-tight dark:text-white">
                                多模态检材接入与全局任务提示
                            </h2>
                            <p className="mt-2 max-w-3xl text-sm md:text-base text-black/60 leading-relaxed dark:text-white/60">
                                上传视频、音频、图片或文本检材。
                            </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
                            {aspectOptions.map((option) => (
                                <button
                                    key={option}
                                    type="button"
                                    onClick={() => setSelectedFocus(option)}
                                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${selectedFocus === option ? "bg-[#6366F1] text-white shadow-[0_0_20px_rgba(99,102,241,0.20)]" : "border border-black/8 bg-black/[0.04] text-black/55 hover:bg-black/[0.07] dark:border-white/10 dark:bg-white/5 dark:text-white/55 dark:hover:bg-white/10"}`}
                                >
                                    {option}
                                </button>
                            ))}
                        </div>
                    </div>

                    <motion.div
                        onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }}
                        onDragLeave={() => setIsDragging(false)}
                        onDrop={onDrop}
                        animate={{
                            borderColor: isDragging ? "rgba(99,102,241,0.85)" : selectedFiles.length ? "rgba(16,185,129,0.40)" : "rgba(255,255,255,0.14)",
                            boxShadow: isDragging ? "0 0 40px rgba(99,102,241,0.25)" : selectedFiles.length ? "0 0 30px rgba(16,185,129,0.12)" : "0 12px 40px rgba(0,0,0,0.12)",
                        }}
                        className="rounded-[1.75rem] border border-dashed border-black/8 bg-black/[0.03] p-6 md:p-7 cursor-pointer dark:border-white/14 dark:bg-white/[0.03]"
                        onClick={() => !uploading && document.getElementById("file-input")?.click()}
                    >
                        <input id="file-input" type="file" multiple accept={ACCEPTED_EXT} className="hidden" onChange={onFileChange} />
                        <div className="flex items-start justify-between gap-4 mb-5">
                            <div>
                                <div className="text-lg md:text-xl font-semibold text-[#1F1F23] dark:text-white">多媒体上传区</div>
                                <div className="mt-1 text-sm text-black/50 dark:text-white/45">最多 5 个文件，视频、音频、图片文件会交给视听鉴伪Agent，文本文件会交给情报溯源Agent处理。</div>
                            </div>
                            <div className="text-right text-xs text-black/40 leading-5 dark:text-white/35">MP4 / WebM / MP3 / WAV / JPG / PNG / WebP / TXT<br />单文件最大 500MB</div>
                        </div>

                        {uploading ? (
                            <div className="space-y-5">
                                <div className="text-center">
                                    <p className="text-[#1F1F23] font-semibold text-lg dark:text-white">正在上传 {selectedFiles.length} 个检材</p>
                                    <p className="text-black/45 text-sm mt-1 dark:text-white/45">总计 {formatSize(totalSize)}</p>
                                </div>
                                <div className="w-full bg-black/8 rounded-full h-2 overflow-hidden dark:bg-white/10">
                                    <motion.div className="h-full rounded-full bg-gradient-to-r from-[#6366F1] via-[#10B981] to-[#D4FF12]" animate={{ width: `${progress}%` }} />
                                </div>
                                <p className="text-center text-[#789500] text-sm font-mono dark:text-[#D4FF12]">
                                    {progress < 100 ? `正在创建检测任务... ${Math.round(progress)}%` : "已启动多智能体分析"}
                                </p>
                            </div>
                        ) : (
                            <div className="rounded-[1.5rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.62)_0%,rgba(244,241,236,0.72)_100%)] px-6 py-8 text-center dark:border-white/10 dark:bg-black/20">
                                <p className="text-[#1E1E22] text-xl font-semibold dark:text-white">拖拽或点击上传检材</p>
                                <p className="mt-2 text-sm text-black/55 leading-relaxed dark:text-white/50">可混合提交视频、音频、图片和文本文件。</p>
                                <div className="mt-5 flex flex-wrap justify-center gap-2">
                                    {["VIDEO", "AUDIO", "IMAGE", "TEXT"].map((type) => (
                                        <span key={type} className="rounded-full border border-black/8 bg-black/[0.04] px-3 py-1 text-[11px] font-mono text-black/45 dark:border-white/10 dark:bg-white/5 dark:text-white/45">{type}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </motion.div>

                    {selectedFiles.length > 0 && (
                        <div className="grid gap-2">
                            {selectedFiles.map((file, index) => (
                                <div key={`${file.name}-${file.size}`} className="flex items-center justify-between gap-4 rounded-2xl border border-black/8 bg-white/55 px-4 py-3 dark:border-white/10 dark:bg-black/20">
                                    <div className="min-w-0">
                                        <div className="truncate text-sm font-medium text-[#1F1F23] dark:text-white">{file.name}</div>
                                        <div className="text-xs text-black/45 dark:text-white/40">{file.type || "unknown"} · {formatSize(file.size)}</div>
                                    </div>
                                    <button type="button" onClick={() => removeFile(index)} disabled={uploading} className="rounded-full border border-black/10 px-3 py-1 text-xs text-black/55 hover:bg-black/[0.06] disabled:opacity-50 dark:border-white/10 dark:text-white/60 dark:hover:bg-white/10">
                                        移除
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="rounded-[1.75rem] border border-black/8 bg-black/[0.03] p-6 md:p-7 dark:border-white/10 dark:bg-white/[0.03]">
                        <div className="flex items-center justify-between gap-4 mb-4">
                            <div>
                                <div className="text-lg md:text-xl font-semibold text-[#1F1F23] dark:text-white">检测提示词</div>
                                <div className="mt-1 text-sm text-black/50 dark:text-white/45">会同步给视听鉴伪、情报溯源、逻辑质询和研判指挥Agent。</div>
                            </div>
                            <button type="button" onClick={() => setCasePrompt(promptTemplates[0])} className="rounded-xl border border-[#6366F1]/20 bg-[#6366F1]/8 px-4 py-2 text-sm font-medium text-[#4F46E5] hover:bg-[#6366F1]/12 transition-colors dark:border-[#6366F1]/25 dark:bg-[#6366F1]/12 dark:text-[#C7C9FF] dark:hover:bg-[#6366F1]/18">
                                提示词模板
                            </button>
                        </div>
                        <textarea
                            value={casePrompt}
                            onChange={(event) => setCasePrompt(event.target.value)}
                            placeholder="例如：请重点判断该视频是否存在换脸、合成语音与传播链异常，并输出关键证据与处置建议。"
                            className="min-h-[180px] w-full resize-none rounded-[1.25rem] border border-black/8 bg-white/60 px-5 py-4 text-base leading-7 text-[#1F1F23] placeholder:text-black/30 focus:outline-none focus:ring-2 focus:ring-[#6366F1]/25 focus:border-[#6366F1]/30 transition-all dark:border-white/10 dark:bg-black/20 dark:text-white dark:placeholder:text-white/25 dark:focus:ring-[#6366F1]/40 dark:focus:border-[#6366F1]/40"
                        />
                        <div className="mt-5 flex flex-wrap gap-2">
                            {promptTemplates.map((template) => (
                                <button key={template} type="button" onClick={() => setCasePrompt(template)} className="rounded-full border border-black/8 bg-black/[0.04] px-3 py-1.5 text-xs text-black/55 hover:bg-black/[0.07] hover:text-black transition-colors dark:border-white/10 dark:bg-white/5 dark:text-white/55 dark:hover:bg-white/10 dark:hover:text-white">{template.slice(0, 14)}...</button>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-[1.75rem] border border-black/8 bg-black/[0.03] p-5 md:p-6 dark:border-white/10 dark:bg-white/[0.03]">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                            <div className="flex flex-wrap items-center gap-3">
                                <button type="button" onClick={launchAnalysis} disabled={uploading} className="inline-flex items-center justify-center rounded-2xl bg-gradient-to-r from-[#8B5CF6] via-[#A855F7] to-[#EC4899] px-8 py-3 text-sm md:text-base font-semibold text-white shadow-[0_10px_40px_rgba(168,85,247,0.35)] transition-transform hover:scale-[1.02] disabled:opacity-60 disabled:cursor-not-allowed">
                                    开始分析
                                </button>
                                <button type="button" onClick={() => setCasePrompt("")} disabled={uploading} className="rounded-2xl border border-black/8 bg-black/[0.04] px-5 py-3 text-sm font-medium text-black/70 hover:bg-black/[0.07] hover:text-black transition-colors disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white">
                                    清空提示词
                                </button>
                            </div>
                            <label className="flex items-center gap-3 rounded-2xl border border-black/8 bg-white/55 px-4 py-3 cursor-pointer dark:border-white/10 dark:bg-black/20">
                                <input type="checkbox" checked={shareToCasebase} onChange={(event) => setShareToCasebase(event.target.checked)} className="h-4 w-4 rounded border-black/20 bg-transparent accent-[#D4FF12] dark:border-white/20" />
                                <div>
                                    <div className="text-sm font-medium text-[#1F1F23] dark:text-white">愿意脱敏后公开至案例库</div>
                                    <div className="text-xs text-black/45 mt-0.5 dark:text-white/40">本次只记录意向，案例库真实加载后续升级</div>
                                </div>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
            <AnimatePresence>
                {error && (
                    <motion.p initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 text-[#EF4444] text-sm text-center">
                        {error}
                    </motion.p>
                )}
            </AnimatePresence>
        </div>
    )
}

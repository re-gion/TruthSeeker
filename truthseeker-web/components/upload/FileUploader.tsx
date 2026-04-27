"use client"

import { useCallback, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import Image from "next/image"
import { motion, AnimatePresence } from "motion/react"
import { BrainCircuit, Film, FileSearch, Mic } from "lucide-react"
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
    {
        label: "深伪取证",
        summary: "换脸/合成/篡改痕迹",
        prompt: "请以数字取证专家视角判断该内容是否存在 AI 伪造、换脸、合成语音、画面拼接或局部篡改痕迹。请优先列出可观察到的关键证据，包括面部边缘、眼口同步、光照阴影、压缩伪影、音画一致性和异常帧，并给出可信度判断。",
    },
    {
        label: "跨模态一致性",
        summary: "画面/音频/文本互证",
        prompt: "请重点检查视频画面、音频声纹、字幕文本、上下文描述之间是否一致。请指出人物身份、口型与语音、场景时间、背景物体、文本叙述之间的冲突点，并说明这些冲突是否足以支持伪造、剪辑误导或断章取义的判断。",
    },
    {
        label: "溯源传播链",
        summary: "URL/来源/扩散风险",
        prompt: "请围绕来源可信度与传播链进行分析：识别文件或链接中的来源线索、域名与账号可信度、可能的首发渠道、传播路径和二次加工痕迹。若存在诈骗、舆情操纵、钓鱼引流或恶意扩散风险，请给出风险等级和建议处置动作。",
    },
    {
        label: "诈骗风险",
        summary: "冒充身份/诱导转账",
        prompt: "请判断该内容是否可能用于诈骗或身份冒充场景。重点检查是否存在伪造领导、亲友、客服、金融机构或官方媒体口吻，以及诱导转账、索要验证码、制造紧迫感、承诺收益等风险信号。请输出可疑话术、证据片段和用户防护建议。",
    },
    {
        label: "司法报告",
        summary: "证据链/结论/建议",
        prompt: "请按专家报告格式分析该材料，输出：一、检测结论；二、关键证据；三、各 Agent 可能关注的疑点；四、证据链完整性与不足；五、是否建议人工复核；六、面向司法、平台治理或企业安全场景的处置建议。请避免只给笼统结论。",
    },
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
    const [templateIndex, setTemplateIndex] = useState(0)
    const [shareToCasebase, setShareToCasebase] = useState(false)
    const [selectedFocus, setSelectedFocus] = useState("多模态取证优先")

    const totalSize = useMemo(
        () => selectedFiles.reduce((sum, file) => sum + file.size, 0),
        [selectedFiles],
    )

    const cycleTemplate = useCallback(() => {
        const nextIndex = (templateIndex + 1) % promptTemplates.length
        setTemplateIndex(nextIndex)
        setCasePrompt(promptTemplates[nextIndex].prompt)
    }, [templateIndex])

    const applyTemplate = useCallback((index: number) => {
        setTemplateIndex(index)
        setCasePrompt(promptTemplates[index].prompt)
    }, [])

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
                                <div className="mt-1 text-sm text-black/50 dark:text-white/45 whitespace-nowrap">最多 5 个文件，全部检材会进入电子取证Agent，文本线索同时进入情报溯源Agent处理。</div>
                            </div>
                            <div className="text-right text-xs text-black/40 leading-5 dark:text-white/35">
                                <div>MP4 / WebM / MP3 / WAV / JPG / PNG /</div>
                                <div>WebP / TXT · 单文件最大 500MB</div>
                            </div>
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
                            <div className="relative overflow-hidden rounded-[1.5rem] border border-black/8 bg-[radial-gradient(circle_at_50%_20%,rgba(99,102,241,0.14),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.72)_0%,rgba(244,241,236,0.82)_100%)] px-6 py-10 text-center dark:border-white/10 dark:bg-[radial-gradient(circle_at_50%_20%,rgba(99,102,241,0.22),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.08)_0%,rgba(255,255,255,0.03)_100%)]">
                                <div className="pointer-events-none absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "radial-gradient(#fff 1px, transparent 1px)", backgroundSize: "18px 18px" }} />
                                <Image
                                    src="/loading-icon.svg"
                                    alt="智能检材扫描"
                                    width={80}
                                    height={80}
                                    className="relative mx-auto mb-5 h-20 w-20 drop-shadow-[0_0_18px_rgba(145,224,33,0.35)]"
                                    priority={false}
                                />
                                <p className="relative text-[#1E1E22] text-xl font-semibold dark:text-white">拖拽或点击上传检材</p>
                                <p className="relative mt-2 text-sm text-black/55 leading-relaxed dark:text-white/50">可混合提交视频、音频、图片和文本文件。</p>
                                <div className="relative mt-5 flex flex-wrap justify-center gap-2">
                                    {[
                                        ["VIDEO", Film],
                                        ["AUDIO", Mic],
                                        ["IMAGE", FileSearch],
                                        ["TEXT", BrainCircuit],
                                    ].map(([type, Icon]) => (
                                        <span key={type as string} className="inline-flex items-center gap-1.5 rounded-full border border-black/8 bg-black/[0.04] px-3 py-1 text-[11px] font-mono text-black/45 dark:border-white/10 dark:bg-white/5 dark:text-white/45">
                                            <Icon className="h-3 w-3" />
                                            {type as string}
                                        </span>
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
                                <div className="mt-1 text-sm text-black/50 dark:text-white/45">会同步给电子取证、情报溯源、逻辑质询和研判指挥Agent。</div>
                            </div>
                        </div>
                        <textarea
                            value={casePrompt}
                            onChange={(event) => setCasePrompt(event.target.value)}
                            placeholder="例如：请重点判断该视频是否存在换脸、合成语音与传播链异常，并输出关键证据与处置建议。"
                            className="min-h-[180px] w-full resize-none rounded-[1.25rem] border border-black/8 bg-white/60 px-5 py-4 text-base leading-7 text-[#1F1F23] placeholder:text-black/30 focus:outline-none focus:ring-2 focus:ring-[#6366F1]/25 focus:border-[#6366F1]/30 transition-all dark:border-white/10 dark:bg-black/20 dark:text-white dark:placeholder:text-white/25 dark:focus:ring-[#6366F1]/40 dark:focus:border-[#6366F1]/40"
                        />
                        <div className="mt-5 flex gap-1.5 overflow-x-auto whitespace-nowrap pb-1">
                            {promptTemplates.map((template, index) => (
                                <button
                                    key={template.label}
                                    type="button"
                                    onClick={() => applyTemplate(index)}
                                    className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] leading-none transition-colors ${templateIndex === index
                                        ? "border-[#6366F1]/30 bg-[#6366F1]/12 text-[#4F46E5] dark:border-[#6366F1]/35 dark:bg-[#6366F1]/18 dark:text-[#C7C9FF]"
                                        : "border-black/8 bg-black/[0.04] text-black/55 hover:bg-black/[0.07] hover:text-black dark:border-white/10 dark:bg-white/5 dark:text-white/55 dark:hover:bg-white/10 dark:hover:text-white"
                                        }`}
                                >
                                    <span className="font-semibold">{template.label}</span>
                                    <span className="ml-1 opacity-65">{template.summary}</span>
                                </button>
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
                                <button type="button" onClick={cycleTemplate} disabled={uploading} className="rounded-2xl border border-[#6366F1]/20 bg-[#6366F1]/8 px-5 py-3 text-sm font-medium text-[#4F46E5] hover:bg-[#6366F1]/12 transition-colors disabled:opacity-50 dark:border-[#6366F1]/25 dark:bg-[#6366F1]/12 dark:text-[#C7C9FF] dark:hover:bg-[#6366F1]/18">
                                    换一个模板
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

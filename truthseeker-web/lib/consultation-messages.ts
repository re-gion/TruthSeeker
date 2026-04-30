export type PanelRole = "host" | "expert" | "viewer" | "commander"

export interface ConsultationComment {
    id: string
    clientMessageId?: string
    authorId: string
    role: PanelRole
    text: string
    timestamp: string
    messageType?: string
    anchorAgent?: string
    phase?: string
    confidence?: number
    suggestedAction?: string
    optimistic?: boolean
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null
}

function readString(value: unknown): string | undefined {
    return typeof value === "string" && value.trim() ? value : undefined
}

function readNumber(value: unknown): number | undefined {
    return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function normalizeRole(value: unknown): PanelRole {
    if (value === "user" || value === "host") return "host"
    if (value === "commander") return "commander"
    if (value === "viewer") return "viewer"
    return "expert"
}

function readClientMessageId(item: Record<string, unknown>) {
    const metadata = isRecord(item.metadata) ? item.metadata : null
    return readString(item.clientMessageId)
        ?? readString(item.client_message_id)
        ?? readString(metadata?.client_message_id)
        ?? readString(metadata?.clientMessageId)
}

export function normalizeConsultationMessage(item: Record<string, unknown>): ConsultationComment {
    return {
        id: readString(item.id) ?? Math.random().toString(36).substring(7),
        clientMessageId: readClientMessageId(item),
        authorId: readString(item.authorId) ?? readString(item.expert_name) ?? "expert",
        role: normalizeRole(item.role),
        text: readString(item.text) ?? readString(item.message) ?? "",
        timestamp: readString(item.timestamp) ?? readString(item.created_at) ?? new Date().toISOString(),
        messageType: readString(item.messageType) ?? readString(item.message_type),
        anchorAgent: readString(item.anchorAgent) ?? readString(item.anchor_agent),
        phase: readString(item.phase) ?? readString(item.anchor_phase),
        confidence: readNumber(item.confidence),
        suggestedAction: readString(item.suggestedAction) ?? readString(item.suggested_action),
        optimistic: item.optimistic === true,
    }
}

function canReplaceOptimistic(existing: ConsultationComment, incoming: ConsultationComment) {
    return existing.optimistic
        && existing.role === incoming.role
        && existing.authorId === incoming.authorId
        && existing.text === incoming.text
}

export function mergeConsultationComments(
    current: ConsultationComment[],
    incoming: Array<ConsultationComment | null | undefined>,
): ConsultationComment[] {
    const merged = [...current]

    for (const comment of incoming) {
        if (!comment) continue

        const idIndex = merged.findIndex(item => item.id === comment.id)
        if (idIndex >= 0) {
            merged[idIndex] = { ...merged[idIndex], ...comment, optimistic: comment.optimistic ?? false }
            continue
        }

        const clientIndex = comment.clientMessageId
            ? merged.findIndex(item => item.clientMessageId === comment.clientMessageId)
            : -1
        if (clientIndex >= 0) {
            merged[clientIndex] = { ...merged[clientIndex], ...comment, optimistic: comment.optimistic ?? false }
            continue
        }

        const optimisticIndex = merged.findIndex(item => canReplaceOptimistic(item, comment))
        if (optimisticIndex >= 0) {
            merged[optimisticIndex] = { ...merged[optimisticIndex], ...comment, optimistic: comment.optimistic ?? false }
            continue
        }

        merged.push(comment)
    }

    return merged.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
}

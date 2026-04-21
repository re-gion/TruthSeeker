"use client"

import { useEffect, useMemo, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export type UserRole = 'host' | 'expert' | 'viewer'

export interface PresenceState {
    user_id: string
    role: UserRole
    joined_at: string
}

export function useRealtimeSession(taskId: string, role: UserRole = 'host') {
    const [onlineUsers, setOnlineUsers] = useState<PresenceState[]>([])
    const userId = useMemo(() => {
        if (typeof window === "undefined") return "anon"

        const storedUserId = window.localStorage.getItem("temp_user_id")
        if (storedUserId) return storedUserId

        const generatedUserId = window.crypto.randomUUID()
        window.localStorage.setItem("temp_user_id", generatedUserId)
        return generatedUserId
    }, [])

    const channel = useMemo(() => {
        if (typeof window === "undefined") {
            return null
        }

        const supabase = createClient()
        return supabase.channel(`task:${taskId}`, {
            config: {
                presence: { key: userId },
            },
        })
    }, [taskId, userId])

    useEffect(() => {
        if (!channel) return

        const handlePresenceSync = () => {
            const state = channel.presenceState() as unknown as Record<string, Array<Partial<PresenceState> | undefined>>
            const users: PresenceState[] = []

            for (const key of Object.keys(state)) {
                const userState = state[key]?.[0]
                if (!userState) continue

                users.push({
                    user_id: key,
                    role: userState.role ?? role,
                    joined_at: userState.joined_at ?? new Date().toISOString(),
                })
            }

            setOnlineUsers(users)
        }

        channel
            .on('presence', { event: 'sync' }, () => {
                handlePresenceSync()
            })
            .subscribe(async (status: string) => {
                if (status === 'SUBSCRIBED') {
                    await channel.track({
                        role,
                        joined_at: new Date().toISOString(),
                    })
                }
            })

        return () => {
            void channel.unsubscribe()
        }
    }, [channel, role])

    return { channel, onlineUsers }
}

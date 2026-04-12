"use client"

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { RealtimeChannel } from '@supabase/supabase-js'

export type UserRole = 'host' | 'expert' | 'viewer'

export interface PresenceState {
    user_id: string
    role: UserRole
    joined_at: string
}

export function useRealtimeSession(taskId: string, role: UserRole = 'host') {
    const [channel, setChannel] = useState<RealtimeChannel | null>(null)
    const [onlineUsers, setOnlineUsers] = useState<PresenceState[]>([])

    useEffect(() => {
        const supabase = createClient()
        // Generate a random user id if none exists (for MVP)
        const userId = typeof window !== 'undefined' ?
            (localStorage.getItem('temp_user_id') || Math.random().toString(36).substring(7)) : 'anon'

        if (typeof window !== 'undefined' && !localStorage.getItem('temp_user_id')) {
            localStorage.setItem('temp_user_id', userId)
        }

        const newChannel = supabase.channel(`task_${taskId}`, {
            config: {
                presence: { key: userId },
            },
        })

        newChannel
            .on('presence', { event: 'sync' }, () => {
                const state = newChannel.presenceState()
                const users: PresenceState[] = []
                for (const key in state) {
                    // Suppress type errors for now; presenceState returns unknown array
                    const userState = state[key][0] as any
                    if (userState) {
                        users.push({
                            user_id: key,
                            role: userState.role as UserRole,
                            joined_at: userState.joined_at as string
                        })
                    }
                }
                setOnlineUsers(users)
            })
            .subscribe(async (status) => {
                if (status === 'SUBSCRIBED') {
                    await newChannel.track({
                        role,
                        joined_at: new Date().toISOString(),
                    })
                }
            })

        setChannel(newChannel)

        return () => {
            newChannel.unsubscribe()
        }
    }, [taskId, role])

    return { channel, onlineUsers }
}

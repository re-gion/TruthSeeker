"use server"

import { createClient } from "@/lib/supabase/server"
import { redirect } from "next/navigation"

export async function signUp(formData: FormData) {
    const supabase = await createClient()
    const { error } = await supabase.auth.signUp({
        email: formData.get("email") as string,
        password: formData.get("password") as string,
    })
    if (error) return { error: error.message }
    return { success: true }
}

export async function signIn(formData: FormData) {
    const supabase = await createClient()
    const { error } = await supabase.auth.signInWithPassword({
        email: formData.get("email") as string,
        password: formData.get("password") as string,
    })
    if (error) return { error: error.message }
    redirect("/")
}

export async function signOut() {
    const supabase = await createClient()
    await supabase.auth.signOut()
    redirect("/login")
}

export async function resetPassword(formData: FormData) {
    const supabase = await createClient()
    const email = formData.get("email") as string
    const redirectTo = `${process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"}/reset-password`
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo,
    })
    if (error) return { error: error.message }
    return { success: true }
}

export async function updatePassword(formData: FormData) {
    const supabase = await createClient()
    const password = formData.get("password") as string
    const { error } = await supabase.auth.updateUser({ password })
    if (error) return { error: error.message }
    return { success: true }
}

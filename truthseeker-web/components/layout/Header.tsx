import { createClient, getUserSafe } from "@/lib/supabase/server"
import { HeaderClient } from "@/components/layout/HeaderClient"

export default async function Header() {
    const supabase = await createClient()
    const user = await getUserSafe(supabase)

    return <HeaderClient user={user ? { email: user.email ?? "" } : null} />
}

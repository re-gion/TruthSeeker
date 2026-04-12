import { createClient } from "@/lib/supabase/server"
import { HeaderClient } from "@/components/layout/HeaderClient"

export default async function Header() {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()

    return <HeaderClient user={user ? { email: user.email ?? "" } : null} />
}

import Link from 'next/link'

import { COPY } from '@/constants/copy.constant'
import { ROUTE } from '@/constants/route.constant'

/** The bar every page wears, with the name as the way back to the form. */
const SiteHeader = () => {
    return (
        <header className="border-b border-line bg-canvas">
            <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-3 py-3 sm:px-6 sm:py-4">
                <Link href={ROUTE.scanForm} className="flex items-center gap-2">
                    <span className="size-2.5 rounded-full bg-accent" />
                    <span className="text-base font-semibold tracking-tight text-ink">
                        {COPY.appTitle}
                    </span>
                </Link>
                <span className="hidden text-xs font-medium uppercase tracking-widest text-ink-faint sm:inline">
                    {COPY.appKicker}
                </span>
            </div>
        </header>
    )
}

export default SiteHeader

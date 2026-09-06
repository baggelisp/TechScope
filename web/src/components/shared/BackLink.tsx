import Link from 'next/link'

export type BackLinkProps = {
    href: string
    label: string
}

/**
 * The way out of a page that is not the first one.
 *
 * A plain link to where the page came from, not a history call: it works on a shared URL, on a
 * fresh tab, and without any JavaScript.
 */
const BackLink = ({ href, label }: BackLinkProps) => {
    return (
        <Link
            href={href}
            className="inline-flex w-fit items-center gap-2 text-sm font-medium text-ink-muted transition-colors hover:text-ink"
        >
            <span aria-hidden="true">&larr;</span>
            <span>{label}</span>
        </Link>
    )
}

export default BackLink

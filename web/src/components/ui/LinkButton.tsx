import Link from 'next/link'

export type LinkButtonVariant = 'secondary' | 'danger'

export type LinkButtonProps = {
    children: React.ReactNode
    href: string
    variant: LinkButtonVariant
}

const LINK_BUTTON_CLASS_NAME: Record<LinkButtonVariant, string> = {
    secondary:
        'rounded-lg border border-line-strong bg-surface px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-ink-faint hover:bg-surface-raised',
    danger: 'rounded-lg border border-peach/30 bg-transparent px-4 py-2.5 text-sm font-medium text-peach transition-colors hover:bg-peach/10',
}

const LinkButton = ({ children, href, variant }: LinkButtonProps) => {
    return (
        <Link href={href} className={LINK_BUTTON_CLASS_NAME[variant]}>
            {children}
        </Link>
    )
}

export default LinkButton

export type TagTone = 'accent' | 'lilac' | 'sky' | 'mint' | 'peach' | 'neutral'

export type TagProps = {
    children: React.ReactNode
    tone: TagTone
}

const TAG_CLASS_NAME: Record<TagTone, string> = {
    accent: 'bg-accent/15 text-accent ring-accent/25',
    lilac: 'bg-lilac/15 text-lilac ring-lilac/25',
    sky: 'bg-sky/15 text-sky ring-sky/25',
    mint: 'bg-mint/15 text-mint ring-mint/25',
    peach: 'bg-peach/15 text-peach ring-peach/25',
    neutral: 'bg-white/5 text-ink-muted ring-white/10',
}

const Tag = ({ children, tone }: TagProps) => {
    return (
        <span
            className={`rounded-md px-2.5 py-0.5 text-xs font-medium ring-1 ${TAG_CLASS_NAME[tone]}`}
        >
            {children}
        </span>
    )
}

export default Tag

export type CheckIconProps = {
    isDimmed: boolean
}

/** A tick, drawn rather than typed, so it keeps its weight at any size. */
const CheckIcon = ({ isDimmed }: CheckIconProps) => {
    const className = decideClassName(isDimmed)

    return (
        <svg
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={className}
        >
            <path d="M4.5 10.5l3.6 3.6 7.4-8.2" />
        </svg>
    )
}

export default CheckIcon

function decideClassName(isDimmed: boolean): string {
    if (isDimmed) return 'size-4 text-accent/45'

    return 'size-4 text-accent'
}

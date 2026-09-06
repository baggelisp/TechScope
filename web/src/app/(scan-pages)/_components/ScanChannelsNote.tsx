import { COPY } from '@/constants/copy.constant'

const ScanChannelsNote = () => {
    return (
        <div className="flex flex-col items-center gap-1 text-center">
            <span className="text-xs font-medium uppercase tracking-widest text-ink-faint">
                {COPY.channelsHeading}
            </span>
            <p className="max-w-xl text-sm leading-relaxed text-ink-muted">{COPY.channelsBody}</p>
        </div>
    )
}

export default ScanChannelsNote

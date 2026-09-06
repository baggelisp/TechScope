import { COPY } from '@/constants/copy.constant'

/** The one thing the landing page says before it asks for anything. */
const ScanHero = () => {
    return (
        <div className="flex flex-col items-center gap-4 text-center">
            <h1 className="max-w-2xl text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-4xl lg:text-5xl">
                {COPY.heroHeadline}
            </h1>
            <p className="max-w-xl text-sm leading-relaxed text-ink-muted sm:text-base">{COPY.heroBody}</p>
        </div>
    )
}

export default ScanHero

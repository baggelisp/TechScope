import BackLink from '@/components/shared/BackLink'
import { COPY } from '@/constants/copy.constant'
import { ROUTE } from '@/constants/route.constant'

export type DomainScanPageHeaderProps = {
    domain: string
}

const DomainScanPageHeader = ({ domain }: DomainScanPageHeaderProps) => {
    return (
        <div className="flex flex-col gap-4">
            <BackLink href={ROUTE.scanForm} label={COPY.backToForm} />
            <div className="flex flex-col gap-1">
                <h1 className="break-all text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
                    {domain}
                </h1>
                <p className="text-sm text-ink-muted">{COPY.domainHeadingSuffix}</p>
            </div>
        </div>
    )
}

export default DomainScanPageHeader

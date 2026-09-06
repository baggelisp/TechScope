import { COPY } from '@/constants/copy.constant'

export type DomainScanDetailHeadingProps = {
    isVisible: boolean
}

const DomainScanDetailHeading = ({ isVisible }: DomainScanDetailHeadingProps) => {
    if (isVisible) {
        return (
            <h2 className="text-base font-semibold tracking-tight text-ink sm:text-lg">
                {COPY.domainDetailHeading}
            </h2>
        )
    }

    return null
}

export default DomainScanDetailHeading

import Link from 'next/link'

import ScanResultsMatrixRowRedirect from './ScanResultsMatrixRowRedirect'
import type { DomainResult } from '@/api/schemas'
import { buildDomainRoute } from '@/constants/route.constant'
import RedirectUtility from '@/utils/RedirectUtility'

export type ScanResultsMatrixRowDomainProps = {
    domain: DomainResult
}

/**
 * The domain, and where its signals were actually read from.
 *
 * Four of the assignment's own domains redirect to the company that acquired them, so a
 * detection is only honest if the page it came from is on the record.
 */
const ScanResultsMatrixRowDomain = ({ domain }: ScanResultsMatrixRowDomainProps) => {
    const redirect = RedirectUtility.decideRedirectOrNull(domain.domain, domain.observed_url)

    return (
        <th
            scope="row"
            className="sticky left-0 z-10 bg-surface px-3 py-3 text-left align-middle font-medium text-ink sm:px-4"
        >
            <div className="flex flex-col gap-0.5">
                <Link
                    href={buildDomainRoute(domain.domain)}
                    className="w-fit text-ink underline decoration-line-strong underline-offset-4 transition-colors hover:decoration-accent"
                >
                    {domain.domain}
                </Link>
                <ScanResultsMatrixRowRedirect redirect={redirect} />
            </div>
        </th>
    )
}

export default ScanResultsMatrixRowDomain

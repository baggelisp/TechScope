import { redirect } from 'next/navigation'

import DomainScanView from './_components/DomainScanView'
import { ROUTE } from '@/constants/route.constant'
import DomainListUtility from '@/utils/DomainListUtility'

type DomainScanPageProps = {
    params: Promise<{ domain: string }>
}

/** One domain, or back to the form if what arrived in the path is not one. */
const DomainScanPage = async ({ params }: DomainScanPageProps) => {
    const { domain: written } = await params
    const domain = DomainListUtility.decideFirstOrNull(decodeURIComponent(written))

    if (domain) return <DomainScanView domain={domain} />

    redirect(ROUTE.scanForm)
}

export default DomainScanPage

import ScanChannelsNote from '@/app/(scan-pages)/_components/ScanChannelsNote'
import ScanFormCard from '@/app/(scan-pages)/_components/ScanFormCard'
import ScanHero from '@/app/(scan-pages)/_components/ScanHero'
import PageContainer from '@/components/layout/PageContainer'
import SiteHeader from '@/components/layout/SiteHeader'

/** The form. It fetches nothing: a scan is something a person asks for. */
const ScanFormPage = () => {
    return (
        <div className="min-h-screen bg-canvas">
            <SiteHeader />
            <PageContainer>
                <ScanHero />
                <ScanFormCard />
                <ScanChannelsNote />
            </PageContainer>
        </div>
    )
}

export default ScanFormPage

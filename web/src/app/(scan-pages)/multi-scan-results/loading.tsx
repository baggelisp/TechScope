import PageContainer from '@/components/layout/PageContainer'
import SiteHeader from '@/components/layout/SiteHeader'
import LoadingPanel from '@/components/shared/LoadingPanel'
import { COPY } from '@/constants/copy.constant'

/** Streamed in while the page above runs the scan. */
const Loading = () => {
    return (
        <div className="min-h-screen bg-canvas">
            <SiteHeader />
            <PageContainer>
                <LoadingPanel title={COPY.pendingHeading} message={COPY.pendingBody} />
            </PageContainer>
        </div>
    )
}

export default Loading

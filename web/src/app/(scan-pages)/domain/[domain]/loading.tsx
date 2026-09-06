import PageContainer from '@/components/layout/PageContainer'
import SiteHeader from '@/components/layout/SiteHeader'
import LoadingPanel from '@/components/shared/LoadingPanel'
import { COPY } from '@/constants/copy.constant'

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

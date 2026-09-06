import Tag from '@/components/ui/Tag'
import { decideChannelPresentation } from '@/constants/channel.constant'

export type ScanEvidenceChannelTagProps = {
    channel: string
}

const ScanEvidenceChannelTag = ({ channel }: ScanEvidenceChannelTagProps) => {
    const presentation = decideChannelPresentation(channel)

    return (
        <div className="flex">
            <Tag tone={presentation.tone}>{presentation.label}</Tag>
        </div>
    )
}

export default ScanEvidenceChannelTag

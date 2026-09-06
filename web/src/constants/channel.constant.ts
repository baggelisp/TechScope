/**
 * How each signal channel is described and coloured.
 *
 * One registry keyed by the channel, so a channel the scanner adds is one entry here rather than
 * a hunt for every place a channel name is turned into a label.
 */

import { CHANNEL, type Channel } from '@/api/schemas'
import type { TagTone } from '@/components/ui/Tag'

export type ChannelPresentation = {
    label: string
    tone: TagTone
}

export const UNKNOWN_CHANNEL_PRESENTATION: ChannelPresentation = {
    label: 'Other',
    tone: 'neutral',
}

export const CHANNEL_PRESENTATION: Record<Channel, ChannelPresentation> = {
    [CHANNEL.header]: {
        label: 'Response header',
        tone: 'sky',
    },
    [CHANNEL.cookie]: {
        label: 'Cookie',
        tone: 'peach',
    },
    [CHANNEL.scriptSrc]: {
        label: 'Script src',
        tone: 'lilac',
    },
    [CHANNEL.scriptInline]: {
        label: 'Inline script',
        tone: 'lilac',
    },
    [CHANNEL.html]: {
        label: 'HTML',
        tone: 'peach',
    },
    [CHANNEL.meta]: {
        label: 'Meta tag',
        tone: 'mint',
    },
    [CHANNEL.jsGlobal]: {
        label: 'JavaScript global',
        tone: 'lilac',
    },
    [CHANNEL.dnsMx]: {
        label: 'DNS MX',
        tone: 'accent',
    },
    [CHANNEL.dnsTxt]: {
        label: 'DNS TXT',
        tone: 'accent',
    },
    [CHANNEL.dnsCname]: {
        label: 'DNS CNAME',
        tone: 'accent',
    },
}

export const decideChannelPresentation = (channel: string): ChannelPresentation => {
    const known = Object.values(CHANNEL).find((value) => value === channel)

    if (known) return CHANNEL_PRESENTATION[known]

    return UNKNOWN_CHANNEL_PRESENTATION
}

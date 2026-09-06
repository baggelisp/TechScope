import { describe, expect, it } from 'vitest'

import EvidenceAnchorUtility from '@/utils/EvidenceAnchorUtility'

describe('EvidenceAnchorUtility.buildId', () => {
    it('builds an id from a cell position', () => {
        expect(EvidenceAnchorUtility.buildId(3, 7)).toBe('evidence-3-7')
    })

    it('handles the first cell', () => {
        expect(EvidenceAnchorUtility.buildId(0, 0)).toBe('evidence-0-0')
    })

    it('gives every cell of a row a different id', () => {
        expect(EvidenceAnchorUtility.buildId(2, 0)).not.toBe(EvidenceAnchorUtility.buildId(2, 1))
    })

    it('gives the same column in different rows different ids', () => {
        expect(EvidenceAnchorUtility.buildId(0, 5)).not.toBe(EvidenceAnchorUtility.buildId(1, 5))
    })

    it('cannot be made to collide by punctuation, which a name slug could', () => {
        const positions = [
            [0, 0],
            [0, 1],
            [1, 0],
            [1, 1],
        ] as const
        const ids = positions.map(([row, column]) => EvidenceAnchorUtility.buildId(row, column))

        expect(new Set(ids).size).toBe(positions.length)
    })
})

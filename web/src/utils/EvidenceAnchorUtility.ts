/**
 * The id that ties one matrix cell to the popover holding its evidence.
 *
 * The browser opens a popover by id, which is what lets the whole results page stay a server
 * component: no state, no handler, no client bundle for something the platform already does.
 *
 * The id is built from the cell's position rather than from its domain and technology. A slug of
 * those two collides — `foo-bar.com` and `foo.bar.com` reduce to the same text — and two cells
 * sharing an id both open the first popover, which puts one domain's evidence under another's
 * name on the one page whose whole purpose is evidence. A position cannot collide.
 */

const ID_PREFIX = 'evidence'
const ID_SEPARATOR = '-'

class EvidenceAnchorUtility {
    static buildId(rowIndex: number, columnIndex: number): string {
        return [ID_PREFIX, rowIndex, columnIndex].join(ID_SEPARATOR)
    }
}

export default EvidenceAnchorUtility

/** Handing the browser a file built in the page, with no round trip to make it. */

class DownloadUtility {
    static saveText(fileName: string, mediaType: string, contents: string): void {
        const blob = new Blob([contents], { type: mediaType })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = fileName
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }
}

export default DownloadUtility

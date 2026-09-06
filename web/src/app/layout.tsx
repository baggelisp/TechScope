import type { Metadata, Viewport } from 'next'

import { COPY } from '@/constants/copy.constant'

import './globals.css'

export const metadata: Metadata = {
    title: COPY.appTitle,
    description: COPY.appTagline,
}

/** Stated rather than inherited: every page here is laid out for a phone first. */
export const viewport: Viewport = {
    width: 'device-width',
    initialScale: 1,
}

const RootLayout = ({ children }: Readonly<{ children: React.ReactNode }>) => {
    return (
        <html lang="en">
            <body className="min-h-screen bg-canvas font-sans text-ink antialiased">
                {children}
            </body>
        </html>
    )
}

export default RootLayout

import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Immigration Document Assistant',
  description: 'Explainable RAG for German Immigration Documents — MSc Thesis',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  )
}

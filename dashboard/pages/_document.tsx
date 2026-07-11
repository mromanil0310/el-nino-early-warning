import { Html, Head, Main, NextScript } from 'next/document'
import { supabaseUrl } from '../lib/supabase'

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta name="theme-color" content="#166534" />
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        {/* Shave the connection setup off the first data fetch */}
        {supabaseUrl && <link rel="preconnect" href={supabaseUrl} crossOrigin="anonymous" />}
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  )
}

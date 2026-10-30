import { useEffect, useState } from 'react'

// the 1850 Lewistown gazette article that scripts/load_skeleton.py loads
const ARTICLE = '9_1850-07-26_p1_sn83032276_00296028587_1850072601_0265.json'

type Article = {
  paper: string
  date: string
  display_headline: string
  text: string
  crop_urls: string[]
}

function App() {
  const [article, setArticle] = useState<Article>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    fetch(`/api/skeleton/${encodeURIComponent(ARTICLE)}`)
      .then((response) =>
        response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)),
      )
      .then(setArticle, (failure: Error) => setError(failure.message))
  }, [])

  if (error) return <main><p>The article could not be loaded ({error}).</p></main>
  if (!article) return <main><p>Loading the article…</p></main>
  return (
    <main
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(18rem, 1fr))',
        gap: '2rem',
        padding: '1rem',
      }}
    >
      <div>
        {article.crop_urls.map((url, part) => (
          <img
            key={url}
            src={url}
            alt={`The clipping, part ${part + 1} of ${article.crop_urls.length}`}
            style={{ width: '100%', display: 'block' }}
          />
        ))}
      </div>
      <article>
        <h1 style={{ whiteSpace: 'pre-line' }}>{article.display_headline}</h1>
        <p>
          {article.paper}, {article.date}
        </p>
        <p style={{ whiteSpace: 'pre-wrap' }}>{article.text}</p>
      </article>
    </main>
  )
}

export default App

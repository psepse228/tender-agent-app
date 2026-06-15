module.exports = async function handler(req, res) {
  const url = req.query.url || 'https://etender.uzex.uz';

  try {
    const r = await fetch('https://api.firecrawl.dev/v1/scrape', {
      method:  'POST',
      headers: {
        'Authorization': `Bearer ${process.env.FIRECRAWL_API_KEY}`,
        'Content-Type':  'application/json',
      },
      body:   JSON.stringify({ url, formats: ['markdown'], onlyMainContent: true }),
      signal: AbortSignal.timeout(25000),
    });

    const data = await r.json();
    const markdown = data.data?.markdown || data.markdown || '';

    res.json({
      status:        r.status,
      ok:            r.ok,
      markdownChars: markdown.length,
      preview:       markdown.slice(0, 1000),
      firecrawlKey:  process.env.FIRECRAWL_API_KEY ? 'set' : 'MISSING',
      openaiKey:     process.env.OPENAI_API_KEY    ? 'set' : 'MISSING',
      airtableKey:   process.env.AIRTABLE_API_KEY  ? 'set' : 'MISSING',
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
};

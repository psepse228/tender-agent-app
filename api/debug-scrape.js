const { client } = require('./_supabase');

module.exports = async function handler(req, res) {
  const url = req.query.url || 'https://etender.uzex.uz';

  const keys = {
    firecrawl: process.env.FIRECRAWL_API_KEY ? 'set' : 'MISSING',
    openai:    process.env.OPENAI_API_KEY    ? 'set' : 'MISSING',
    supabase:  process.env.SUPABASE_URL && process.env.SUPABASE_KEY ? 'set' : 'MISSING',
  };

  // Test Supabase connection
  let supabaseTest = {};
  try {
    const { data, error } = await client().from('profile').select('id').limit(1);
    supabaseTest = error ? { error: error.message } : { ok: true, rows: data?.length };
  } catch (e) {
    supabaseTest = { error: e.message };
  }

  // Test Firecrawl
  let firecrawlTest = {};
  try {
    const r = await fetch('https://api.firecrawl.dev/v1/scrape', {
      method:  'POST',
      headers: { 'Authorization': `Bearer ${process.env.FIRECRAWL_API_KEY}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify({ url, formats: ['markdown'], onlyMainContent: true }),
      signal:  AbortSignal.timeout(20000),
    });
    const data     = await r.json();
    const markdown = data.data?.markdown || data.markdown || '';
    firecrawlTest  = { status: r.status, ok: r.ok, chars: markdown.length, preview: markdown.slice(0, 500) };
  } catch (e) {
    firecrawlTest = { error: e.message };
  }

  res.json({ keys, supabaseTest, firecrawlTest });
};

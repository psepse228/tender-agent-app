const OpenAI        = require('openai');
const { client }    = require('./_supabase');

const PROFILE_TABLE = 'profile';
const TENDERS_TABLE = 'tenders';
const FIRECRAWL_URL = 'https://api.firecrawl.dev/v1/scrape';

const SOURCES = [
  { name: 'eTender UzEx', url: 'https://etender.uzex.uz' },
  { name: 'XT-Xarid',     url: 'https://xt-xarid.uz' },
  { name: 'TenderWeek',   url: 'https://tenderweek.com' },
  { name: 'ADB',          url: 'https://www.adb.org/projects?filter=business_opportunity' },
  { name: 'World Bank',   url: 'https://projects.worldbank.org/en/projects-operations/procurement' },
  { name: 'BicоTender',   url: 'https://bicotender.ru' },
];

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();

  try {
    const sb = client();

    // 1. Load company profile
    const { data: profileRows } = await sb.from(PROFILE_TABLE).select('data').limit(1);
    const profileText = profileRows?.[0]?.data || 'No profile configured yet.';

    // 2. Scrape + score each source in parallel (pipeline per source)
    const results = await Promise.allSettled(
      SOURCES.map(async (source) => {
        const markdown = await scrapeSource(source);
        if (!markdown) return [];
        return extractAndScore(markdown, source, profileText);
      })
    );

    // 3. Flatten — keep everything with a title
    const tenders = results
      .filter(r => r.status === 'fulfilled')
      .flatMap(r => r.value)
      .filter(t => t.title);

    const perSource = SOURCES.map((s, i) => ({
      name:   s.name,
      status: results[i].status,
      count:  results[i].status === 'fulfilled' ? results[i].value.length : 0,
    }));
    console.log('Per-source:', JSON.stringify(perSource));
    console.log('Total tenders found:', tenders.length);

    // 4. Return to client immediately
    res.status(200).json({ tenders, debug: perSource });

    // 5. Persist to Supabase in background
    try {
      await sb.from(TENDERS_TABLE).delete().neq('id', '00000000-0000-0000-0000-000000000000');
      if (tenders.length) {
        await sb.from(TENDERS_TABLE).insert(tenders.map(toRow));
      }
      console.log('Supabase save complete');
    } catch (saveErr) {
      console.error('Supabase save failed (non-fatal):', saveErr.message);
    }

  } catch (e) {
    console.error('Refresh error:', e.message);
    res.status(500).json({ error: e.message, tenders: [] });
  }
};

// ── FIRECRAWL ──────────────────────────────────────────────────────────────

async function scrapeSource(source) {
  try {
    const res = await fetch(FIRECRAWL_URL, {
      method:  'POST',
      headers: {
        'Authorization': `Bearer ${process.env.FIRECRAWL_API_KEY}`,
        'Content-Type':  'application/json',
      },
      body:   JSON.stringify({ url: source.url, formats: ['markdown'], onlyMainContent: true }),
      signal: AbortSignal.timeout(25000),
    });
    if (!res.ok) {
      console.warn(`Firecrawl ${res.status} for ${source.name}`);
      return null;
    }
    const data = await res.json();
    return data.data?.markdown || data.markdown || null;
  } catch (e) {
    console.warn(`Firecrawl failed for ${source.name}:`, e.message);
    return null;
  }
}

// ── GPT-4o EXTRACTION + SCORING ───────────────────────────────────────────

async function extractAndScore(markdown, source, profileText) {
  const openai  = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const content = markdown.slice(0, 8000);

  const systemPrompt = `You are a tender analyst for a company in Tashkent, Uzbekistan.

Company profile:
${profileText}

Extract all tenders from the page content and score each for relevance to this company.

Scoring rules:
- If budget is missing or unclear → set "financial" to 40-50 (NEVER 0)
- matchPercent = compliance×0.4 + financial×0.2 + feasibility×0.25 + winChance×0.15
- matchPercent ≥ 70 → recommendation = "Подать заявку"
- matchPercent 40–69 → recommendation = "Рассмотреть"
- matchPercent < 40 → recommendation = "Пропустить"

Return ONLY valid JSON: { "tenders": [ ... ] }

Each tender object:
{
  "title": "string",
  "organization": "string",
  "budget": "string or null",
  "deadline": "string or null",
  "url": "string or null",
  "matchPercent": number 0-100,
  "recommendation": "Подать заявку" | "Рассмотреть" | "Пропустить",
  "compliance": number 0-100,
  "financial": number 0-100,
  "feasibility": number 0-100,
  "winChance": number 0-100,
  "whyParticipate": "string",
  "risks": "string",
  "actionPlan": "string",
  "riskLevel": "Низкий" | "Средний" | "Высокий",
  "profitPotential": "Низкий" | "Средний" | "Высокий"
}

Extract up to 10 most relevant tenders. If no tenders found return { "tenders": [] }.`;

  try {
    const response = await openai.chat.completions.create({
      model:           'gpt-4o',
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user',   content: `Platform: ${source.name}\nURL: ${source.url}\n\nContent:\n${content}` },
      ],
      max_tokens:  3000,
      temperature: 0.1,
    });

    const parsed = JSON.parse(response.choices[0].message.content);
    return (parsed.tenders || []).map(t => ({
      ...t,
      source:   t.url || source.url,
      platform: source.name,
    }));
  } catch (e) {
    console.warn(`GPT failed for ${source.name}:`, e.message);
    return [];
  }
}

// ── SUPABASE ROW MAPPING ──────────────────────────────────────────────────

function toRow(t) {
  return {
    title:           t.title           || '',
    organization:    t.organization    || '',
    budget:          t.budget          || '',
    deadline:        t.deadline        || '',
    source:          t.source          || '',
    platform:        t.platform        || '',
    match_percent:   Number(t.matchPercent)   || 0,
    recommendation:  t.recommendation  || '',
    compliance:      Number(t.compliance)     || 0,
    financial:       Number(t.financial)      || 0,
    feasibility:     Number(t.feasibility)    || 0,
    win_chance:      Number(t.winChance)      || 0,
    why_participate: t.whyParticipate  || '',
    risks:           t.risks           || '',
    action_plan:     t.actionPlan      || '',
    risk_level:      t.riskLevel       || '',
    profit_potential:t.profitPotential || '',
  };
}

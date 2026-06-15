const { client } = require('./_supabase');

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).end();

  try {
    const { data, error } = await client()
      .from('tenders')
      .select('*')
      .order('match_percent', { ascending: false })
      .limit(100);

    if (error) throw new Error(error.message);

    const tenders = (data || []).map(r => ({
      id:              r.id,
      title:           r.title           || '',
      organization:    r.organization    || '',
      budget:          r.budget          || '',
      deadline:        r.deadline        || '',
      source:          r.source          || '',
      platform:        r.platform        || '',
      matchPercent:    r.match_percent   || 0,
      recommendation:  r.recommendation  || '',
      compliance:      r.compliance      || 0,
      financial:       r.financial       || 0,
      feasibility:     r.feasibility     || 0,
      winChance:       r.win_chance      || 0,
      whyParticipate:  r.why_participate  || '',
      risks:           r.risks           || '',
      actionPlan:      r.action_plan     || '',
      riskLevel:       r.risk_level      || '',
      profitPotential: r.profit_potential || '',
    }));

    res.status(200).json({ tenders });
  } catch (e) {
    console.error('get-tenders error:', e.message);
    res.status(500).json({ error: e.message, tenders: [] });
  }
};

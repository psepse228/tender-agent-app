const { listRecords } = require('./_airtable');

const TENDERS_TABLE = 'tblVDZGXzM9B7uM4O';

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).end();

  try {
    const records = await listRecords(TENDERS_TABLE, 'maxRecords=100');

    const tenders = records
      .map(r => {
        const f = r.fields;
        return {
          id:              r.id,
          title:           f['Title']           || '',
          organization:    f['Organization']    || '',
          budget:          f['Budget']          || '',
          deadline:        f['Deadline']        || '',
          source:          f['Source']          || '',
          platform:        f['Platform']        || '',
          matchPercent:    Number(f['Match Percent'])    || 0,
          recommendation:  f['Recommendation']  || '',
          compliance:      Number(f['Compliance'])      || 0,
          financial:       Number(f['Financial'])       || 0,
          feasibility:     Number(f['Feasibility'])     || 0,
          winChance:       Number(f['Win Chance'])      || 0,
          whyParticipate:  f['Why Participate']  || '',
          risks:           f['Risks']           || '',
          actionPlan:      f['Action Plan']     || '',
          riskLevel:       f['Risk Level']      || '',
          profitPotential: f['Profit Potential'] || '',
        };
      })
      .sort((a, b) => b.matchPercent - a.matchPercent);

    res.status(200).json({ tenders });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message, tenders: [] });
  }
};

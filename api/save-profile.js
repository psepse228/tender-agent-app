const { listRecords, createRecords, patchRecord } = require('./_airtable');

const PROFILE_TABLE = 'tblhzGlJBg0xbWsVA';

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();

  try {
    const body    = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const updates = body.updates;

    if (!updates || !Object.keys(updates).length) {
      return res.status(400).json({ success: false, error: 'No updates provided' });
    }

    const records = await listRecords(PROFILE_TABLE);

    if (records.length > 0) {
      await patchRecord(PROFILE_TABLE, records[0].id, updates);
    } else {
      await createRecords(PROFILE_TABLE, [updates]);
    }

    res.status(200).json({ success: true });
  } catch (e) {
    console.error(e);
    res.status(500).json({ success: false, error: e.message });
  }
};

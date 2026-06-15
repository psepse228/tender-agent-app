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

    // Serialize all profile fields into a single text blob stored in "Name".
    // This works on any Airtable table without needing custom fields.
    const profileText = Object.entries(updates)
      .filter(([, v]) => v)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\n');

    const records = await listRecords(PROFILE_TABLE);

    if (records.length > 0) {
      await patchRecord(PROFILE_TABLE, records[0].id, { Name: profileText });
    } else {
      await createRecords(PROFILE_TABLE, [{ Name: profileText }]);
    }

    res.status(200).json({ success: true });
  } catch (e) {
    console.error('save-profile error:', e.message);
    res.status(500).json({ success: false, error: e.message });
  }
};

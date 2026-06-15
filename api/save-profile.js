const { client } = require('./_supabase');

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();

  try {
    const body    = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const updates = body.updates;

    if (!updates || !Object.keys(updates).length) {
      return res.status(400).json({ success: false, error: 'No updates provided' });
    }

    const profileText = Object.entries(updates)
      .filter(([, v]) => v)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\n');

    const sb = client();

    const { data: existing } = await sb
      .from('profile')
      .select('id')
      .limit(1);

    if (existing && existing.length > 0) {
      const { error } = await sb
        .from('profile')
        .update({ data: profileText, updated_at: new Date().toISOString() })
        .eq('id', existing[0].id);
      if (error) throw new Error(error.message);
    } else {
      const { error } = await sb
        .from('profile')
        .insert({ data: profileText });
      if (error) throw new Error(error.message);
    }

    res.status(200).json({ success: true });
  } catch (e) {
    console.error('save-profile error:', e.message);
    res.status(500).json({ success: false, error: e.message });
  }
};

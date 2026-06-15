const BASE_URL = 'https://api.airtable.com/v0';
const BASE_ID  = 'appR9ZChkECIS64SX';

function headers() {
  return {
    'Authorization': `Bearer ${process.env.AIRTABLE_API_KEY}`,
    'Content-Type':  'application/json',
  };
}

async function listRecords(tableId, query = '') {
  const url = `${BASE_URL}/${BASE_ID}/${tableId}${query ? '?' + query : ''}`;
  const res  = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`Airtable list ${res.status}: ${await res.text()}`);
  return (await res.json()).records || [];
}

async function createRecords(tableId, fieldsList) {
  const results = [];
  for (let i = 0; i < fieldsList.length; i += 10) {
    const batch = fieldsList.slice(i, i + 10);
    const res   = await fetch(`${BASE_URL}/${BASE_ID}/${tableId}`, {
      method:  'POST',
      headers: headers(),
      body:    JSON.stringify({ records: batch.map(f => ({ fields: f })) }),
    });
    if (!res.ok) throw new Error(`Airtable create ${res.status}: ${await res.text()}`);
    results.push(...((await res.json()).records || []));
  }
  return results;
}

async function deleteRecords(tableId, ids) {
  for (let i = 0; i < ids.length; i += 10) {
    const batch = ids.slice(i, i + 10);
    const qs    = batch.map(id => `records[]=${id}`).join('&');
    const res   = await fetch(`${BASE_URL}/${BASE_ID}/${tableId}?${qs}`, {
      method:  'DELETE',
      headers: headers(),
    });
    if (!res.ok) throw new Error(`Airtable delete ${res.status}: ${await res.text()}`);
  }
}

async function patchRecord(tableId, recordId, fields) {
  const res = await fetch(`${BASE_URL}/${BASE_ID}/${tableId}/${recordId}`, {
    method:  'PATCH',
    headers: headers(),
    body:    JSON.stringify({ fields }),
  });
  if (!res.ok) throw new Error(`Airtable patch ${res.status}: ${await res.text()}`);
  return res.json();
}

module.exports = { listRecords, createRecords, deleteRecords, patchRecord };

const { createClient } = require('@supabase/supabase-js');

function client() {
  return createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_KEY
  );
}

module.exports = { client };

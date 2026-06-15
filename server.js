const express = require('express');
const path    = require('path');

const getTenders     = require('./api/get-tenders');
const tenderRefresh  = require('./api/tender-refresh');
const saveProfile    = require('./api/save-profile');

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname)));

app.get('/api/get-tenders',      getTenders);
app.post('/api/tender-refresh',  tenderRefresh);
app.post('/api/save-profile',    saveProfile);

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => console.log(`Tender Agent running on port ${PORT}`));

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite builds straight into backend/dist (this project lives at
// backend/frontend/ specifically so it sits inside Railway's service root
// directory, "/backend" -- see the frontend-rewrite branch notes). FastAPI
// (see backend/app/main.py) serves dist/index.html at "/" and mounts
// dist/assets at "/assets".
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // Local dev: `npm run dev` here still hits the real FastAPI backend
      // (run separately on :8000) for every API/auth route instead of
      // requiring a built dist/ to exist.
      '/api': 'http://localhost:8000',
      '/login': 'http://localhost:8000',
      '/terms': 'http://localhost:8000',
      '/privacy': 'http://localhost:8000',
    },
  },
});

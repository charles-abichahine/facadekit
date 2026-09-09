# facadekit-web

Vite + React + TypeScript. Brief box, proposal image, legalised panel map,
three download buttons. Submits a job and polls — it never blocks on a single
request, because generation takes tens of seconds.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://localhost:8000
npm run build
```

`VITE_API_URL` points at the deployed API in production; left empty, the dev
proxy in `vite.config.ts` handles it and the browser sees one origin, so CORS
never comes into it locally.

The page states on screen that the legaliser is a baseline and the images are
placeholders. That banner comes off when the CP-SAT solver lands, not before.

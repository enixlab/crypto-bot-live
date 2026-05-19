// Vercel API function — proxy vers GCS bucket public.
// /api/data?file=<filename>&t=<cachebuster>
// → lit gs://<bucket>/<prefix><filename> via HTTPS

export default async function handler(req, res) {
  const file = req.query.file;
  if (!file || file.includes("..") || file.includes("/")) {
    return res.status(400).json({ error: "invalid file" });
  }
  const bucket = process.env.GCS_BUCKET || "enix-crypto-bot-state";
  const prefix = process.env.GCS_PREFIX || "data/";
  const url = `https://storage.googleapis.com/${bucket}/${prefix}${file}`;
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) return res.status(r.status).end();
    const data = await r.json();
    res.setHeader("Cache-Control", "no-cache, max-age=0");
    return res.status(200).json(data);
  } catch (e) {
    return res.status(500).json({ error: String(e) });
  }
}

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const port = Number(process.env.PORT || 5177);
const host = process.env.HOST || (process.env.REPLIT_DEV_DOMAIN ? "0.0.0.0" : "127.0.0.1");
const publicUrl = process.env.REPLIT_DEV_DOMAIN ? `https://${process.env.REPLIT_DEV_DOMAIN}` : null;

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8"
};

const server = http.createServer((req, res) => {
  const rawPath = decodeURIComponent(new URL(req.url, `http://${req.headers.host || `${host}:${port}`}`).pathname);
  const safePath = rawPath === "/" ? "/index.html" : rawPath;
  const filePath = path.resolve(root, `.${safePath}`);
  if (!filePath.startsWith(root)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }
  fs.readFile(filePath, (error, data) => {
    if (error) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }
    res.writeHead(200, { "content-type": types[path.extname(filePath)] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(port, host, () => {
  console.log(`MS2.0 main app running at http://${host}:${port}`);
  if (publicUrl) {
    console.log(`MS2.0 Replit URL: ${publicUrl}`);
  }
});

// Génère l'image de partage (1200×630) à partir du logo et d'une vraie capture.
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const asset = (name) => pathToFileURL(join(root, "src/assets", name)).href;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.goto(pathToFileURL(join(root, "src/404.html")).href);
await page.setContent(`<!doctype html><meta charset="utf-8"><style>
  @font-face { font-family: B; src: url("${asset("fonts/bricolage-grotesque-latin-wght-normal.woff2")}"); font-weight: 200 800; }
  @font-face { font-family: S; src: url("${asset("fonts/source-sans-3-latin-wght-normal.woff2")}"); font-weight: 200 900; }
  * { box-sizing: border-box; margin: 0; }
  body { width: 1200px; height: 630px; overflow: hidden; background: #f8fafd; color: #0f2a47; font-family: S; position: relative; }
  .text { position: absolute; left: 64px; top: 64px; width: 530px; }
  .brand { display: flex; align-items: center; gap: 14px; font: 700 34px B; margin-bottom: 48px; }
  h1 { font: 700 56px/1.08 B; letter-spacing: -0.015em; }
  h1 span { color: #1f6298; }
  p { margin-top: 28px; font-size: 26px; line-height: 1.35; color: #475b72; }
  i { display: inline-block; width: 12px; height: 12px; background: #e5b434; transform: rotate(45deg); margin: 0 12px 3px 2px; }
  img.shot { position: absolute; left: 640px; top: 90px; width: 900px; border: 1px solid #d5e0eb; border-radius: 16px; box-shadow: 0 24px 50px -22px rgb(15 42 71 / 45%); }
</style>
<div class="text"><div class="brand"><img src="${asset("img/logo-96.png")}" width="60" height="60" alt="">PM² Desktop</div>
<h1>Pilotez vos projets <span>avec méthode.</span></h1>
<p><i></i>Application locale en français, fondée sur la méthodologie PM² v3.1</p></div>
<img class="shot" src="${asset("img/cockpit-1500.webp")}" alt="">`);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(300);
await page.screenshot({ path: join(root, "src/assets/img/og-image.png") });
await browser.close();

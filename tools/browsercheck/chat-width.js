/** 窄窗口下的排版检查：助手气泡不能被压成一列字。 */
const puppeteer = require('puppeteer-core');

const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
const OUT = 'D:/TUT/ProjectComputer/tools/browsercheck';
const BASE = 'http://localhost:5173';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EXE,
    headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu'],
    defaultViewport: {width: 1600, height: 1000},
  });
  const page = await browser.newPage();
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  await page.goto(BASE, {waitUntil: 'domcontentloaded'});
  const token = await page.evaluate(async () => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: 'admin@lab.test', password: 'admin1234'}),
    });
    return (await res.json()).token;
  });
  await page.evaluate((t) => localStorage.setItem('pm.token', t), token);

  for (const width of [1600, 1100, 860]) {
    await page.setViewport({width, height: 900});
    await page.goto(BASE, {waitUntil: 'networkidle2'});
    await wait(1200);
    await page.evaluate(() =>
      [...document.querySelectorAll('.viewtabs button')]
        .find((b) => b.textContent.includes('AI 教师'))
        ?.click(),
    );
    await wait(900);
    // 复用最近一个已有消息的会话，避免制造垃圾数据
    await page.evaluate(() => document.querySelector('.conv-item')?.click());
    await wait(900);
    const geo = await page.evaluate(() => {
      const b = document.querySelector('.msg.assistant .bubble');
      if (!b) return null;
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      const chars = Math.max(1, Math.round(r.width / parseFloat(cs.fontSize)));
      return {w: Math.round(r.width), charsPerLine: chars, h: Math.round(r.height)};
    });
    console.log(`视口 ${width}px →`, geo ? `气泡 ${geo.w}px，每行约 ${geo.charsPerLine} 字，高 ${geo.h}px` : '无助手消息');
    await page.screenshot({path: `${OUT}/chat-w${width}.png`});
  }

  await browser.close();
})();

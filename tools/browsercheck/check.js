/**
 * 用 Remotion 自带的 Chrome Headless Shell 打开工作台，
 * 抓控制台报错 + 截图。仅开发期验证用，不进产品构建。
 *
 * 用法：node check.js [url] [outPng]
 */
const puppeteer = require('puppeteer-core');

const EXE =
  'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';

(async () => {
  const url = process.argv[2] || 'http://localhost:5173/';
  const out = process.argv[3] || 'D:/TUT/ProjectComputer/tools/browsercheck/shot.png';

  const browser = await puppeteer.launch({
    executablePath: EXE,
    headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1600,1000'],
    defaultViewport: {width: 1600, height: 1000, deviceScaleFactor: 1},
  });

  const page = await browser.newPage();
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`.slice(0, 400)));
  page.on('pageerror', (e) => logs.push(`[pageerror] ${String(e).slice(0, 600)}`));
  page.on('requestfailed', (r) => logs.push(`[reqfail] ${r.url()} ${r.failure()?.errorText}`));

  await page.goto(url, {waitUntil: 'networkidle2', timeout: 45000});
  // 等 Player 首帧（预览是异步挂载的）
  await new Promise((r) => setTimeout(r, 3500));

  await page.screenshot({path: out, fullPage: false});
  const text = await page.evaluate(() => document.body.innerText.slice(0, 800));
  await browser.close();

  console.log(JSON.stringify({url, out, logs, text}, null, 2));
})().catch((e) => {
  console.error('FAILED', e);
  process.exit(1);
});

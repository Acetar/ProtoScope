/** 新增知识点的渲染抽查：进入工作台，逐个点开 6 个新知识点，确认画面不是空白。 */
const puppeteer = require('puppeteer-core');

const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
const OUT = 'D:/TUT/ProjectComputer/tools/browsercheck';
const BASE = 'http://localhost:5173';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EXE, headless: 'shell',
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
  await page.goto(BASE, {waitUntil: 'networkidle2'});
  await wait(1800);

  const titles = await page.evaluate(() =>
    [...document.querySelectorAll('.panel.catalog li strong')].map((e) => e.textContent.trim()),
  );
  console.log(`目录 ${titles.length} 条：`, titles.join(' / '));

  const targets = ['TCP 超时重传', 'TCP 慢启动与拥塞避免', 'DNS 迭代查询', 'ICMP 与 ping', 'DHCP 动态获取地址', 'NAT 地址转换'];
  for (const name of targets) {
    await page.evaluate((n) => {
      const li = [...document.querySelectorAll('.panel.catalog li')].find((x) => x.textContent.includes(n));
      li?.click();
    }, name);
    await wait(2600);
    const info = await page.evaluate(() => ({
      title: document.querySelector('.stage-head h2')?.textContent.trim(),
      sub: document.querySelector('.stage-head p')?.textContent.trim(),
    }));
    const file = `kp-${name.replace(/[^\w\u4e00-\u9fa5]/g, '').slice(0, 12)}.png`;
    await page.screenshot({path: `${OUT}/${file}`});
    console.log('·', name, '→', info.title, '|', info.sub);
  }

  // 抓一张有内容的目录全图（12 条）
  await page.screenshot({path: `${OUT}/catalog-12.png`});
  await browser.close();
})();

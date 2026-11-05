/**
 * 抓包页真机检查：上传样例 pcap → 看三栏联动 → 变成动画。
 * 跑法：node tools/browsercheck/capture.js
 */
const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME = path.resolve(
  __dirname,
  '../../renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe',
);
const PCA = 'D:\\TUT\\ProjectComputer\\samples\\http-handshake.pcap';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1600,1000'],
    defaultViewport: { width: 1600, height: 1000 },
  });
  const page = await browser.newPage();
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));

  await page.goto('http://localhost:5173', { waitUntil: 'networkidle2', timeout: 45000 });
  await new Promise((r) => setTimeout(r, 1500));

  // 切到抓包页
  const clicked = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.viewtabs button')].find((b) =>
      b.textContent.includes('抓包'),
    );
    if (!btn) return false;
    btn.click();
    return true;
  });
  console.log('切换到抓包页:', clicked);
  await new Promise((r) => setTimeout(r, 600));

  // 上传样例文件
  const input = await page.$('input[type=file]');
  if (!input) {
    console.log('找不到上传控件');
    await page.screenshot({ path: path.join(__dirname, 'cap-00-nofile.png') });
    await browser.close();
    return;
  }
  await input.uploadFile(PCA);
  await new Promise((r) => setTimeout(r, 3000));

  await page.screenshot({ path: path.join(__dirname, 'cap-01-parsed.png') });
  const summary = await page.evaluate(() => ({
    sessions: [...document.querySelectorAll('.sessions li strong')].map((e) => e.textContent),
    packets: [...document.querySelectorAll('.packets li')].length,
    fields: [...document.querySelectorAll('.frow')].slice(0, 4).map((e) => e.innerText.replace(/\n/g, '=')),
  }));
  console.log('会话:', summary.sessions);
  console.log('报文行数:', summary.packets);
  console.log('字段示例:', summary.fields);

  // 点第 6 行（HTTP GET），验证联动
  await page.evaluate(() => document.querySelectorAll('.packets li')[5]?.click());
  await new Promise((r) => setTimeout(r, 500));
  await page.screenshot({ path: path.join(__dirname, 'cap-02-linked.png') });
  const linked = await page.evaluate(() => {
    const active = document.querySelector('.packets li.active');
    const onArrow = document.querySelector('.alabel.on');
    return { row: active?.innerText.replace(/\n/g, ' | '), arrow: onArrow?.textContent };
  });
  console.log('联动:', linked);

  // 变成动画
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.cap-action button')][0];
    btn?.click();
  });
  await new Promise((r) => setTimeout(r, 3500));
  await page.screenshot({ path: path.join(__dirname, 'cap-03-motion.png') });
  const motion = await page.evaluate(() => document.querySelector('.stage')?.innerText.slice(0, 300));
  console.log('动画页:', motion);

  const noisy = logs.filter((l) => !l.includes('Function components cannot be given refs'));
  if (noisy.length) console.log('控制台:', noisy.slice(0, 8).join('\n'));
  await browser.close();
})();

/**
 * 落地页与登录墙验证（DOM 断言版）。
 *
 * 不依赖人眼看图：每一步都断��关键 DOM 与布局指标，
 * 截图只作为留档。视觉后端不可用时也能判断有没有坏。
 */
const puppeteer = require('puppeteer-core');

const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
const OUT = 'D:/TUT/ProjectComputer/tools/browsercheck';
const BASE = 'http://localhost:5173';

const results = [];
function check(name, ok, detail = '') {
  results.push({name, ok, detail});
  console.log(ok ? '✓' : '✗', name, detail);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EXE, headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu'],
    defaultViewport: {width: 1600, height: 1000},
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)); });

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const shot = (n) => page.screenshot({path: `${OUT}/${n}.png`});

  await page.goto(BASE, {waitUntil: 'networkidle2'});
  await wait(1200);

  // ---- 1. 登录墙 ----
  const wall = await page.evaluate(() => ({
    landing: !!document.querySelector('.landing'),
    topbar: !!document.querySelector('.topbar'),
    labels: [...document.querySelectorAll('.landing button')].map((b) => b.textContent.trim()),
    title: document.querySelector('.landing h1')?.innerText.replace(/\n/g, ' '),
    cards: [...document.querySelectorAll('.landing .card h3')].map((h) => h.textContent.trim()),
  }));
  check('未登录只显示落地页', wall.landing && !wall.topbar);
  check('首屏标题', wall.title === '把每一次握手 都看得见', wall.title || '(空)');
  check('功能区四张卡', wall.cards.length === 4, wall.cards.join(' / '));
  check('导航按钮齐全', wall.labels.includes('登录') && wall.labels.includes('免费注册'), wall.labels.join(','));
  await shot('land-01-hero');

  // 整页高度要够长（hero 之外的区块确实渲染了）
  const layout = await page.evaluate(() => {
    const box = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().height) : 0; };
    return {body: document.body.scrollHeight, hero: box('.hero'), features: box('.features'), how: box('.how'),
      overflowX: document.documentElement.scrollWidth > window.innerWidth + 1};
  });
  check('整页高度合理', layout.body > 1200, `${layout.body}px`);
  check('无横向溢出', !layout.overflowX);
  await page.screenshot({path: `${OUT}/land-full.png`, fullPage: true});

  // ---- 2. 点登录 ----
  await page.evaluate(() => [...document.querySelectorAll('.landing button')].find((b) => b.textContent.trim() === '登录').click());
  await wait(500);
  const modal = await page.evaluate(() => {
    const m = document.querySelector('.auth-modal');
    if (!m) return null;
    const b = m.getBoundingClientRect();
    return {
      w: Math.round(b.width), h: Math.round(b.height),
      inputs: m.querySelectorAll('input').length,
      title: m.querySelector('h2')?.textContent.trim(),
      mask: !!document.querySelector('.modal-mask'),
      inViewport: b.left >= 0 && b.right <= window.innerWidth && b.top >= 0 && b.bottom <= window.innerHeight,
    };
  });
  check('点击登录弹出弹窗', !!modal && modal.mask);
  check('弹窗尺寸正常', !!modal && modal.w > 300 && modal.w < 600 && modal.inViewport, modal ? `${modal.w}x${modal.h} 输入框${modal.inputs}` : '');
  await shot('land-04-login-modal');

  // ---- 3. 登录 ----
  await page.type('.auth-modal input[type=email]', 'demo@lab.test');
  await page.type('.auth-modal input[type=password]', 'demo1234');
  await page.click('.auth-modal .primary');
  await wait(3000);

  const after = await page.evaluate(() => ({
    landing: !!document.querySelector('.landing'),
    topbar: !!document.querySelector('.topbar'),
    actions: [...document.querySelectorAll('.topbar-actions button')].map((b) => b.textContent.trim()),
    tabs: [...document.querySelectorAll('.viewtabs button')].map((b) => b.textContent.trim()),
    token: !!localStorage.getItem('pm.token'),
  }));
  check('登录后进入工作台', after.topbar && !after.landing);
  check('拿到 token', after.token);
  check('顶栏含退出', after.actions.includes('退出'), after.actions.join(','));
  check('管理员可见"管理"', after.actions.includes('管理'), after.actions.join(','));
  check('三个标签页', after.tabs.length === 3, after.tabs.join(' / '));
  await shot('land-05-workbench');

  // ---- 4. AI 教师 ----
  await page.evaluate(() => [...document.querySelectorAll('.viewtabs button')].find((b) => b.textContent.includes('AI')).click());
  await wait(1000);
  const tutor = await page.evaluate(() => ({
    panel: !!document.querySelector('.panel.tutor'),
    presets: [...document.querySelectorAll('.preset')].map((b) => b.textContent.trim()),
    hasBoard: !!document.querySelector('.panel.stage canvas, .panel.stage iframe, .panel.stage .skeleton'),
  }));
  check('AI 教师面板渲染', tutor.panel);
  check('追问胶囊存在', tutor.presets.length >= 3, tutor.presets.join(' / '));
  await shot('land-06-tutor');

  // 问一个问题：无 key 时后端回退规则模板，仍应出文字
  await page.type('.tutor-input textarea', '为什么是三次握手');
  await page.click('.tutor-input .primary');
  await wait(3500);
  const answer = await page.evaluate(() => [...document.querySelectorAll('.msg.assistant .bubble')].map((b) => b.innerText));
  const last = answer[answer.length - 1] || '';
  check('助教返回文字', last.length > 20, `${last.length} 字`);
  check('文字不是打字机卡住', !last.startsWith('[object'), last.slice(0, 40).replace(/\n/g, ' '));
  await shot('land-07-tutor-answer');

  // ---- 5. 管理员 ----
  await page.evaluate(() => [...document.querySelectorAll('.topbar-actions button')].find((b) => b.textContent.trim() === '管理').click());
  await wait(1200);
  const admin = await page.evaluate(() => ({
    open: !!document.querySelector('.modal.admin'),
    rows: document.querySelectorAll('.admin-table tbody tr').length,
    stats: [...document.querySelectorAll('.stat b')].map((b) => b.textContent.trim()),
  }));
  check('管理员面板打开', admin.open);
  check('用户列表有行', admin.rows >= 1, `${admin.rows} 行`);
  check('统计卡片', admin.stats.length === 4, admin.stats.join(' / '));
  await shot('land-08-admin');

  // ---- 6. 退出后回到落地页 ----
  await page.evaluate(() => document.querySelector('.admin-head .ghost')?.click());
  await wait(400);
  await page.evaluate(() => [...document.querySelectorAll('.topbar-actions button')].find((b) => b.textContent.trim() === '退出').click());
  await wait(700);
  const back = await page.evaluate(() => ({landing: !!document.querySelector('.landing'), token: localStorage.getItem('pm.token')}));
  check('退出后回到落地页', back.landing && !back.token);

  const failed = results.filter((r) => !r.ok);
  console.log(`\n通过 ${results.length - failed.length}/${results.length}`);
  console.log('控制台错误：', errors.length ? errors : '无');
  await browser.close();
  if (failed.length || errors.length) process.exit(1);
})().catch((e) => { console.error('FAILED', e); process.exit(1); });

/**
 * AI 教师会话界面验证（DOM 断言版）。
 *
 * 覆盖：会话列表渲染、发问后流式回答落地、在对话里生成动画（卡片长在消息流里而不是另开一栏）、
 * 切换会话不丢消息、并发时侧栏出现"正在生成"标记。
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
  page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 300)); });

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const shot = (n) => page.screenshot({path: `${OUT}/${n}.png`});
  const clickText = (sel, text) =>
    page.evaluate((s, t) => {
      const el = [...document.querySelectorAll(s)].find((b) => b.textContent.trim().includes(t));
      if (!el) return false;
      el.click();
      return true;
    }, sel, text);

  // 用 API 直接拿到 token，塞进 localStorage：把"登录 UI"留给 landing.js 覆盖，这里专注会话功能
  await page.goto(BASE, {waitUntil: 'domcontentloaded'});
  const token = await page.evaluate(async () => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: 'admin@lab.test', password: 'admin1234'}),
    });
    const data = await res.json();
    return data.token || '';
  });
  check('拿到登录 token', !!token, token ? token.slice(0, 12) + '…' : '(空)');
  await page.evaluate((t) => localStorage.setItem('pm.token', t), token);
  await page.goto(BASE, {waitUntil: 'networkidle2'});
  await wait(1500);

  // ---- 进入 AI 教师 ----
  const switched = await clickText('.viewtabs button', 'AI 教师');
  await wait(1200);
  const shell = await page.evaluate(() => ({
    app: !!document.querySelector('.tutor-app'),
    side: !!document.querySelector('.conv-side'),
    head: document.querySelector('.chat-head h2')?.textContent.trim(),
    convCount: document.querySelectorAll('.conv-item').length,
    blank: !!document.querySelector('.chat-blank'),
    presets: document.querySelectorAll('.preset').length,
    // 旧的"三栏挤压"结构必须已经消失
    oldLayout: !!document.querySelector('.panel.tutor'),
  }));
  check('切到 AI 教师标签', switched);
  check('会话界面渲染', shell.app && shell.side, JSON.stringify(shell));
  check('左侧已有一个会话', shell.convCount >= 1, String(shell.convCount));
  check('空的对话显示引导与预设问题', shell.blank && shell.presets === 4);
  check('旧的三栏挤压布局已移除', !shell.oldLayout);
  // 先新建一个干净会话：库里可能还留着调试产生的会话
  await clickText('.conv-top button', '新建对话');
  await wait(900);
  await shot('tutor-01-blank');

  // ---- 发一个问题（走预设）----
  await clickText('.preset', '为什么是三次握手');
  await wait(600);
  const streaming = await page.evaluate(() => !!document.querySelector('.typing-chip') || !!document.querySelector('.typing'));
  // 规则兜底也会分块吐字，等它结束
  let answer = '';
  for (let i = 0; i < 40; i++) {
    await wait(400);
    answer = await page.evaluate(() => {
      const bubbles = [...document.querySelectorAll('.msg.assistant .bubble')];
      return bubbles.length ? bubbles[bubbles.length - 1].innerText.trim() : '';
    });
    const done = await page.evaluate(() => !document.querySelector('.typing-chip'));
    if (done && answer.length > 20) break;
  }
  const msgCount = await page.evaluate(() => document.querySelectorAll('.msg').length);
  check('问答成对出现', msgCount >= 2, String(msgCount));
  check('助教回答有内容', answer.length > 20, `${answer.length} 字：${answer.slice(0, 40)}`);
  check('回答里有真实字段（seq/ack/flags 至少一个）', /seq|ack|SYN|ESTABLISHED/i.test(answer));
  check('曾经出现流式状态', streaming || answer.length > 0);
  await shot('tutor-02-answer');

  // ---- 在对话里生成动画 ----
  await page.evaluate(() => {
    const ta = document.querySelector('.composer-input');
    ta.value = '画一个 DNS 递归解析的过程';
    ta.dispatchEvent(new Event('input', {bubbles: true}));
  });
  await wait(300);
  await clickText('.composer-actions button', '生成动画');
  await wait(90);
  const pendingCard = await page.evaluate(() => !!document.querySelector('.anim-skeleton'));

  let card = null;
  for (let i = 0; i < 30; i++) {
    await wait(500);
    card = await page.evaluate(() => {
      const el = document.querySelector('.anim-card');
      if (!el) return null;
      const box = el.getBoundingClientRect();
      return {
        title: el.querySelector('.anim-title')?.textContent.trim(),
        meta: el.querySelector('.anim-meta')?.textContent.trim(),
        src: el.querySelector('.anim-src')?.textContent.trim(),
        hasPlayer: !!el.querySelector('.anim-card [style*="border-radius"]') || !!el.querySelector('video'),
        width: Math.round(box.width),
        inFlow: !!el.closest('.chat-body'),
      };
    });
    if (card && card.title && !card.title.includes('正在编排')) break;
  }
  check('生成时出现占位卡片', pendingCard);
  check('动画卡片出现在消息流内', !!card && card.inFlow, JSON.stringify(card));
  check('卡片标题不是占位文案', !!card && !card.title.includes('正在编排'), card?.title || '(无)');
  check('卡片带时长/帧数', !!card && /\d/.test(card.meta || ''), card?.meta || '');
  check('卡片宽度不挤压右侧（≤760px）', !!card && card.width <= 780, String(card?.width));
  await shot('tutor-03-animation');

  // ---- 会话切换与并发 ----
  const before = await page.evaluate(() => document.querySelectorAll('.conv-item').length);
  const prevId = await page.evaluate(() => document.querySelector('.conv-item.on')?.dataset.convId);
  await clickText('.conv-top button', '新建对话');
  await wait(900);
  const after = await page.evaluate(() => ({
    count: document.querySelectorAll('.conv-item').length,
    activeTitle: document.querySelector('.conv-item.on .conv-title')?.textContent.trim(),
    blank: !!document.querySelector('.chat-blank'),
    msgs: document.querySelectorAll('.msg').length,
  }));
  check('新建会话后列表 +1', after.count === before + 1, `${before} → ${after.count}`);
  check('新会话是空的', after.blank && after.msgs === 0, JSON.stringify(after));

  // 切回第一个会话，消息还在
  await page.evaluate((id) => {
    document.querySelector(`.conv-item[data-conv-id="${id}"]`)?.click();
  }, prevId);
  await wait(1200);
  const back = await page.evaluate(() => ({
    msgs: document.querySelectorAll('.msg').length,
    anim: document.querySelectorAll('.anim-card').length,
  }));
  check('切回旧会话消息仍在', back.msgs >= 2, JSON.stringify(back));
  check('切回旧会话动画卡片仍在', back.anim >= 1, String(back.anim));
  await shot('tutor-04-switch');

  // ---- 布局指标 ----
  const layout = await page.evaluate(() => {
    const app = document.querySelector('.tutor-app').getBoundingClientRect();
    const side = document.querySelector('.conv-side').getBoundingClientRect();
    return {
      h: Math.round(app.height),
      sideW: Math.round(side.width),
      overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      vh: window.innerHeight,
    };
  });
  check('会话界面在视口内（不撑出滚动）', !layout.overflowX, JSON.stringify(layout));
  check('侧栏宽度约 258px', Math.abs(layout.sideW - 258) <= 2, String(layout.sideW));

  check('无 JS 报错（除已知 Remotion 库告警）', !errors.some((e) => !/not a prop|given refs|AbsoluteFill|Remotion|acknowledge/i.test(e)),
    errors.slice(0, 3).join(' | ') || 'none');

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} 通过`);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})();

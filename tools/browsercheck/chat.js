/** 聊天体验自检：寒暄 → 结构化讲解 → 直接要动画（应自动出片）。 */
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
  const fails = [];
  const check = (ok, msg) => {
    console.log(`${ok ? '✓' : '✗'} ${msg}`);
    if (!ok) fails.push(msg);
  };

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
  await wait(1500);

  // 进入 AI 教师
  await page.evaluate(() =>
    [...document.querySelectorAll('.viewtabs button')]
      .find((b) => b.textContent.includes('AI 教师'))
      ?.click(),
  );
  await wait(1200);

  // 新建一个干净会话
  await page.evaluate(() =>
    [...document.querySelectorAll('.conv-side button')]
      .find((b) => b.textContent.includes('新建对话'))
      ?.click(),
  );
  await wait(900);

  async function ask(text) {
    await page.evaluate((t) => {
      const ta = document.querySelector('.composer-input');
      ta.value = t;
      ta.dispatchEvent(new Event('input', {bubbles: true}));
    }, text);
    await wait(200);
    await page.evaluate(() => document.querySelector('.composer-actions .primary')?.click());
    await wait(400);
  }

  // ① 寒暄
  await ask('你好');
  await wait(2500);
  const hello = await page.evaluate(() => {
    const bubbles = [...document.querySelectorAll('.msg.assistant .bubble')];
    return bubbles[bubbles.length - 1]?.textContent || '';
  });
  check(hello.includes('你好'), '寒暄有正常回应');
  check(!/你问的是|固定剧本/.test(hello), '寒暄不再是模板腔');
  console.log('   → ', hello.slice(0, 60).replace(/\n/g, ' '));

  // ② 原理提问（自动对上知识点）
  await ask('DNS 递归和迭代查询有什么区别');
  await wait(3000);
  const ans = await page.evaluate(() => {
    const bubbles = [...document.querySelectorAll('.msg.assistant .bubble')];
    return bubbles[bubbles.length - 1]?.textContent || '';
  });
  check(ans.length > 40, '讲解性回答非空');
  console.log('   → ', ans.slice(0, 90).replace(/\n/g, ' '));

  // 气泡宽度（排版问题的主要指标：不能被压成一列字）
  const geo = await page.evaluate(() => {
    const b = document.querySelector('.msg.assistant .bubble');
    const r = b.getBoundingClientRect();
    const cs = getComputedStyle(b);
    const lines = b.textContent.split('\n').length;
    return {w: Math.round(r.width), h: Math.round(r.height), fs: cs.fontSize, ws: cs.whiteSpace, lines};
  });
  check(geo.w > 320, `助手气泡宽度正常（${geo.w}px）`);
  await page.screenshot({path: `${OUT}/chat-01-answer.png`});

  // ③ 直接要动画 → 应该自动在对话里出片
  await ask('画一个 TCP 三次握手的动画');
  // 占位卡是瞬态的（本地规则库出片只要几百毫秒），所以"出现占位或直接出片"都算通过
  let appeared = false;
  for (let i = 0; i < 20 && !appeared; i += 1) {
    appeared = await page.evaluate(
      () => !!document.querySelector('.anim-skeleton') || !!document.querySelector('.anim-card'),
    );
    if (!appeared) await wait(150);
  }
  check(appeared, '对话里出现动画（占位卡或成品卡）');
  await wait(9000);
  const anim = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('.anim-card')];
    const last = cards[cards.length - 1];
    return {
      count: cards.length,
      title: last?.querySelector('.anim-title')?.textContent.trim() || '',
      meta: last?.querySelector('.anim-meta')?.textContent.trim() || '',
      hasPlayer: !!last?.querySelector('video, .player, [class*=player]'),
      width: last ? Math.round(last.getBoundingClientRect().width) : 0,
    };
  });
  check(anim.count >= 1, `对话里生成了动画卡片（${anim.count} 张）`);
  check(!!anim.title && anim.width > 400, `卡片有标题且不被挤压：${anim.title} / ${anim.width}px / ${anim.meta}`);
  await page.screenshot({path: `${OUT}/chat-02-animation.png`});

  // ④ 排版：不该有横向溢出、文字不该只有 1 字宽
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(overflow <= 0, `无横向溢出（${overflow}）`);

  console.log(fails.length ? `\n失败 ${fails.length} 条` : '\n全部通过');
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();

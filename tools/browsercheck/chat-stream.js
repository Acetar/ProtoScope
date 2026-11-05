/**
 * 回归测试：模型逐 token 流式返回时，气泡不能"一个 token 一行"。
 *
 * 真实模型（DeepSeek）的流是几字符一个 chunk 的，服务端把它们原样塞进 SSE。
 * 之前前端在每个 token 后面补了换行，于是每行只有 2–4 个字，看起来像碎掉。
 * 这个脚本把 /api/tutor/ask 换成合成的"逐字符"流，验证拼接结果与原文一致。
 */
const puppeteer = require('puppeteer-core');

const CHROME =
  'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
const BASE = 'http://localhost:5173';
const API = 'http://127.0.0.1:8000';

const ANSWER = [
  '结论：ICMP 是网络层的"差错报告 + 探测"协议，它不传业务数据。',
  '',
  'ICMP 与 ping 的过程可以拆成 3 步：',
  '1. type=8 是 Echo Request，type=0 是 Echo Reply。',
  '2. 每跳 TTL 减 1，回来的 TTL 能反推经过了几跳。',
  '3. RTT 就是往返时间，丢包时不会有 Reply。',
].join('\n');

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok });
  console.log(`${ok ? '✓' : '✗'} ${name}${detail ? '\n   →  ' + detail : ''}`);
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'shell',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1600, height: 1000 },
  });
  const page = await browser.newPage();

  // 登录拿 token，直接种到 localStorage，省掉 UI 交互
  const login = await fetch(API + '/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@lab.test', password: 'admin1234' }),
  }).then((r) => r.json());

  await page.evaluateOnNewDocument((token) => {
    localStorage.setItem('pm.token', token);
  }, login.token);

  // 把问答接口替换成"逐字符"的合成流
  await page.evaluateOnNewDocument((answer) => {
    const realFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (!url.includes('/api/tutor/ask')) return realFetch(input, init);

      const enc = new TextEncoder();
      const frames = ['event: meta\ndata: {"conversationId":0,"userMessageId":null}\n\n'];
      // 按服务端真实帧格式下发：一个片段 = 若干行 data + 空行。
      // 片段切到 3 个字符，比真实模型还碎，最能暴露"每 token 一换行"。
      for (let i = 0; i < answer.length; i += 3) {
        const piece = answer.slice(i, i + 3);
        const data = piece.split('\n').map((line) => 'data: ' + line + '\n').join('');
        frames.push('event: token\n' + data + '\n');
      }
      frames.push('event: done\ndata: [DONE]\n\n');

      const stream = new ReadableStream({
        async start(controller) {
          for (const f of frames) {
            controller.enqueue(enc.encode(f));
            await new Promise((r) => setTimeout(r, 2));
          }
          controller.close();
        },
      });
      return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
    };
  }, ANSWER);

  await page.goto(BASE, { waitUntil: 'networkidle2' });
  await wait(1200);

  await page.evaluate(() =>
    [...document.querySelectorAll('.viewtabs button')].find((b) => b.textContent.includes('AI')).click()
  );
  await wait(900);
  await page.evaluate(() =>
    [...document.querySelectorAll('.conv-top button')].find((b) => b.textContent.includes('新建对话'))?.click()
  );
  await wait(600);

  await page.type('.composer-input', 'ICMP 是干什么的');
  await page.evaluate(() =>
    [...document.querySelectorAll('.composer-actions button')].find((b) => b.textContent.includes('发送')).click()
  );
  await wait(3000);

  const got = await page.evaluate(() => {
    const bubbles = [...document.querySelectorAll('.msg.assistant .bubble')];
    const b = bubbles[bubbles.length - 1];
    return {
      text: b?.innerText ?? '',
      lines: (b?.innerText ?? '').split('\n').filter((l) => l.trim()).map((l) => l.trim()),
      width: b ? Math.round(b.getBoundingClientRect().width) : 0,
      height: b ? Math.round(b.getBoundingClientRect().height) : 0,
    };
  });

  check('气泡里有内容', got.text.length > 20, `${got.text.length} 字`);
  check(
    '没有"一个 token 一行"',
    got.lines.length <= 8,
    `${got.lines.length} 行：${got.lines.slice(0, 3).map((l) => l.slice(0, 12)).join(' | ')}`
  );
  check('段落分隔保留', got.text.includes('\n\n') || got.text.split('\n').length >= 5, JSON.stringify(got.text.slice(0, 40)));
  check('首句完整', got.lines[0]?.startsWith('结论：ICMP 是网络层'), got.lines[0]?.slice(0, 30));
  check('编号列表各自成行', got.lines.some((l) => l.startsWith('1. type=8')), got.lines.find((l) => l.startsWith('1.'))?.slice(0, 20));
  check('气泡宽度合理', got.width > 320 && got.width <= 780, `${got.width}px / 高 ${got.height}px`);

  await page.screenshot({ path: 'D:/TUT/ProjectComputer/tools/browsercheck/stream-fixed.png' });
  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(failed.length ? `\n${failed.length} 条失败` : '\n全部通过');
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

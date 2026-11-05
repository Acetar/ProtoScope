/**
 * 交互流程验证：注册 → 生成 → 打开设置 → 一句话生成（无 key 时应给出可读错误）。
 * 每一步都截图，最后把控制台错误一起打出来。
 */
const puppeteer = require('puppeteer-core');

const EXE =
  'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
const OUT = 'D:/TUT/ProjectComputer/tools/browsercheck';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EXE,
    headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu'],
    defaultViewport: {width: 1600, height: 1000},
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text().slice(0, 300));
  });

  const step = async (name, fn) => {
    await fn();
    await new Promise((r) => setTimeout(r, 900));
    await page.screenshot({path: `${OUT}/${name}.png`});
    console.log('✓', name);
  };

  await page.goto('http://localhost:5173/', {waitUntil: 'networkidle2'});
  await new Promise((r) => setTimeout(r, 2500));

  // 1. 注册
  await step('01-anon', async () => {
    const btns = await page.$$('button');
    for (const b of btns) {
      const t = await page.evaluate((el) => el.textContent.trim(), b);
      if (t === '登录') {
        await b.click();
        break;
      }
    }
    await page.waitForSelector('.modal input[type=email]');
  });

  await step('02-register', async () => {
    // 切到注册
    const btn = await page.evaluateHandle(() => {
      const b = [...document.querySelectorAll('.modal button')].find((x) =>
        x.textContent.includes('去注册'),
      );
      return b;
    });
    if (btn.asElement()) await btn.asElement().click();
    await page.type('.modal input[type=email]', `ai${Date.now()}@lab.test`);
    await page.type('.modal input[type=password]', 'demo123456');
    await page.click('.modal button.primary');
    await page.waitForFunction(() => !document.querySelector('.modal'), {timeout: 8000});
  });

  // 2. 一句话生成（此时没有 key，应报错并给出建议）
  await step('03-prompt-nokey', async () => {
    await page.click('.composer textarea');
    await page.type(
      '.composer textarea',
      '给我做一个自定义协议的动画：客户端先发 HELLO，服务端回 WELCOME，然后交换数据',
    );
    await page.click('.composer button.primary');
    await page.waitForSelector('.toast', {timeout: 12000});
  });

  // 3. 打开设置，填入一个假 key（验证掩码与保存）
  await step('04-settings', async () => {
    const btn = await page.evaluateHandle(() => {
      return [...document.querySelectorAll('button')].find((b) =>
        b.textContent.trim() === '模型设置',
      );
    });
    await btn.asElement().click();
    await page.waitForSelector('.modal input[type=password]');
  });

  await step('05-settings-saved', async () => {
    await page.type('.modal input[type=password]', 'sk-fake-key-for-ui-test-1234567890');
    await page.click('.modal button.primary');
    await page.waitForFunction(() => !document.querySelector('.modal'), {timeout: 8000});
  });

  const bodyText = await page.evaluate(() => document.body.innerText);
  await browser.close();
  console.log(
    JSON.stringify(
      {errors: [...new Set(errors)].slice(0, 6), hasEmail: bodyText.includes('@lab.test')},
      null,
      2,
    ),
  );
})().catch((e) => {
  console.error('FAILED', e);
  process.exit(1);
});

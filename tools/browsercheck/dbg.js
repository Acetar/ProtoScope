const puppeteer = require('puppeteer-core');
const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
(async () => {
  const b = await puppeteer.launch({executablePath: EXE, headless: 'shell', args: ['--no-sandbox','--disable-gpu'], defaultViewport: {width:1600,height:1000}});
  const p = await b.newPage();
  p.on('pageerror', e => console.log('PAGEERROR', String(e).slice(0,300)));
  p.on('console', m => { if (m.type()==='error') console.log('CONSOLE', m.text().slice(0,200)); });
  await p.goto('http://localhost:5173', {waitUntil:'networkidle2'});
  await new Promise(r=>setTimeout(r,1200));
  const info = await p.evaluate(() => ({
    scrollY: window.scrollY,
    bodyH: document.body.scrollHeight,
    htmlH: document.documentElement.scrollHeight,
    bodyOverflow: getComputedStyle(document.body).overflow,
    btns: [...document.querySelectorAll('.landing .btn-solid, .landing .btn-line')].map(b => b.textContent.trim()),
    featuresTop: document.querySelector('.features')?.getBoundingClientRect().top,
  }));
  console.log(JSON.stringify(info, null, 1));
  // 点第一个"登录"
  const ok = await p.evaluate(() => {
    const b = [...document.querySelectorAll('.landing button')].find(x => x.textContent.trim() === '登录');
    if (!b) return 'no button';
    b.click();
    return 'clicked';
  });
  console.log('click:', ok);
  await new Promise(r=>setTimeout(r,700));
  console.log('modal?', await p.evaluate(() => !!document.querySelector('.auth-modal')));
  await b.close();
})();

const puppeteer = require('puppeteer-core');
const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
(async () => {
  const b = await puppeteer.launch({executablePath: EXE, headless: 'shell', args: ['--no-sandbox','--disable-gpu'], defaultViewport: {width:1600,height:1000}});
  const p = await b.newPage();
  p.on('pageerror', e => console.log('PAGEERROR', String(e).slice(0,200)));
  await p.goto('http://localhost:5173', {waitUntil:'networkidle2'});
  await new Promise(r=>setTimeout(r,1500));
  await p.evaluate(() => [...document.querySelectorAll('.landing button')].find(x=>x.textContent.trim()==='登录').click());
  await new Promise(r=>setTimeout(r,600));
  console.log('modal:', await p.evaluate(() => !!document.querySelector('.auth-modal')));
  console.log('inputs:', await p.evaluate(() => document.querySelectorAll('.auth-modal input').length));
  await p.screenshot({path: 'land-04-login-modal.png'});
  await b.close();
})();

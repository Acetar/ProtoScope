const puppeteer = require('puppeteer-core');
const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
(async () => {
  const b = await puppeteer.launch({executablePath: EXE, headless: 'shell', args: ['--no-sandbox','--disable-gpu'], defaultViewport: {width:1600,height:1000}});
  const p = await b.newPage();
  await p.goto('http://localhost:5173', {waitUntil:'networkidle2'});
  await new Promise(r=>setTimeout(r,1500));
  // 用 fullPage 截一张长图，看到整页布局
  await p.screenshot({path: 'land-full.png', fullPage: true});
  const text = await p.evaluate(() => document.querySelector('.landing').innerText);
  console.log(text);
  await b.close();
})();

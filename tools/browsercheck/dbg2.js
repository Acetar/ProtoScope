const puppeteer = require('puppeteer-core');
const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
(async () => {
  const b = await puppeteer.launch({executablePath: EXE, headless: 'shell', args: ['--no-sandbox','--disable-gpu'], defaultViewport: {width:1600,height:1000}});
  const p = await b.newPage();
  await p.goto('http://localhost:5173', {waitUntil:'networkidle2'});
  await new Promise(r=>setTimeout(r,1200));
  for (const y of [700, 1500]) {
    await p.evaluate((y) => window.scrollTo(0, y), y);
    await new Promise(r=>setTimeout(r,600));
    console.log('want', y, 'got', await p.evaluate(() => window.scrollY));
  }
  await b.close();
})();

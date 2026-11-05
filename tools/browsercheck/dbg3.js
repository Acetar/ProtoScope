const puppeteer = require('puppeteer-core');
const EXE = 'D:/TUT/ProjectComputer/renderer/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';
(async () => {
  const b = await puppeteer.launch({executablePath: EXE, headless: 'shell', args: ['--no-sandbox','--disable-gpu'], defaultViewport: {width:1600,height:1000}});
  const p = await b.newPage();
  await p.goto('http://localhost:5173', {waitUntil:'networkidle2'});
  await new Promise(r=>setTimeout(r,1500));
  const m = await p.evaluate(() => {
    const r = (s) => { const e = document.querySelector(s); if(!e) return null; const b = e.getBoundingClientRect(); return {top: Math.round(b.top), h: Math.round(b.height)}; };
    return {
      body: document.body.scrollHeight,
      maxScroll: document.body.scrollHeight - window.innerHeight,
      hero: r('.landing .hero'), features: r('.landing .features'), how: r('.landing .how'), foot: r('.landing .foot'),
    };
  });
  console.log(JSON.stringify(m));
  await p.screenshot({path: 'dbg-top.png'});
  await p.evaluate(() => window.scrollTo(0, 99999));
  await new Promise(r=>setTimeout(r,500));
  console.log('scrolled to', await p.evaluate(()=>window.scrollY));
  await p.screenshot({path: 'dbg-bottom.png'});
  await b.close();
})();

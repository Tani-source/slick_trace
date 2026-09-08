const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('response', response => {
    if (response.url().includes('arcgisonline')) {
      console.log('TILE NETWORK:', response.status(), response.url());
    }
  });

  await page.goto('http://localhost:5173/?demo=true');
  await page.waitForTimeout(3000);
  
  // Take screenshot
  await page.screenshot({ path: '/tmp/map_bug.png' });
  await browser.close();
  console.log("Screenshot saved to /tmp/map_bug.png");
})();

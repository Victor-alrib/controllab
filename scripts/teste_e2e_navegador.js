// Teste ponta a ponta (Playwright) usado durante o desenvolvimento para verificar a interface
// e capturar telas. Pré-requisitos: backend rodando em http://localhost:8000 servindo o frontend
// compilado (npm run build), 'npm install playwright' e uma pasta ./saida.
// Uso: node teste_e2e_navegador.js   — imprime os erros de console encontrados (esperado: []).
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto('http://localhost:8000/');
  await p.waitForSelector('.js-plotly-plot', { timeout: 20000 });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: './saida/1-sim.png' });
  await p.click('button:has-text("Registrar")'); await p.waitForTimeout(300);
  // change Kp via tuning lab
  await p.click('.tabs button:has-text("Sintonia PID")'); await p.waitForTimeout(1200);
  await p.click('button:has-text("Fixar como referência")');
  const kp = p.locator('.slider-head input.num').first();
  await kp.fill('6'); await p.waitForTimeout(1500);
  await p.screenshot({ path: './saida/2-tune.png' });
  await p.click('.tuning button:has-text("Registrar no histórico")'); await p.waitForTimeout(300);
  await p.click('.tabs button:has-text("Comparação")'); await p.waitForTimeout(1500);
  await p.screenshot({ path: './saida/3-compare.png' });
  await p.click('.tabs button:has-text("Análise")'); await p.waitForTimeout(1500);
  await p.screenshot({ path: './saida/4-analysis.png' });
  console.log('errors:', JSON.stringify(errs));
  await b.close();
})();

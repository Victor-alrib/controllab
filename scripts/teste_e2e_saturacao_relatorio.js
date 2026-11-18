// Teste ponta a ponta (Playwright) usado durante o desenvolvimento para verificar a interface
// e capturar telas. Pré-requisitos: backend rodando em http://localhost:8000 servindo o frontend
// compilado (npm run build), 'npm install playwright' e uma pasta ./saida.
// Uso: node teste_e2e_saturacao_relatorio.js   — imprime os erros de console encontrados (esperado: []).
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('http://localhost:8000/');
  await p.waitForSelector('.js-plotly-plot', { timeout: 20000 });
  await p.selectOption('select.model-select >> nth=0', 'first_order');
  await p.waitForTimeout(400);
  const satCard = p.locator('.card', { hasText: 'Saturação do atuador' });
  await satCard.locator('.card-head .toggle').click();
  await satCard.locator('.card-head h3').click();
  await p.waitForTimeout(200);
  const nums = satCard.locator('input.num');
  await nums.nth(0).fill('-1.5'); await nums.nth(1).fill('1.5');
  const dCard = p.locator('.card', { hasText: 'Perturbações' });
  await dCard.locator('button:has-text("Adicionar")').click();
  await p.waitForTimeout(1800);
  await p.screenshot({ path: './saida/5-sat.png' });
  const html = await p.evaluate(async () => {
    const cfg = JSON.parse(localStorage.getItem('controllab.config.v1'));
    const r = await fetch('/api/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runs: [{ label: 'Atual', config: cfg }] }) });
    return r.text();
  });
  require('fs').writeFileSync('./saida/report.html', html);
  const p2 = await b.newPage({ viewport: { width: 1100, height: 1500 } });
  await p2.setContent(html); await p2.waitForTimeout(500);
  await p2.screenshot({ path: './saida/6-report.png' });
  console.log('errors', JSON.stringify(errs));
  await b.close();
})();

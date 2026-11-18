# Arquitetura e roteiro de expansão

## Fluxo de uma simulação

```
UI (React) ──JSON SimulationRequest──► FastAPI /api/simulate
                                        │
                     build_plant()  ◄───┤───► build_controller()
                     (registry)         │      (registry)
                                        ▼
                     engine.simulate(): laço amostrado
                       a cada t_k = k·Ts:
                         y_k   = C x + D u + d_out(t_k) + ruído
                         u_cmd = controller.compute(ctx)
                         u_k   = sat(u_cmd)
                         controller.commit(u_k)
                         n sub-passos: x ← Φx + Γ·(u_k + d_in)   (ZOH exato, atraso por buffer)
                                        │
                     metrics.*  ◄───────┘
```

## Contratos

### Planta (`plants/base.py`)

- `param_specs`: lista de `ParamSpec` → validação e formulário automático.
- `state_space() -> (A, B, C, D)` contínuo, SISO.
- `initial_state() -> x0`.
- `delay` (parâmetro comum opcional).

Plantas **não lineares** (pêndulo, tanque com saída √h etc.) exigirão um segundo caminho
de integração (`solve_ivp` com passo controlado entre amostras, entrada constante por
partes). A proposta é uma classe `NonlinearPlant` com `f(x, u, t)`/`h(x, u)` e a
linearização `jacobian(x*, u*)` para a aba Análise; o motor escolhe o integrador pelo
tipo da planta.

### Controlador (`controllers/base.py`)

- `reset(ControllerInit)` — Ts, limites de saturação, condição inicial.
- `compute(ControllerContext) -> u_cmd` — recebe `r`, `y` medido **e o estado `x`**.
- `commit(u_aplicado)` — retorno do valor saturado (anti-windup, estados internos).
- `transfer_functions(domain, Ts)` — `(C_r, C_y)` exatos para análise, ou `None` se não linear.
- Flags `requires_state`, `is_linear`, `status`.

## Roteiro dos controladores avançados

Os três aparecem no catálogo como **planejados** e não podem ser selecionados. Não há
implementação simplificada escondida atrás desses nomes.

### LQR
- Parâmetros: matrizes Q (n×n, ≥ 0), R (> 0); opcional ação integral (LQI) para seguimento.
- Projeto: `K = dlqr(Φ_Ts, Γ_Ts, Q, R)` no domínio discreto (coerente com o controlador
  amostrado) — `scipy.linalg.solve_discrete_are`. Ganho de referência `N̄` por
  inversão do ganho DC, ou LQI com estado aumentado.
- Requer `ctx.x`; para estado não medido, adicionar observador (Luenberger/Kalman) como
  componente separado entre planta e controlador, para que o efeito do observador
  apareça nos resultados.
- `transfer_functions`: realimentação de estado → expor `K` e calcular os polos de
  `Φ − ΓK` diretamente na análise (o contrato atual de 2-GDL será estendido com um
  método `closed_loop_state_matrix`).

### Modos deslizantes (SMC)
- Superfície `σ = c·e + ė` (ou `σ = Sx`), lei `u = u_eq − k·sign(σ)` ou com camada-limite
  `sat(σ/φ)` como opção explícita, nunca como substituto silencioso.
- Exige `ė`: derivada por diferenças (com ruído) ou estado; deixar a escolha visível.
- Indicadores adicionais: amplitude/frequência de chattering, tempo de alcance.
- `is_linear = False` → a aba Análise informa que a análise linear não se aplica.
- Atenção à implementação discreta: o chattering depende de Ts; o simulador já trata Ts
  e a planta de forma exata, então o efeito será fiel.

### Super-Twisting (ST-SMC)
- `u = −k₁|σ|^{1/2} sign(σ) + v`, `v_{k+1} = v_k − Ts·k₂·sign(σ_k)` (discretização
  explícita, documentada como tal); condições de ganho (Levant/Moreno) exibidas com
  base na constante de Lipschitz da perturbação informada pelo usuário.
- Pode reutilizar a mesma superfície do SMC; implementar como subclasse com estado `v`.

## Frontend

- Formulários são gerados de `ParamSpec` (`components/ParamForm.tsx`): `float`, `int`,
  `bool`, `select`, `vector` e `matrix` (sintaxe MATLAB `0 1; -2 -3`). Para Q e R do LQR,
  o tipo `matrix` já existe.
- Novos indicadores: acrescentar ao dicionário retornado por `metrics.py` e a
  `METRIC_DEFS` em `components/MetricsPanel.tsx` (tabelas, comparação e CSV usam essa lista).

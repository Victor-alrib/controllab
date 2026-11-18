# Resultados registrados

Todos os números abaixo saíram de execuções reais do projeto (capturas de tela feitas com
Playwright, saída do pytest e chamadas à API). Nada foi estimado.

## 1. Testes automatizados

`saida-testes.txt`: **25 de 25 testes passando** (pytest 9.1.1, Python 3.13.18), execução
completa em ~6 s. São 21 testes de fidelidade matemática (`test_fidelity.py`, contando as
variações parametrizadas) e 4 da API (`test_api.py`).

| Teste | O que compara | Tolerância |
|---|---|---|
| `test_first_order_open_loop_exact` | Simulação × `K(1−e^{−t/τ})` | < 1e-10 |
| `test_first_order_initial_condition_free_response` | Resposta livre × `y0·e^{−t/τ}` | < 1e-10 |
| `test_second_order_step_and_overshoot[ζ]` | Simulação × fórmula fechada; Mp × `e^{−ζπ/√(1−ζ²)}`; tp × `π/ωd` | < 1e-9; rel. 1e-4; 2e-3 s |
| `test_second_order_initial_conditions` | Oscilador não amortecido com y0, ẏ0 | < 1e-9 |
| `test_tf_and_ss_agree_with_python_control` | TF e espaço de estados × `control.step_response` | < 1e-8 / < 1e-10 |
| `test_delay_is_exact_shift` | Atraso × deslocamento exato | < 1e-9 |
| `test_p_control_steady_state_error` | e_ss × `1/(1+K·Kp)` | < 1e-6 |
| `test_pi_zero_steady_state_error_with_input_disturbance` | PI rejeita perturbação degrau | \|e\| < 1e-5 |
| `test_simulated_loop_matches_exact_discrete_closed_loop[forward/backward/tustin]` | Malha PID simulada × malha fechada discreta construída por espaço de estados | < 1e-10 |
| `test_analysis_poles_consistent_with_stability` | Controle P: estável em tempo contínuo, instável com Ts = 0,2 s; análise e simulação concordam | — |
| `test_margins_first_order_with_delay` | Margem de fase com atraso × fórmula analítica | < 0,05° |
| `test_saturation_and_antiwindup_reduce_overshoot` | Clamping e back-calculation reduzem o overshoot sob saturação | qualitativo |
| `test_integral_metrics_first_order` | IAE = τ, ISE = τ/2, ITAE = τ² | rel. 1e-4 |
| `test_first_order_rise_and_settling` | tr = τ·ln 9, ts = τ·ln 50 | rel. 1e-4; 2e-3 s |
| `test_not_settled_is_flagged` | Resposta que não estabilizou não recebe tempo de acomodação | — |
| `test_step_metrics_window_excludes_later_disturbance` | Índices do degrau ignoram perturbação posterior | rel. 1e-3 |
| `test_invalid_inputs` | Parâmetros inválidos e controlador "planejado" são rejeitados | — |

## 2. Experimento de sintonia (capturas 01–04)

Planta `G(s) = 4/(s² + 1,2s + 4)` (K = 1, ωn = 2 rad/s, ζ = 0,3). PID com Ki = 1,5, Kd = 0,4,
Tf = 0,01 s, b = c = 1, integrador Euler progressivo, Ts = 0,01 s, degrau unitário em t = 0,
10 s simulados (1.000 amostras, sub-passo h = 0,0005 s).

| Indicador | #1 Kp = 2 | #2 Kp = 6 |
|---|---|---|
| Overshoot [%] | 3,327 | 33,39 |
| Tempo de subida [s] | 0,4727 | 0,2307 |
| Tempo de acomodação (2 %) [s] | 4,893 | 6,305 |
| Tempo de pico [s] | 0,8255 | 0,5405 |
| Erro em regime (t = 10 s) | 0,001371 | 0,01573 |
| IAE | 0,6724 | 0,7872 |
| ISE | 0,237 | 0,2082 |
| ITAE | 1,106 | 1,965 |
| Pico de controle max\|u\| | 22 | 26 |
| Esforço ∫u² dt | 15,61 | 23,41 |
| Variação total Σ\|Δu\| | 22,94 | 35,51 |
| Tempo saturado [%] | 0 | 0 |

O "erro em regime" não é zero mesmo com ação integral porque a janela de 10 s termina antes
de a cauda lenta do integrador desaparecer; com Kp = 6 há um polo em z = 0,9978 (≈ −0,22 rad/s).

### Análise linear com Kp = 6 (captura 04)

| Item | Valor |
|---|---|
| Polos da planta | −0,6 ± 1,908j (ωn = 2, ζ = 0,3) |
| Polos discretos de malha fechada | 0,9978; 0,9861 ± 0,05102j; 0,5125 |
| Raio espectral | 0,99781 → estável |
| Polos contínuos equivalentes | −98,358; −1,312 ± 5,116j; −0,219 |
| Margem de fase | 31,49° em 5,361 rad/s |
| Margem de ganho | ∞ |

Com Kp = 2, a mesma análise dá margem de fase de **52,37° em 3,467 rad/s** e raio espectral
de **0,99441** (estável).

## 3. Saturação + perturbação (captura 05)

Planta de 1ª ordem (K = 1, τ = 1 s), o mesmo PID com Kp = 2, saturação u ∈ [−1,5; 1,5],
perturbação degrau de 0,5 na entrada em t = 5 s.

| Indicador | Valor |
|---|---|
| Overshoot (janela [0, 5) s) | 0 % |
| Tempo de subida | 2,02 s |
| Tempo de acomodação | 3,526 s |
| Erro em regime antes da perturbação | 0,007328 |
| Erro final e(10 s) | −0,01112 |
| IAE / ISE / ITAE | 1,218 / 0,4607 / 2,976 |
| max\|u\| | 1,5 (limite da saturação) |
| Tempo saturado | 0,6 % |

Numa versão anterior, esse mesmo caso reportava **overshoot de 10,86 %**, causado pela
perturbação e não pelo seguimento da referência. A correção passou a calcular os índices do
degrau só na janela anterior à primeira perturbação (teste
`test_step_metrics_window_excludes_later_disturbance`).

## 4. Arquivos

- `capturas/01-simulacao.png` – aba Simulação (Kp = 2)
- `capturas/02-sintonia-pid.png` – laboratório de sintonia (Kp = 6 sobre referência Kp = 2)
- `capturas/03-comparacao.png` – comparação das duas execuções
- `capturas/04-analise.png` – polos, Bode e margens (Kp = 6)
- `capturas/05-saturacao-perturbacao.png` – caso da seção 3
- `capturas/06-relatorio-html.png` e `exemplo-relatorio.html` – relatório gerado pelo app
- `saida-testes.txt` – saída do pytest

## 5. Desempenho

Tempo de uma chamada a `/api/simulate` (planta de 2ª ordem + PID, Ts = 0,01 s), medido em um
ambiente Linux, incluindo a resposta HTTP:

| Amostras | Tempo |
|---|---|
| 1.000 | 0,12 s |
| 20.000 | 0,31 s |
| 200.000 (limite configurado) | 2,73 s |

Build de produção do frontend: 4,88 MB de JavaScript (1,48 MB com gzip), dominado pelo
Plotly.js.

## 6. Próximas validações

- Comparação numérica com MATLAB/Simulink para os mesmos casos.
- Avaliação com estudantes (usabilidade e ganho de aprendizado).
- Carregar o Plotly sob demanda para reduzir o bundle.

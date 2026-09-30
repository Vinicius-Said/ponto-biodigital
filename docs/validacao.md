# Validação do MVP

Resultado registrado em **30/09/2026**, com Python **3.12.14**, Flask 3.1.3 e SQLAlchemy 2.0.54 em Linux. As dependências de execução usadas estão em `requirements-lock.txt`.

## Resultados executados

| Verificação | Resultado |
|---|---|
| pytest com SQLite temporário | **78 passaram**, 2 ignorados por exigirem bloqueios InnoDB |
| pytest com MariaDB **10.11.14 / InnoDB** | **80 passaram**, sem falhas |
| Cobertura de linhas do pacote `app` | **88%** em ambos os bancos |
| Ruff e `pip check` | Sem erros de análise ou dependências incompatíveis |
| Migrations reais nos dois bancos | Upgrade inicial, estado de instalação, downgrade e novo upgrade verificados |
| Duas marcações simultâneas no MariaDB | Uma aplicada, uma bloqueada; uma única batida persistida |
| Duas solicitações simultâneas no MariaDB | Uma aplicada, uma bloqueada; uma única solicitação pendente |
| Chromium / Playwright 1.55.0 | Fluxo completo concluído, sem erros JavaScript |
| Interface | Desktop 1440 × 1000 e celular 390 × 844; navegação, tema persistido e ausência de overflow geral |
| PDF | Individual e consolidado gerados; relatório mensal renderizado em duas páginas e conferido visualmente |

O fluxo de navegador cobre setup com token, login, cadastro de funcionário, marcação, tema escuro após recarga, menu móvel, solicitação de correção, aprovação pela diretoria e download do PDF. Usa banco descartável, credenciais aleatórias e relógio de servidor controlado exclusivamente no script de teste. Não acessa o banco operacional.

## Regras e segurança cobertas

- Funcionário vê seus dados; diretoria administra a equipe; acesso anônimo e troca de identificadores não liberam dados indevidos.
- Sem credenciais administrativas padrão; setup exige token e fica indisponível após conclusão.
- CSRF nos POSTs, logout somente por POST, senhas com hash, tentativas de login limitadas e sessões revogadas após troca de senha/desativação.
- Escape de HTML e rejeição de tentativa de injeção no login; senhas não aparecem na auditoria.
- Horário e data da marcação vêm do servidor; envio de horário, funcionário ou cabeçalho de IP pelo cliente não substitui os valores autorizados.
- Sequência de quatro ou duas batidas, duplicidade, dia local de Brasília, sábado, domingo, feriado, ausência e registros incompletos.
- Vigência de jornadas, impedimento de alteração retroativa, desativação/reativação e seed idempotente.
- Solicitação, aprovação, recusa, ajuste direto, marcação esquecida, validação de ordem e preservação do registro original e das revisões.
- Retenção de auditoria por três meses de calendário, preservando marcações e correções.
- Filtros de período, geração de PDF, texto longo/malicioso e URLs sob `SCRIPT_NAME=/ponto`.

## Reproduzir a suíte

Depois de criar o ambiente conforme o README:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q --cov=app
.\.venv\Scripts\python.exe -m ruff check app tests scripts run.py passenger_wsgi.py
.\.venv\Scripts\python.exe -m pip check
```

Em Linux/macOS, substitua o executável por `.venv/bin/python`. Para MariaDB/MySQL, defina `TEST_DATABASE_URL` usando um banco **exclusivo e descartável cujo nome comece com `ponto_test`**. A fixture apaga e recria suas tabelas a cada cenário.

Exemplo apenas para um banco de teste local:

```powershell
$env:TEST_DATABASE_URL = "mysql+pymysql://USUARIO:SENHA_CODIFICADA@127.0.0.1:3306/ponto_test_local?charset=utf8mb4"
.\.venv\Scripts\python.exe -m pytest -q --cov=app
Remove-Item Env:TEST_DATABASE_URL
```

Não use credenciais ou banco de produção nesse comando. A proteção pelo prefixo do nome ajuda a evitar erro, mas não substitui conferir o ambiente.

## Verificação opcional no navegador

Não é necessária para iniciar o aplicativo. Para reproduzir a homologação da interface:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/browser_smoke.py
```

O script inicia um servidor HTTP local em porta livre e encerra ao concluir. Capturas de tela e o PDF de homologação ficam em `tmp/ui`, ignorado pelo Git. O relógio controlado mantém o cenário em um dia útil mesmo quando executado no fim de semana.

## Integração contínua e limites

O workflow `.github/workflows/ci.yml` configura SQLite em Python 3.10/3.12 e um serviço MariaDB 10.11. Cada commit e pull request dispara a suíte; o resultado de cada execução fica na aba Actions do GitHub. Os números acima descrevem a validação local concluída.

Não foi feito deploy na hospedagem cPanel, nem verificada sua versão real de Python. O entrypoint Passenger e o prefixo `/ponto` estão preparados, com procedimento em [deploy-cpanel.md](deploy-cpanel.md). A instalação em Windows está documentada; a suíte local desta entrega foi executada em Linux. Impressão física, backup/restauração da hospedagem e operação com a equipe real dependem da homologação no ambiente da empresa.

# Ponto Biodigital

MVP 0.1.0 do controle interno de ponto da Biodigital, implementado com Python/Flask, Jinja2 e MySQL/MariaDB. Preparado para o cPanel Application Manager/Passenger em `https://biodigital.com.br/ponto`.

## Funcionalidades

- Configuração inicial do primeiro diretor com token de instalação; sem usuário ou senha padrão.
- Login por usuário e senha, CSRF, hash scrypt, sessões e autorização no backend.
- Perfis **FUNCIONARIO** e **DIRETORIA**, com isolamento do histórico individual.
- Cadastro de funcionário e acesso, desativação/reativação, redefinição de senha e criação de outros diretores.
- Jornadas 08h–17h, 09h–18h e 13h–18h, sábado 09h–13h e domingo de folga.
- Novas jornadas e histórico de vigência, sem reescrever jornadas anteriores.
- Cadastro de feriados aplicáveis à empresa pela diretoria.
- Marcações pelo relógio do servidor, IP observado, validação de sequência e proteção contra envio duplicado.
- Histórico por dia, semana, mês ou período personalizado de até 366 dias.
- Correção de horário ou marcação esquecida, aprovação/recusa e ajuste administrativo com motivo.
- Marcações originais e histórico de correções preservados permanentemente.
- Dashboard do funcionário e da diretoria, PDF individual/consolidado e impressão.
- Auditoria administrativa dos últimos três meses; comando de expurgo separado do histórico de ponto.
- Interface responsiva, tema claro/escuro persistido no navegador e Bootstrap local.

## Rodar no Windows

Pré-requisitos: Git e Python **3.10 ou superior**. A versão usada nos testes está documentada em [Validação](docs/validacao.md). Use inicialmente o SQLite local; a produção utiliza MySQL/MariaDB.

No PowerShell, dentro da pasta onde deseja clonar:

```powershell
git clone https://github.com/Vinicius-Said/ponto-biodigital.git
cd ponto-biodigital
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Edite `.env` no VS Code. Coloque o valor gerado em `SECRET_KEY`. Execute o último comando novamente e use **outro valor** em `SETUP_TOKEN`. Mantenha `APP_ENV=development`, `DATABASE_URL=sqlite:///ponto.db`, `APPLICATION_ROOT=/` e `SESSION_COOKIE_SECURE=false` para o primeiro teste local.

A seguir:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m flask --app run seed
.\.venv\Scripts\python.exe run.py
```

Abra `http://127.0.0.1:5000/setup`. Informe o `SETUP_TOKEN`, escolha seu usuário de diretor e uma senha de 10 a 128 caracteres. Depois faça login e cadastre a equipe. A rota de configuração é desabilitada após o primeiro cadastro. Remova o `SETUP_TOKEN` do ambiente após concluir.

O arquivo SQLite fica em `instance/ponto.db`, fora do Git. O uso dos executáveis completos acima dispensa ativar o ambiente e alterar a política de execução do PowerShell.

## Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Edite SECRET_KEY e SETUP_TOKEN conforme o procedimento acima.
.venv/bin/python -m flask --app run db upgrade
.venv/bin/python -m flask --app run seed
.venv/bin/python run.py
```

## MySQL/MariaDB

Crie um banco exclusivo e configure `.env`:

```dotenv
DATABASE_URL=mysql+pymysql://USUARIO:SENHA_CODIFICADA@127.0.0.1:3306/BANCO?charset=utf8mb4
```

Caracteres reservados da senha precisam ser codificados na URL. Para evitar exibir uma senha na linha de comando, use:

```bash
python -c "from getpass import getpass; from urllib.parse import quote; print(quote(getpass('Senha do banco: '), safe=''))"
```

Execute `flask --app run db upgrade` no ambiente que aponta para esse banco. Migrations criam o schema e o estado de configuração; `seed` somente cria jornadas e pode ser repetido. A conexão deve usar InnoDB e `utf8mb4`; recomenda-se MariaDB 10.6+ ou MySQL 8.0+. Não execute `db create_all` nem `db stamp` como substitutos das migrations.

## cPanel

Siga [o guia completo de instalação e atualização](docs/deploy-cpanel.md). Ele inclui ambiente virtual, banco, variáveis, `/ponto`, Passenger, reinicialização, cron de logs e backup. **A versão e o caminho do Python do servidor ainda precisam ser confirmados no ambiente real.**

`passenger_wsgi.py` disponibiliza `application`; não inicia servidor de desenvolvimento. Em produção o aplicativo exige MySQL/MariaDB, segredo forte, cookies seguros e debug desativado.

## Regras de cálculo

O total realizado soma intervalos de trabalho entre marcações válidas; não aplica desconto fixo além do intervalo efetivamente registrado. A previsão usa a jornada vigente na data. Sábado não exige intervalo; domingos e feriados cadastrados têm previsão zero. O turno 13h–18h possui duas marcações.

O **saldo apurado** soma somente dias completos, folgas e dias passados sem registro. Dias em andamento, incompletos ou sem jornada ficam identificados, sem transformar dados insuficientes em um saldo final. Segmentos fechados de dias incompletos podem aparecer no realizado parcial.

Não há tolerância automática, folha de pagamento, adicional noturno, fechamento mensal ou banco de horas formal. Jornadas que cruzam a meia-noite estão fora do MVP. A diferença de horas é informativa conforme as regras cadastradas pela empresa.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests run.py passenger_wsgi.py
```

A suíte usa bancos temporários criados por migrations reais. Para testar MariaDB/MySQL, defina `TEST_DATABASE_URL` com um **banco descartável cujo nome comece com `ponto_test`**. A suíte apaga e recria o schema desse banco; nunca aponte testes para dados de operação.

O workflow de GitHub Actions executa testes com SQLite e MariaDB. Veja também [os critérios de validação](docs/validacao.md).

## Documentação

- [Especificação e rastreabilidade dos requisitos](docs/especificacao.md)
- [Arquitetura e banco](docs/arquitetura.md)
- [Instalação, atualização e backup no cPanel](docs/deploy-cpanel.md)
- [Uso diário e administração](docs/operacao.md)
- [Validação do MVP](docs/validacao.md)

Segredos, backups, banco local e dados reais da equipe não devem entrar no Git. Não existe conta administrativa padrão no código.

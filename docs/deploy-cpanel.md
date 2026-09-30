# Instalação no cPanel / Passenger

Este procedimento publica o repositório em `https://biodigital.com.br/ponto`. A publicação depende do acesso ao cPanel da empresa e dos recursos efetivos do servidor. O MVP não criou uma aplicação de produção nem alterou o site institucional.

## 1. Confirmar o ambiente

No Terminal do cPanel ou SSH da própria conta, confira `python3 --version`. O projeto requer Python 3.10+. Se o Python padrão for antigo, o provedor precisa disponibilizar um interpretador compatível e configurar o Passenger para utilizá-lo. Verifique também ambiente virtual/pip, Application Manager, Passenger e módulo de variáveis `mod_env`. O caminho do interpretador não pode ser inferido pela tela do painel.

Não execute comandos administrativos do WHM como usuário comum. Peça ao responsável pela hospedagem a configuração do interpretador caso necessário.

## 2. Obter o código fora de public_html

Pelo Git Version Control do cPanel, clone o repositório para `ponto-biodigital`, relativo à home da conta. Alternativamente, no Terminal, substitua `SEU_USUARIO`:

```bash
cd /home/SEU_USUARIO
git clone https://github.com/Vinicius-Said/ponto-biodigital.git
cd ponto-biodigital
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
```

Se usar outro Python compatível, crie a venv com o caminho dele. `requirements-lock.txt` registra o conjunto validado; não inclui ferramentas de teste. Mantenha todo o código e `.env` fora do diretório público.

## 3. Criar o banco

Em MySQL Databases/Database Wizard, crie banco e usuário exclusivos. Os nomes do cPanel normalmente possuem o prefixo da conta: use os nomes completos fornecidos pelo painel. Associe o usuário ao banco e conceda privilégios necessários para criar/alterar o schema e operar os dados. Nunca use o root do servidor na aplicação.

Prefira InnoDB, utf8mb4, MariaDB 10.6+ ou MySQL 8.0+. Se a hospedagem só permitir outro banco/versão, confirme compatibilidade antes da homologação. Host e porta dependem do provedor.

## 4. Configurar o ambiente

Gere `SECRET_KEY` e `SETUP_TOKEN` distintos, cada um com `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Use variáveis no Application Manager e também disponibilize os mesmos valores para os comandos no Terminal. Uma opção prática é manter um `.env` privado na raiz do aplicativo, com permissão `600`. A aplicação lê esse arquivo, mas variáveis existentes no processo têm prioridade. Não coloque credenciais diferentes no painel e no arquivo.

| Variável | Valor de produção |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | Segredo aleatório gerado exclusivamente para produção |
| `SETUP_TOKEN` | Outro token aleatório, somente durante a instalação |
| `DATABASE_URL` | `mysql+pymysql://USUARIO:SENHA_CODIFICADA@HOST:3306/BANCO?charset=utf8mb4` |
| `APPLICATION_ROOT` | `/ponto` |
| `SESSION_COOKIE_SECURE` | `true` |
| `PASSENGER_PYTHON` | `/home/SEU_USUARIO/ponto-biodigital/.venv/bin/python` |
| `PROXY_FOR_COUNT` | `0`, salvo configuração real verificada |
| `PROXY_PROTO_COUNT` | `0`, salvo configuração real verificada |
| `PROXY_PREFIX_COUNT` | `0`, salvo configuração real verificada |

Não habilite trust de `X-Forwarded-For` apenas para mudar o IP exibido. O provedor deve informar quais cabeçalhos são definidos e quantos proxies confiáveis existem. HTTPS deve estar ativo antes de usar cookies Secure. `APP_ENV` é a opção deste projeto; não use o antigo `FLASK_ENV` para configurar produção.

## 5. Migrations e seed

Com `.env` configurado ou variáveis exportadas no Terminal:

```bash
cd /home/SEU_USUARIO/ponto-biodigital
.venv/bin/python -m flask --app run db upgrade
.venv/bin/python -m flask --app run seed
```

Nunca rode a suíte de testes no banco operacional. Se já existir um banco criado por um protótipo sem migrations, faça backup e planeje a migração dos dados; não marque o schema antigo como atualizado com `db stamp`.

## 6. Registrar no Application Manager

| Campo | Preenchimento |
|---|---|
| Application Name | `biodigital-ponto` |
| Deployment Domain | `biodigital.com.br` |
| Base Application URL | `/ponto` |
| Application Path | `ponto-biodigital`, relativo a `/home/SEU_USUARIO` |
| Deployment Environment | `Production` |

Confirme as variáveis, o interpretador e a existência de `passenger_wsgi.py`. O entrypoint expõe `application` e utiliza a venv indicada. Clique Deploy quando o código, banco, HTTPS e configuração estiverem prontos.

O Passenger deve entregar o prefixo como `SCRIPT_NAME=/ponto`. Todas as URLs são geradas por `url_for`; não acrescente `/ponto` diretamente às rotas. `APPLICATION_ROOT` também configura o caminho do cookie. Se as URLs geradas apontarem para `/login` em vez de `/ponto/login`, confira o mapeamento e cabeçalhos do Passenger com o provedor.

## 7. Primeiro diretor e homologação

Abra `https://biodigital.com.br/ponto/setup` e informe o token da instalação. Crie a conta e faça login. Remova o token após concluir; a rota também fica bloqueada pelo estado persistido no banco.

Cadastre os funcionários reais, datas de início e jornadas, e depois os feriados aplicáveis. Faça um teste com uma conta própria de homologação: marcação, histórico, pedido de correção, aprovação, PDF e desativação. Confirme que um funcionário não acessa outro funcionário nem páginas administrativas. Confirme IP, data de Brasília, cookies e operação no celular. Registros de homologação não devem ser confundidos com a jornada real da equipe; prefira banco de homologação separado.

## 8. Reinicialização e diagnóstico

Depois de alterações:

```bash
mkdir -p tmp
touch tmp/restart.txt
```

O Passenger verifica esse arquivo para reiniciar. Consulte `stderr.log` no diretório da aplicação em caso de erro. Verifique o caminho da venv, variáveis acessíveis ao Passenger, banco, permissões e migrations. Não habilite debug em produção nem sirva a aplicação por `flask run` ao público.

`/ponto/health` deve responder JSON. Esse endpoint não consulta o banco; valide também o login e uma tela com dados.

## 9. Retenção dos logs

Configure um Cron Job diário no cPanel, substituindo a conta:

```cron
15 3 * * * cd /home/SEU_USUARIO/ponto-biodigital && /home/SEU_USUARIO/ponto-biodigital/.venv/bin/python -m flask --app run prune-logs
```

O horário do cron segue o servidor. O comando expurga auditoria anterior a três meses de calendário e tentativas de login antigas. Batidas e correções não são apagadas. Sem o cron, logs antigos deixam de aparecer na tela, mas permanecem armazenados até o comando ser executado. A retenção de `stderr.log` e dos backups é uma política separada da hospedagem.

## 10. Backup e restauração

Defina com a infraestrutura frequência, retenção e cópia fora do servidor. Use os recursos de backup do cPanel ou dump do banco, preservando o `.env` em local protegido e o commit instalado. Não coloque dumps no Git ou em `public_html`.

Exemplo manual: `mysqldump -h HOST -u USUARIO -p --single-transaction BANCO > /home/SEU_USUARIO/backups/ponto-AAAA-MM-DD.sql`. A opção `-p` pede a senha sem gravá-la no comando. Crie o diretório fora do público e restrinja suas permissões. Para restaurar, use banco separado, importe o dump, confira `alembic_version` e teste login/histórico/correções/PDF antes de trocar a configuração de produção. Não rode `seed` como substituto da restauração dos dados.

## 11. Atualizações

Faça backup e registre o commit atual. Obtenha a versão validada por `git pull --ff-only`, instale o lock de dependências, execute `flask --app run db upgrade` e toque `tmp/restart.txt`. Verifique os fluxos principais. Uma volta ao código anterior exige compatibilidade do schema; downgrade do banco só deve ocorrer com plano e backup, pois pode remover dados.

## Referências oficiais

- [cPanel: Application Manager](https://docs.cpanel.net/cpanel/software/application-manager/)
- [cPanel: Python WSGI](https://docs.cpanel.net/knowledge-base/web-services/how-to-install-a-python-wsgi-application/)
- [Flask: proxies confiáveis](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/)
- [Flask-WTF: proteção CSRF](https://flask-wtf.readthedocs.io/en/1.2.x/csrf/)

Consultadas em 30/09/2026. As decisões específicas de banco, token, prefixo e comandos descrevem este projeto.

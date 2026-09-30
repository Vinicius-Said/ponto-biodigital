# Especificação do MVP 0.1.0

Data: 30/09/2026. Empresa: Biodigital. Responsável: Vinícius Said. Base: documento aprovado **Planejamento_Sistema_Ponto_Biodigital.docx**, versão 1.0, e decisões da conversa do projeto. Esta especificação descreve a implementação entregue.

## Proposta e escopo

Centralizar o ponto de aproximadamente cinco funcionários e três diretores, com autenticação individual, histórico, cálculo conforme jornadas, correções rastreáveis e relatório. Aplicação monolítica modular acessível por navegador em desktop e celular. URL de implantação: `https://biodigital.com.br/ponto`.

A solução substitui acompanhamento manual por dados estruturados. Não integra folha, GPS, biometria, multiempresa, e-mail, 2FA, gráficos, importação CSV/Excel ou legislação trabalhista. Não realiza exclusão física de funcionários ou marcações, fechamento mensal ou bloqueio do histórico por competência.

## Requisitos funcionais e implementação

| ID | Requisito | Entrega |
|---|---|---|
| RF-01 a RF-03 | Login, logout e sessão | `/login`, POST `/logout`, cookies, revogação por versão e expiração |
| RF-04 e RF-05 | Cadastro e desativação | Funcionários, desativação/reativação com histórico preservado |
| RF-06 | Usuários e senhas | Cadastro, ativação, desativação, redefinição e alteração da própria senha |
| RF-07 a RF-09 | Ponto, servidor e IP | Sequência automática validada no backend, UTC e data local, IP observado |
| RF-10 a RF-12 | Histórico e filtros | Próprio histórico e visão administrativa, dia/semana/mês/personalizado |
| RF-13 a RF-15 | Solicitação, decisão e auditoria | Correção de horário ou marcação esquecida, motivo, decisão e cadeia permanente |
| RF-16 | Cálculo de jornada | Previsto, realizado, saldo apurado e dias pendentes |
| RF-17 | Jornada histórica | `employee_schedules` com vigência inclusiva, novas versões imutáveis |
| RF-18 e RF-19 | Dashboards | Dia do funcionário, situação diária da equipe e correções pendentes |
| RF-20 | Relatórios | PDF individual/consolidado, correções e impressão do navegador |
| RF-21 | Logs | Usuário, ação, entidade, IP, data/hora UTC e contexto JSON |
| RF-22 e RF-23 | Tema e responsividade | Tema claro/escuro, navegação móvel e tabelas com rolagem própria |
| RF-24 | Configuração inicial | Token de instalação, criação do primeiro diretor e bloqueio após conclusão |

## Requisitos não funcionais

Hash scrypt; autorização no backend; CSRF global; consultas parametrizadas por ORM; saída HTML escapada; segredos em variáveis de ambiente; cookies HttpOnly/SameSite=Lax; cookies Secure e HTTPS em produção; CSP restritiva; tratamento de erros; invalidação de sessões após troca de senha/status; limite de tentativas de login persistido no banco. A autorização verifica o funcionário associado mesmo quando IDs são enviados pelo cliente.

Código modularizado em modelos, serviços, blueprints, formulários, templates e configuração. Migrations Alembic versionadas. Testes funcionais e de segurança. Banco relacional com chaves, índices e restrições. Sem dependência de um frontend separado ou runtime Node.js no servidor. Dependências principais em `requirements.txt`, versões testadas em `requirements-lock.txt`.

## Regras de negócio

| Jornada | Segunda a sexta | Intervalo previsto | Sábado | Domingo |
|---|---|---|---|---|
| 1 | 08:00–17:00 | 60 minutos | 09:00–13:00 | Folga |
| 2 | 09:00–18:00 | 60 minutos | 09:00–13:00 | Folga |
| 3 | 13:00–18:00 | Sem intervalo | 09:00–13:00 | Folga |

Feriados aplicáveis à empresa são cadastrados pela diretoria; não há calendário presumido. A previsão dessas datas é zero. Marcações em dias de folga podem ser registradas e o realizado aparece como diferença positiva.

Jornadas sem intervalo usam ENTRADA → SAIDA. As demais usam ENTRADA → INTERVALO_SAIDA → INTERVALO_RETORNO → SAIDA. O dia e o tipo esperado enviados pelo formulário são conferidos com o estado atual; o horário é calculado exclusivamente no servidor. Uma marcação de cada tipo por funcionário/data. O banco e o bloqueio de linha do funcionário evitam duplicidades e concorrência em produção.

Uma nova vigência não pode retroagir nem sobrepor o início da última jornada. Jornada já criada não possui rota de edição. A desativação encerra a vigência atual, cancela agendamentos futuros, bloqueia os acessos e preserva registros. Reativação abre nova vigência e não converte o período sem jornada em faltas.

Somente dias concluídos e dias passados sem registro entram no saldo; dias incompletos continuam pendentes. Atraso é uma comparação informativa da entrada registrada com o horário previsto, sem tolerância ou penalidade presumida. Ausências anteriores ao início do controle e lacunas sem jornada não geram saldo negativo.

## RBAC

| Ação | Funcionário | Diretoria |
|---|---|---|
| Login/logout e alterar própria senha | Sim | Sim |
| Registrar próprio ponto | Sim | Não |
| Consultar próprio histórico | Sim | Acessa todos os funcionários |
| Consultar outro funcionário | Não | Sim |
| Solicitar correção própria | Sim | Ajuste administrativo com motivo |
| Aprovar/recusar solicitação | Não | Sim |
| Funcionários, jornadas, usuários e feriados | Não | Sim |
| Auditoria, PDFs e impressão administrativa | Não | Sim |

A ocultação de ações na interface complementa as verificações do backend. O último diretor ativo não pode ser desativado.

## Correções e retenção

Cada solicitação guarda horário anterior, desejado, motivo, situação, revisor, justificativa e datas. A aprovação mantém `recorded_at` original e aplica `corrected_at`. Marcação esquecida só é incluída após aprovação, com origem CORRECAO. Não se presume um registro original que nunca existiu.

O horário precisa respeitar a mesma data local e a ordem das demais marcações, não pode ser futuro e precisa de jornada vigente. Uma solicitação já decidida não pode ser reaprovada; pedidos pendentes duplicados são bloqueados. O backend revalida a sequência e o horário anterior durante a aprovação para detectar alteração concorrente.

A cadeia de solicitações/decisões é permanente. A auditoria operacional fica disponível por três meses de calendário e é expurgada por comando/cron. Remover esses logs não apaga batidas nem decisões.

## Stack e infraestrutura

Python 3.10+, Flask 3.1, Flask-SQLAlchemy/SQLAlchemy 2.0, Flask-Login, Flask-WTF, Flask-Migrate/Alembic, Werkzeug, PyMySQL, ReportLab, Jinja2, Bootstrap 5.3.8 e CSS/JS próprios. SQLite é oferecido para aprendizado local; produção exige MySQL/MariaDB com InnoDB e utf8mb4. Aplicação servida por Apache/Passenger pelo Application Manager do cPanel. Git/GitHub para código e histórico.

## Decisões de implementação

Foram adicionadas três estruturas auxiliares: `holidays` para folgas reais; `system_state` para configuração única e serialização de ações administrativas; `login_attempts` para limite de autenticação compartilhado pelos processos Passenger. Não são módulos adicionais de RH.

Os estilos Bootstrap são locais para dispensar CDN. O comando `seed` nunca cria credenciais. A produção não executa migrations automaticamente a cada worker; elas são uma operação explícita de instalação/atualização. A confirmação da versão efetiva do Python e a homologação no cPanel real continuam sendo etapas de implantação.

## Critério de conclusão

Fluxos completos no GitHub, instalação reproduzível, migrations versionadas, testes aprovados, interface verificada e guias operacionais. Publicação no servidor, credenciais de produção, backup definitivo e homologação com a equipe são etapas posteriores à entrega do código.

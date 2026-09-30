# Uso do sistema

## Funcionário

Faça login com usuário e senha recebidos. Na visão geral, confira a jornada e o status do dia e clique no botão que indica a próxima marcação. A sequência é validada no servidor. O turno de cinco horas, sábado e folgas usam entrada e saída; o turno com intervalo usa quatro marcações.

Em Meu histórico, escolha hoje, semana, mês ou personalizado. No período personalizado selecione as datas e clique Filtrar. Horários ajustados são identificados. Realizado parcial e saldo pendente significam que faltam marcações para concluir a apuração.

Para corrigir um horário ou informar uma marcação esquecida, abra Correções, informe data, tipo, novo horário e motivo. A diretoria aprova ou recusa e o histórico mostra a decisão. Não tente marcar uma saída como se fosse uma entrada perdida; peça a correção do tipo correto.

Altere sua senha clicando no seu usuário no cabeçalho. A troca encerra todas as sessões. Use Sair para encerrar o acesso no navegador. O botão de tema alterna claro/escuro e salva a preferência neste navegador.

## Diretoria

Na visão geral consulte a equipe e as pendências. Funcionários permite cadastrar nome, início do controle, jornada, usuário e senha inicial. Escolha a data de início real do controle: dias passados com jornada mas sem registros aparecerão como Sem registro e gerarão diferença negativa.

No detalhe do funcionário consulte o histórico, edite o nome, defina nova vigência, redefina senha ou desative. A desativação encerra a vigência e bloqueia o login, mantendo todos os dados. Ao reativar, escolha a jornada para o novo período. Jornadas antigas são preservadas; crie outra jornada para mudar os horários e vincule a nova vigência.

Feriados precisam ser cadastrados conforme o calendário da empresa. Feriados passados não podem ser removidos pela interface. Inserir uma data passada recalcula a previsão dessa data e registra uma ação de auditoria.

Em Correções, consulte pedidos pendentes, leia os horários e o motivo, e aprove ou recuse. Recusa exige justificativa. Uma solicitação não pode ser decidida novamente. Também é possível ajustar o ponto diretamente pelo detalhe do funcionário, informando data, horário e motivo; esse ajuste usa a mesma validação e mantém a cadeia de correções.

Usuários e acessos permite cadastrar outros diretores e administrar logins. O cadastro de funcionário já cria seu acesso. Não existe senha recuperável no banco: use a redefinição. Nunca publique credenciais no GitHub. Um diretor não pode desativar a própria conta; deve existir pelo menos um diretor ativo.

Relatórios permite selecionar um funcionário ou toda a equipe, escolher o período e baixar PDF ou imprimir. Inclui horários, previstos, realizados, saldo, situação e correções. O saldo apurado exclui dias pendentes; o total realizado pode conter segmentos fechados de dias incompletos.

Auditoria mostra ações recentes com IP e usuário. Correções anteriores a três meses permanecem no histórico das solicitações e nos relatórios, mesmo depois do expurgo dos logs operacionais.

## Manutenção

O responsável pela hospedagem executa migrations em atualizações, mantém o cron de `prune-logs`, backups, monitoramento e teste periódico de restauração. Não há agendamento interno persistente em workers Passenger. O ambiente de homologação deve usar banco próprio.

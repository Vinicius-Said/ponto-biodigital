# Ponto Biodigital

Sistema web de controle de ponto interno da Biodigital.

## Objetivo

Aplicação para registro, consulta e gerenciamento de ponto dos colaboradores da empresa.

## MVP

- Autenticação por usuário e senha
- RBAC com duas permissões:
  - FUNCIONARIO
  - DIRETORIA
- Cadastro e gerenciamento de funcionários
- Registro de ponto com data, hora e IP
- Histórico individual de marcações
- Solicitação e aprovação de correções
- Auditoria administrativa
- Relatórios PDF

## Stack definida

- Python
- Flask
- SQLAlchemy
- MySQL/MariaDB
- Jinja2
- Bootstrap

## Implantação alvo

Servidor compartilhado com cPanel utilizando Passenger WSGI.

## Status

Projeto em desenvolvimento - MVP inicial.

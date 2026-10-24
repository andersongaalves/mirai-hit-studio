# Auditoria setorial - S02 Identidade e acesso

Status do setor: **DIAGNOSTICADO**. Este documento nao autoriza correcao, migration,
merge ou deploy (Etapa 06, secao 13).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA analisado | `18caa5b` (main). Sem mudanca de codigo desde `8a7ac44` |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; 8 suites Playwright locais com API simulada; sondagens de backend no CI (harness SQLite isolado, branch descartavel `audit/s02-probes`); 2 consultas agregadas somente leitura no banco de producao |
| Limitacoes | Suites Python nao rodam localmente (PyPI indisponivel). Nenhum teste em producao. Os ambientes do Render nao foram lidos, entao o TTL real do token foi inferido de `.env.example` (60 min) e do CI (30 min) |

Suites executadas, todas verdes: `acesso`, `auth_sessions`, `client_access`,
`client_signup`, `password_recovery`, `usuarios`, `security`, `admin_foundation`.

## 2. Inventario

**Rotas (backend)**

| Rota | Acesso | Observacao |
| --- | --- | --- |
| `POST /auth/login` | Publica | Limite por IP 10/min (SQLite local do processo) |
| `GET /auth/me` | Sessao | Devolve o usuario completo |
| `POST /auth/client-signup[/resend]`, `/auth/password-recovery[/reset]` | Publica | Limites em `auth_rate_limits` (por origem e por identidade) |
| `POST /cliente-acessos/validar`, `/ativar` | Publica com token | Token de uso unico, 48 h |
| `/propostas/{id}/acesso-cliente[/convidar,/reenviar,/revogar]` | Admin | Convite comercial |
| `GET/POST/PATCH /usuarios[...]`, `/produtores`, `/senha`, `/classificacao` | Admin | Edicao e `PATCH`; reset de senha incrementa `auth_version` |

**Contrato de sessao**: JWT `sub` = **username**, `av` = `auth_version`, sem refresh em
uso (`create_refresh_token` existe mas nao e chamado). O token fica em `localStorage`, uma
chave por papel (`mirai.auth.{admin,produtor,cliente}.access_token`). "Sair" so apaga a
chave local.

**Telas**: `/acesso` (unificada), `/cadastro`, `/ativar`, `/recuperar-senha`,
`/redefinir-senha`; formularios de login proprios em `/admin`, `/cliente` e `/produtor`;
Admin > Usuarios (lista, modal, reset de senha, classificacao).

**Tabelas**: `usuarios` (inclui `nome_exibicao`, `painel_beats`, `is_test`),
`cliente_acessos`, `auth_rate_limits`.

**Dados (agregados, 24/10)**: 1 admin, 4 produtores (todos com nome de exibicao),
4 clientes (todos com letras maiusculas no login). Nenhuma colisao de login ignorando
maiusculas/espacos.

## 3. Fluxos

- Principal: `/acesso` -> login -> redireciona ao painel do papel (cliente aceita `next`).
- Cliente novo: cadastro publico ou convite -> e-mail -> `/ativar` -> cria login e senha
  -> volta a `/acesso` para entrar.
- Recuperacao: `/recuperar-senha` -> e-mail (somente cliente ativado) -> `/redefinir-senha`.
- Alternativos: abrir `/admin`, `/cliente` ou `/produtor` sem sessao, sair, expirar ou
  receber 401 mostra o **formulario antigo do proprio painel** (nao a tela unificada).
- Erro: credenciais invalidas (401 generico), conta inativa (mesma mensagem), limite (429).

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S02-001 | P1 | 4.6 Seguranca | Sessao de conta renomeada autentica a nova conta criada com o mesmo login | Aberto |
| AUD6-S02-002 | P2 | 4.6 Seguranca | Reativar uma conta revalida tokens emitidos antes da desativacao | Aberto |
| AUD6-S02-003 | P2 | 4.1 / 5 Fluxo | Paineis ainda exibem os logins antigos em vez de levar a `/acesso` | Aberto |
| AUD6-S02-004 | P2 | 4.8 / 4.6 | Ninguem consegue trocar a propria senha; produtor e equipe nao tem recuperacao | Aberto |
| AUD6-S02-005 | P2 | 4.1 Admin | Conta de cliente aberta em Usuarios nao pode ser salva | Aberto |
| AUD6-S02-006 | P2 | 4.1 / 4.8 | Login diferencia maiusculas; logins que diferem so por maiusculas podem coexistir | Aberto |
| AUD6-S02-007 | P2 | 4.6 (dep. S12) | Token em `localStorage` com CSP apenas em Report-Only; "Sair" nao revoga | Aberto |
| AUD6-S02-008 | P3 | 4.6 | Enumeracao de usuarios pelo tempo de resposta do login | Aberto (era AUD-S02-001) |
| AUD6-S02-009 | P3 | 4.6 / 4.10 | Limite de login so por IP e em armazenamento local do processo | Aberto |
| AUD6-S02-010 | P3 | 4.9 / 4.5 | Login do Admin nao envia com Enter e sugere o usuario "admin" | Aberto |
| AUD6-S02-011 | P3 | 4.4 | Portais mostram o login (username) em vez do nome de exibicao | Aberto |
| AUD6-S02-012 | P3 | 4.5 | `/auth/me` devolve ao proprio usuario classificacao interna e flags administrativas | Aberto |
| AUD6-S02-013 | P3 | 4.8 | `/acesso` com sessao valida pede login de novo | Aberto |
| AUD6-S02-014 | P3 | 4.4 / 4.2 | Textos e detalhes das telas de acesso | Aberto |
| AUD6-S02-015 | P3 | 4.8 / 4.10 | Sessao expira sem aviso nem renovacao | Aberto (decisao) |

### AUD6-S02-001 - Sessao de conta renomeada passa para a nova conta (P1)

| Campo | Conteudo |
| --- | --- |
| Setores impactados | S09 (Admin > Usuarios), S07, S08 |
| Evidencia | Sondagem no CI: produtor `joao` (id 2) com token valido; Admin renomeia para `joao-antigo` e cria um novo `joao` com papel admin. O token antigo em `GET /auth/me` retorna **id 3, papel admin** (200) |
| Impacto | Acesso indevido, inclusive com privilegio administrativo, durante a validade do token. Exige que o Admin reutilize um login dentro desse prazo; pelo criterio de severidade e acesso indevido, por isso fica acima de P2 |
| Causa | `sub` do JWT e o username e `get_current_user` busca por username; renomear nao incrementa `auth_version`, e a nova conta nasce com `auth_version = 0` |
| Recomendacao | Minimo: incrementar `auth_version` ao trocar o username (encerra as sessoes da conta renomeada). Estrutural: usar o id estavel no `sub`, mantendo leitura do formato antigo ate os tokens expirarem |
| Teste necessario | Regressao renomear + recriar retornando 401 |
| Dependencias | Nenhuma; nao exige migration |

### AUD6-S02-002 - Reativacao revalida tokens antigos (P2)

- Evidencia: sondagem no CI. Token emitido antes da desativacao: 401 enquanto inativa,
  **200 apos reativar**.
- Impacto: sessoes de alguem afastado voltam a valer sem novo login (ex.: dispositivo
  compartilhado ou token copiado).
- Causa: desativar nao incrementa `auth_version`; `get_current_user` so checa `ativo`.
- Recomendacao: incrementar `auth_version` ao desativar (e ao mudar papel, por coerencia).
- Teste: desativar -> reativar -> token antigo 401.

### AUD6-S02-003 - Logins antigos dos paineis (P2)

- Evidencia: `auth.js` `mostrarLogin()` exibe `#login-panel` de cada painel quando nao ha
  sessao, no "Sair", na expiracao e em 401. Capturas (390 px): `/cliente` e `/produtor`
  usam um formulario sem "Esqueci minha senha", "Mostrar senha", "Criar conta" e "Voltar";
  `/admin` mostra "Acesso Restrito" com outro visual. `acesso.js`/`auth_next.js` so
  aceitam `next` para `/cliente`.
- Impacto: e o problema relatado pelo responsavel; tres experiencias de login, sem
  recuperacao de senha nos paineis, e retorno ao lugar errado depois de entrar.
- Recomendacao: paineis redirecionam para `/acesso?next=<rota atual>`; `next` validado por
  papel (`/admin`, `/produtor`, `/cliente`, mesmo dominio); remover os formularios antigos.
- Teste: cerca de 20 suites de navegador entram pelos formularios antigos (`#username` no
  painel) e precisam passar por `/acesso` ou semear a sessao.

### AUD6-S02-004 - Troca e recuperacao de senha (P2)

- Evidencia: a senha so e gravada em tres pontos: reset pelo Admin
  (`usuario_service.redefinir_senha`), ativacao de convite e redefinicao por e-mail
  (`client_access_service`). Nao ha rota de troca de senha para a propria conta. A recuperacao por e-mail so atende cliente
  ativado (`_eligible_recovery_account`); contas de produtor e admin nao tem e-mail. Em
  `/acesso`, "Esqueci minha senha" aparece para todos e a resposta e generica.
- Impacto: produtor ou admin que esquece a senha depende do Admin; ninguem consegue
  trocar uma senha comprometida sozinho.
- Recomendacao: `Seguranca e senha` no menu da conta (senha atual + nova, incrementa
  `auth_version`, auditoria). Na recuperacao, texto dizendo que produtores e equipe devem
  falar com o Admin. Avaliar e-mail para produtores (decisao).
- Teste: troca com senha atual errada, sucesso encerra outras sessoes.

### AUD6-S02-005 - Conta de cliente no Admin > Usuarios (P2)

- Evidencia: sondagem de navegador. Ao abrir uma conta de cliente, o seletor de papel
  (so "Produtor" e "Administrador") fica vazio e invalido; "Salvar" nao envia nada. O
  filtro de papel tambem nao tem "Cliente", embora clientes aparecam em "Todos".
- Impacto: o Admin nao consegue desativar o login de um cliente, nem definir seu nome de
  exibicao, por essa tela.
- Recomendacao: mostrar "Cliente" como papel somente leitura (troca de papel continua
  proibida para clientes) e incluir o filtro "Cliente". Link contextual para o cadastro do
  cliente (S09).
- Teste: abrir cliente, alterar nome de exibicao/status e salvar.

### AUD6-S02-006 - Maiusculas no login (P2)

- Evidencia: sondagem no CI: `Ana` e `ana` foram criados como contas distintas; `ANA`
  recebe 401 e `Ana` entra. Producao: os 4 logins de clientes tem maiusculas; nenhuma
  colisao ignorando maiusculas/espacos.
- Impacto: cliente precisa lembrar a grafia exata; logins parecidos geram confusao e risco
  de engano no suporte.
- Recomendacao: login sem diferenciar maiusculas e unicidade por `lower(username)`
  (migration com indice unico; dados atuais permitem). Manter a grafia exibida.
- Teste: login em qualquer caixa; cadastro rejeita variante de caixa.
- Dependencia: decisao + migration.

### AUD6-S02-007 - Sessao exposta a XSS e sem revogacao (P2, dep. S12)

- Evidencia: `_headers` publica `Content-Security-Policy-Report-Only` (nao aplicada); o
  token de 60 min fica em `localStorage`; "Sair" so apaga a chave local.
- Impacto: um XSS em qualquer pagina do dominio levaria sessoes validas ate expirarem, sem
  como encerra-las alem de reset de senha pelo Admin.
- Recomendacao: aplicar a CSP (apos revisar os relatorios) e oferecer "Sair de todos os
  dispositivos" (incrementa `auth_version`). Cookie HttpOnly fica como evolucao futura.

### AUD6-S02-008 a 015 (P3)

- **008 Enumeracao**: login de usuario inexistente responde em ~2,6 ms; senha errada de
  usuario existente em ~206 ms (bcrypt). Executar hash ficticio quando o usuario nao
  existir. (Confirma AUD-S02-001 da Etapa 03.)
- **009 Limite de login**: so por IP (10/min) e em SQLite local do processo, que zera a
  cada deploy/instancia. Usar `auth_rate_limits` (ja existe) com chave por IP e por login.
- **010 Admin**: campos fora de `<form>`, Enter nao envia; placeholder "admin" revela o
  login do administrador. Resolvido junto com 003.
- **011 Nome exibido**: barra lateral e saudacao dos portais usam `user.username`; usar
  `nome_exibicao` quando existir.
- **012 Campos da sessao**: `/auth/me` e o login devolvem `is_test`, `is_admin`,
  `painel_beats` e `cliente_id` ao proprio usuario. Responder so o necessario por papel.
- **013 Sessao existente**: `/acesso` com sessao valida mostra o formulario. Oferecer
  "Continuar como <nome>" ou redirecionar.
- **014 Textos**: "Privacidade" no rodape nao e link; o placeholder de senha `••••` parece
  campo preenchido; "Esqueci minha senha" tem peso de botao; apos ativar, o cliente precisa
  entrar de novo; "Solicite um novo envio" (link expirado) nao oferece o caminho.
- **015 Expiracao**: a sessao encerra sem aviso ao expirar e o painel volta ao login,
  podendo perder formularios longos (proposta, servico). Avisar antes e renovar em uso
  (decisao sobre duracao e refresh).

## 5. Corrigir, remover e simplificar

- Corrigir: 001, 002 (sem migration), 005, 010.
- Remover: formularios de login dos tres paineis (003); placeholder "admin".
- Simplificar: um unico ponto de entrada (`/acesso`) com `next` por papel.

## 6. Centralizar

- Menu da conta (Etapa 06, 5.1) no nome do canto: Meu perfil (nome de exibicao),
  Seguranca e senha (004), Sair, Sair de todos os dispositivos (007), Ajuda.
- Hoje cada portal tem apenas o username e um botao "Sair" na barra lateral.

## 7. Implementacoes candidatas

- Troca de senha autenticada; "Sair de todos os dispositivos".
- Login sem diferenciar maiusculas.
- Aviso de expiracao com renovacao.
- Login automatico apos ativacao do convite.

## 8. Tutoriais e ajuda contextual

- Primeiro acesso do cliente: da ativacao ao primeiro projeto (checklist curto).
- Recuperacao: explicar no proprio formulario quem pode recuperar por e-mail.

## 9. Linguagem

- "Acesso Restrito" / "ENTRAR NO SISTEMA" (Admin) -> deixam de existir com 003.
- Recuperacao: "Produtores e equipe Mirai: peca a redefinicao ao administrador."
- Link expirado: botao "Pedir novo link" quando houver fluxo de reenvio.

## 10. Links contextuais e opcoes ocultas

- Admin > Usuarios: conta de cliente -> cadastro do cliente (S09).
- "Sair de todos os dispositivos" so dentro de Seguranca, nao ao lado de "Sair".

## 11. Lacunas de teste

- Backend: renomear + recriar; desativar/reativar; login com outra caixa; troca de senha.
- Navegador: conta de cliente no modal de Usuarios; Enter no login; paineis redirecionando
  para `/acesso` com `next` por papel; `/acesso` com sessao existente.

## 12. Dependencias

- S07/S08: cabecalho dos portais e menu da conta.
- S09: Admin > Usuarios e pagina central do cliente.
- S11: e-mails de recuperacao e convite.
- S12: CSP, armazenamento do limitador, TTL dos tokens no Render.

## 13. Riscos residuais e criterios de validacao

- Ate corrigir 001, nao reutilizar um login de conta renomeada (orientacao operacional).
- Validar o setor quando: 001 e 002 corrigidos com regressao; 003 e 005 entregues e
  inspecionados em 390/1280 px; decisao registrada para 004, 006, 007 e 015; testes
  focados verdes no CI.

## Ordem sugerida de correcao

1. 001 + 002 (pequena, sem migration, alto ganho de seguranca).
2. 003 + 010 + 013 (entrada unica).
3. 005 + 011 (Admin e nome exibido).
4. 004 (troca de senha) e 008/009 (login).
5. 006 (migration) e 007/015 (decisoes com S12).

# Fase E - hardening de seguranca

Escopo: autenticacao, autorizacao simples, XSS/URLs, sessao, protecao contra abuso e validacoes. Fluxos A-D preservados. Nenhuma migration, banco real, e-mail real ou operacao de deploy foi executada nesta fase.

## Autenticacao e permissoes

JWT usa o mesmo algoritmo configurado na geracao e validacao. Access exige assinatura valida, exp, sub nao vazio, type=access e usuario existente no banco. A dependencia retorna UsuarioModel. Erros retornam 401 sem token/payload. Nao existe campo de usuario ativo: desativacao nao foi inventada. O helper de refresh exige type=refresh; nao ha endpoint de refresh, portanto nenhum fluxo novo foi criado.

| Recurso | Publico | Autenticado/comum ou produtor | Admin |
|---|---|---|---|
| Login, solicitar orcamento, newsletter | Sim, com rate limit | Sim | Sim |
| Ler servicos, portfolio e configuracoes da calculadora | Sim | Sim | Sim |
| /auth/me | Nao | Proprio usuario, sem senha/hash | Sim |
| Listar usuarios para selecionar produtor | Nao | Sim, resposta sem senha/hash | Sim |
| Orcamentos administrativos, propostas e producoes | Nao | Sim, regra operacional existente | Sim |
| Alterar configuracoes, servicos e portfolio | Nao | 403 | Sim |
| Criar usuario administrador | Nao ha rota HTTP | Nao | Script local interativo |

Admin exige is_admin=true E role=admin. Registros inconsistentes nao ganham privilegio por apenas um dos campos. Nao existem rotas de escrita de usuarios, logs ou newsletter administrativa neste estado. Nao foi criado RBAC por produtor/registro. Usuarios existentes devem ser classificados conscientemente: os defaults historicos de role/is_admin sao privilegiados e nao foram migrados.

## XSS, URLs e HTML

Helper central escapeHtml para interpolacoes, safeURL para links externos e serviceStructure para render defensivo. Corrigidos renderer de servicos, cards publicos, portfolio, builder e link de guia do orcamento. O editor de propostas reutiliza o escape central. Conteudo de API e usuario vira texto, inclusive aspas em atributos. O accordion publico usa listener delegado em vez de onclick interpolado.

URLs externas aceitam somente HTTP/HTTPS absolutas, sem credenciais embutidas, whitespace ou controles. javascript:, data:, file: e vbscript: sao recusados. Caminhos estaticos internos e Blob URLs criadas pelo proprio fluxo de PDF sao excecoes controladas, nao entradas externas. mailto/tel nao sao necessarios nos sinks alterados.

HTML dos componentes locais e template de documento permanecem recursos internos, nao HTML livre editavel. Campos da proposta sao escapados pelo template; preview usa iframe sandbox. Nenhum sanitizer caseiro de HTML rico foi introduzido. Service JSON invalido tem fallback controlado; itens malformados na lista administrativa sao filtrados.

## Sessao

Login e restauracao usam initializeAdmin ja existente. Reload valida /auth/me antes de carregar dados. Login utiliza a resposta autenticada de /auth/login. Inicializacao por token continua protegida contra repeticao.

Logout remove access/refresh do localStorage, invalida requisicoes em andamento, limpa listas/estado/builder/formularios, fecha modais/editor e libera preview/Blob. authFetch verifica a geracao da sessao tanto nos headers quanto apos ler o corpo. Respostas antigas nao repovoam dados nem encerram um novo login. 401 concorrentes causam apenas um logout; sem token, nao ha nova requisicao. Expiracao agenda limpeza local; eventos de storage sincronizam mudancas entre abas.

## Limites e anti-duplicacao

| POST | Limite por IP e rota |
|---|---|
| /auth/login | 10 por 60 segundos |
| /orcamentos | 5 por 600 segundos |
| /newsletter | 5 por 600 segundos |

Janela fixa, resposta 429 com Retry-After. GET/health e demais rotas nao consomem esses limites. SQLite separado do banco da aplicacao, transacao BEGIN IMMEDIATE e conexoes fechadas explicitamente compartilham contadores entre processos no mesmo host. Caminho: RATE_LIMIT_DB ou arquivo mirai-rate-limits.sqlite3 no diretorio temporario. Chaves sao hashes de rota/IP, expurgadas apos uma hora, com teto de 100 mil entradas. Falha/capacidade indisponivel: 503, sem bypass silencioso ou detalhes da conexao.

Limitacao: nao e distribuido entre instancias e armazenamento temporario pode ser perdido. Antes de escalar, usar limitador compartilhado/edge e verificar bypass de acesso direto ao backend. O codigo usa request.client, sem confiar diretamente em X-Forwarded-For. Configuracao do proxy ASGI deve aceitar forwarding somente de proxies confiaveis; isso precisa ser confirmado no ambiente hospedado, que nao foi acessado. Usuarios atras de NAT dividem a cota. Janelas fixas permitem rajadas nas bordas.

Formulario publico bloqueia double-submit e listeners repetidos. Newsletter duplicada retorna o cadastro existente, sem novo e-mail, inclusive apos conflito de unicidade. Orcamento nao ganhou chave duravel de idempotencia: chamadas de clientes externos ainda podem repetir dentro da cota.

## Validacoes

- Orcamento: nome/servico nao vazios, limites 120/100, email valido ate 150, whatsapp ate 30, detalhes ate 20000, link HTTP/HTTPS ate 500, total finito e nao negativo. Total continua obrigatorio, preservando contrato existente. Observacoes administrativas ate 20000; produtor deve existir.
- Configuracoes: desconto continua canonico, numeros finitos. Negativos e maiores que 100 nao foram proibidos sem regra comercial; pendencia documentada.
- Propostas: preservados server-owned/extra forbid/status readonly no PATCH, quantidades positivas e valores finitos; limites de descricao, condicoes, itens e pagamentos; URLs HTTP/HTTPS. Backend continua autoridade de totais e transicoes.
- Servicos: estrutura_servico continua string JSON. Raiz objeto com intro, sections e benefits. Secao exige title e items, icon opcional; tipos estritos e campos desconhecidos recusados. Ate 30 secoes, 100 itens por secao, 100 beneficios; textos e JSON limitados. Parametros seguem as chaves reais da calculadora. ServicoUpdate herda a mesma validacao de escrita. Leituras legadas nao foram migradas.
- Newsletter: email valido ate 150 e campos extras recusados. Portfolio: textos limitados e URLs validadas.
- Senhas: login preserva minimo historico de 1, maximo 72 bytes UTF-8; script de criacao exige ao menos 8 caracteres. Hash/verificacao rejeitam excesso antes do bcrypt. create_admin usa getpass com confirmacao, sem --password ou alternativa nao interativa. Erros de argumentos nao refletem valores.

## Headers, CSP, CORS e erros

Backend: X-Content-Type-Options=nosniff, Referrer-Policy=strict-origin-when-cross-origin, Permissions-Policy desabilitando camera/microfone/geolocalizacao e X-Frame-Options=DENY. HSTS de um ano somente quando a requisicao e HTTPS; o reconhecimento de HTTPS depende de proxy confiavel. Sem mudanca de startup/schema.

frontend/_headers declara headers equivalentes e CSP Report-Only para hospedagem que interprete esse arquivo. Nao e aplicado por servidores estaticos genericos. Nenhum deploy foi realizado para confirmar headers na borda.

CSP nao esta em enforcement. Restam handlers inline em admin.html, estilos inline e recursos externos; script-src self gerara diagnosticos para usos incompatíveis. connect-src https e amplo em report-only. Nao ha coletor report-uri. Antes de enforcement, inventariar origens exatas e migrar handlers restantes. Nao se deve considerar CSP report-only uma barreira contra XSS.

CORS usa ALLOWED_ORIGINS explicitamente, rejeita wildcard/origens com caminhos, deduplica entradas e restringe metodos/headers. Credenciais de cookie desabilitadas; Authorization permitido. Dominio oficial, Pages e localhost precisam constar como origens exatas na configuracao de cada ambiente; nao foi lida configuracao real. Testados origin permitido e proibido.

Erros de validacao devolvem local/tipo e mensagem generica, sem input original (evita refletir senha). Erros SQLAlchemy devolvem 503 generico. Os erros comerciais seguros das Fases A-D foram preservados, assim como email_send_failed. Nao ha exposicao de trace em respostas de erro genericas do FastAPI com debug desativado.

## Testes locais

Dependencias de teste: backend/requirements-test.txt inclui httpx. SQLite descartavel, configuracao sintetica e mocks de envio; requests HTTP de seguranca usam transporte ASGI sem rede. Testes frontend interceptam todas as URLs.

```powershell
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -p test_security_phase_e.py -v
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -p 'test_proposta*.py' -v
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -p test_public_admin_contracts.py -v
node frontend/tests/security.cjs
node frontend/tests/flows.cjs
node frontend/tests/proposta_contracts.mjs
node frontend/tests/proposta_editor.cjs
node frontend/tests/proposta_documento.cjs
node frontend/tests/proposta_comercial.cjs
```

Os testes de navegador requerem Playwright e Edge (ou BROWSER_CHANNEL configurado). NODE_PATH pode apontar para a instalacao local do Playwright. O teste backend de documento emite fixtures temporarias para o teste frontend de PDF.

Resultado: 3 testes agrupados de seguranca, 18 testes de propostas A-D e 1 roundtrip publico/admin aprovados. Seis suites JavaScript aprovadas. Cobertura inclui JWT valido/expirado/assinatura/tipo/sub/usuario inexistente, 401/403/admin, desconto 0/-1/101, produtor invalido, newsletter duplicada, senhas UTF-8, excesso de requisicoes, CORS/headers, XSS e corrida de logout. Regressao: login/reload sem duplicidade, orcamento publico, configuracoes, salvar proposta, foco, snapshot, PDF, QR, envio, aprovacao e producao idempotente. Sem regressao detectada nesses cenarios.

Verificacao estatica adicional: sintaxe de 71 ES modules, resolucao de 170 imports relativos e sintaxe de 34 arquivos Python locais aprovada, sem importar a aplicacao nessa verificacao.

## Riscos residuais e proxima fase

JWT permanece em localStorage: JavaScript comprometido ainda pode le-lo; logout nao revoga token ja copiado. Migracao futura para cookie HttpOnly requer projeto de CSRF, SameSite/Secure, CORS com credenciais e dominios frontend/backend (Pages/Cloudflare e Render). Nao foi implementada.

Pendencias: rate limit distribuido e verificacao de IP/proxy no ambiente real; CSP enforcement; revisao manual de privilegios legados; politica de desativacao/revogacao e propriedade por produtor; limites comerciais de desconto; idempotencia duravel de orcamento. PostgreSQL e infraestrutura de producao nao foram exercitados. Nenhuma dessas pendencias foi convertida em nova funcionalidade, e a Fase F nao foi iniciada.

## Arquivos da Fase E

Criados: backend/core/http_security.py, backend/core/rate_limit.py, backend/schemas/validation.py, backend/schemas/servico_estrutura.py, backend/requirements-test.txt, backend/tests/test_security_phase_e.py, frontend/_headers, frontend/js/utils/security.js, frontend/tests/security.cjs e este documento.

Alterados no backend: core/dependencies.py, core/security.py, main.py; routers/auth.py, config.py, newsletter.py, orcamentos.py, projetos.py, servicos.py; schemas/newsletter.py, orcamento.py, projeto.py, proposta.py, servico.py, usuario.py; scripts/create_admin.py.

Alterados no frontend: js/admin/auth.js, index.js, configuracoes.js, projetos.js; admin/builder/builder.js, builder_dom.js, builder_preview.js; admin/orcamentos/orcamentos_modal.js; admin/producoes/producoes_modal.js; admin/propostas/proposta_utils.js; admin/servicos/servicos.js, servicos_api.js; js/modules/orcamento.js, service_renderer.js; js/portfolio_ui.js, ui.js; tests/flows.cjs.

Outros arquivos locais das Fases A-D sao preexistentes a este hardening e nao devem ser confundidos com mudancas de seguranca. O listener de logout do controller de propostas ja integra esse conjunto local e foi preservado/testado.

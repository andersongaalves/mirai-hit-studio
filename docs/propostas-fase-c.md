# Propostas: Fase C

## Arquivos desta execucao

Criados:
- `backend/services/qr_code_service.py`
- `backend/services/pdf_service.py`
- `backend/services/documento_storage.py`
- `backend/services/proposta_documento_service.py`
- `backend/templates/proposta.html`
- `backend/tests/test_proposta_documento.py`
- `frontend/tests/proposta_documento.cjs`
- `docs/propostas-fase-c.md`

Alterados, preservando o trabalho local anterior:
- `backend/requirements.txt`
- `backend/routers/propostas.py`
- `backend/tests/test_proposta_router.py` (expectativa de existencia do novo endpoint)
- `frontend/css/pages/admin.css` (preview antigo removido; contencao do editor)
- `frontend/js/admin/propostas/proposta_api.js`
- `frontend/js/admin/propostas/proposta_state.js`
- `frontend/js/admin/propostas/proposta_preview.js`
- `frontend/js/admin/propostas/propostas.js`
- `frontend/tests/proposta_editor.cjs` (expectativas da Fase C)

Outros arquivos mostrados pelo Git ja estavam alterados antes desta fase.

## Fluxo e responsabilidades

- `backend/templates/proposta.html`: unica fonte visual, com autoescape Jinja. Logo PB existente, numero/versao/data, snapshot do cliente, produtor, objeto/descricao, itens, valores, condicoes, pagamentos habilitados, aceite e rodape.
- `services/qr_code_service.py`: valida HTTP(S), sem credenciais ou espacos, e produz PNG em memoria. Nao acessa o link, nao grava imagens e nao aceita outros protocolos. Links excedendo a capacidade do QR falham explicitamente.
- `services/pdf_service.py`: prepara valores Decimal pelo calculo existente, renderiza o template e converte esse mesmo HTML em PDF. Recursos externos/arquivos arbitrarios sao bloqueados; logo e QR sao PNGs embutidos.
- `services/documento_storage.py`: adaptador local explicitamente configurado, chaves opacas e validacao de caminho. Sem diretorio publico ou URL permanente.
- `services/proposta_documento_service.py`: coordena leitura, validacao, renderizacao, armazenamento e persistencia. Usa o mesmo bloqueio de linha do PATCH no PostgreSQL.
- `routers/propostas.py`: mantem a dependencia autenticada existente. Nenhuma alteracao de autenticacao.
- Frontend: helper HTTP existente, estado `gerando`, preview em iframe sandbox sem scripts, links de visualizar/baixar somente para bytes PDF efetivamente retornados pelo backend.

## Endpoints

- `GET /propostas/{id}/preview`: HTML da versao salva, sem gravar arquivo ou mudar dados. Pode funcionar antes do primeiro PDF.
- `POST /propostas/{id}/gerar-documento`: sem payload de valores. Le a proposta persistida, valida snapshot/numero/itens/pagamentos, recalcula valores, gera e armazena PDF, registra `pdf_path` e `gerada_em`; retorna `PropostaResponse`.
- `GET /propostas/{id}/documento`: retorna bytes `application/pdf` da referencia atual, autenticado e com `Cache-Control: no-store`. Sem referencia atual, retorna 404.

Numero, snapshot, versao, status e orcamento nao sao alterados pela geracao. Os dados do cliente nunca sao reconstruidos do orcamento atual. O nome do produtor vem do cadastro relacionado, pois nao existe snapshot do produtor neste contrato.

O PATCH da Fase A ja invalida `pdf_path` e `gerada_em` em alteracoes efetivas e incrementa a versao. Essa regra foi preservada; PATCH sem mudanca efetiva conserva o documento. Gerar novamente nao incrementa a versao.

Erros de validacao retornam 422; dados persistidos inconsistentes continuam usando o 409 do contrato existente. Falhas de template/conversao/storage retornam 503 com mensagem controlada, sem stack trace. Nenhum status de envio/aceite e alterado.

## Editor

Gerar PDF exige proposta carregada, sem dirty, salvamento ou geracao em andamento. A mensagem com dirty e: "Salve as alteracoes antes de gerar o PDF." A interface apresenta a versao acentuada dessa mensagem.

Ao concluir, o controller usa a resposta real, abre Preview e disponibiliza visualizar/baixar. Erros preservam o estado. Contexto de abertura impede que geracoes atrasadas substituam outra proposta; preview atrasado tambem e descartado quando sua aba foi desmontada. URLs Blob representam o PDF real baixado e sao revogadas ao sair/trocar de preview.

O HTML mostra apenas dados salvos, mesmo quando ha edicoes locais; nesse caso aparece o aviso e nenhum download de documento antigo e oferecido. QR ausente recebe aviso textual apenas no editor. Pagamentos desabilitados nao aparecem no documento.

Prazo, validade e observacoes nao possuem campos persistidos no contrato atual. Devem ser informados em `condicoes`/`descricao`; nenhum valor foi inventado e nenhum schema/model foi alterado. Objeto permanece opcional conforme contrato atual. Geracao exige ao menos um item com descricao preenchida.

## Dependencias e Render

Escolha: `xhtml2pdf==0.2.18` (ReportLab) e `qrcode[pil]==8.2`. Instalacao e conversao real verificadas com Python 3.13 no Windows, sem Pango, navegador ou binario de conversao externo. `requirements.txt` foi convertido de UTF-16 para UTF-8 sem alterar as versoes anteriores.

[WeasyPrint](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html) exige Pango e bibliotecas nativas; elas nao estavam instaladas neste Windows e nao sao garantidas na lista do [runtime nativo do Render](https://render.com/docs/native-runtimes). [xhtml2pdf 0.2.18](https://xhtml2pdf.readthedocs.io/en/latest/release-notes.html) suporta CPython 3.10 a 3.14. Para este template PNG/Helvetica, nao foi necessario instalar bibliotecas de sistema. As dependencias transitivas devem continuar sendo verificadas no build Linux; nao foi feito deploy nem teste dentro do Render.

xhtml2pdf possui suporte CSS menor que um navegador. O template usa fluxo simples e tabelas, nao flex/grid para o documento. O HTML preserva a largura util A4; em telas estreitas, a rolagem fica dentro do iframe para nao esmagar as colunas monetarias. Preview HTML e PDF compartilham conteudo/template, mas o preview e continuo e o PDF tem paginacao A4. A visualizacao do PDF real e a referencia exata para impressao.

O logo e lido de `frontend/assets/logo_mirai_BnW.png` relativo ao repositorio. O pacote de deploy precisa conter esse asset junto com `backend/templates/proposta.html`; um pacote contendo somente a pasta backend precisa incluir o asset por uma estrategia de empacotamento definida antes do deploy.

## Armazenamento

Definir `PROPOSTA_PDF_DIR` no ambiente do processo como caminho absoluto para um diretorio privado e persistente. Sem essa configuracao a geracao falha explicitamente. Nao ha fallback silencioso para disco temporario.

Exemplo somente para desenvolvimento no PowerShell, antes de iniciar o backend local:

```powershell
$env:PROPOSTA_PDF_DIR = Join-Path $env:TEMP 'mirai-propostas-local'
```

Esse exemplo e descartavel, NAO e configuracao de producao. O [filesystem do Render e efemero por padrao](https://render.com/docs/disks). Producao precisa de disco persistente montado (configurar a variavel para esse mount) ou outro adaptador de storage privado, por exemplo object storage. Nenhuma configuracao de producao foi alterada.

Cada geracao escreve uma chave unica; grava arquivo temporario, sincroniza e renomeia antes do commit no banco. Falha no commit pode deixar arquivo orfao, mas nao registra referencia parcial. Nao existe transacao atomica entre filesystem e PostgreSQL. Em caso de interrupcao, consultar a proposta: se nao ha referencia atual, gerar novamente. Nao apagar arquivos automaticamente; conciliacao/retencao e remocao de orfaos ficam pendentes. PDFs antigos invalidados nao sao servidos pelo endpoint atual, mas permanecem no storage ate uma politica de retencao ser implementada.

## Testes locais

Nenhum banco real, e-mail, pagamento ou rede externa e utilizado. Os testes backend reutilizam a fixture SQLite descartavel existente; nao revalidam fases de infraestrutura anteriores.

Na raiz do repositorio:

```powershell
$env:PROPOSTA_TEST_OUTPUT = Join-Path $env:TEMP 'mirai-phase-c-layout'
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -p test_proposta_documento.py -v
node frontend/tests/proposta_contracts.mjs
node frontend/tests/proposta_editor.cjs
node frontend/tests/proposta_documento.cjs
```

Os testes de navegador precisam de Playwright resolvivel pelo Node e Edge instalado, ou `BROWSER_CHANNEL` compativel. O teste de documento consome os HTMLs/PDFs reais emitidos pelo teste Python no diretorio de teste. Nao sao blobs simulando PDFs. Screenshots desktop/mobile tambem ficam nesse diretorio temporario.

Cobertura backend: URLs/PNG, bloqueio de recursos, validacao, escape, moeda Decimal, snapshot, parcial 2, conversao real, leitura, referencia/data persistidas, erros, rollback, invalidacao e endpoints. Layout: 1/2/3 pagamentos, 1/24 itens, nome/descricao/condicoes extensos e valores milionarios. QR extraidos do PDF foram decodificados com `zxing-cpp==2.3.0`, ferramenta apenas local de verificacao, nao dependencia de producao.

Cobertura frontend: contrato/estado, regressoes da Fase B, preview real, sandbox, dirty, gerar/salvar, double-submit, download/visualizacao, falhas, resposta inesperada, descarte de respostas tardias e invalidacao apos edicao. Viewport mobile inclui verificacao de ausencia de overflow horizontal.

Resultado da execucao local: 5 testes Python de documento e 5 de persistencia aprovados; 3 suites JavaScript aprovadas; sintaxe/imports relativos dos 14 ES modules e compilacao dos arquivos Python novos/alterados aprovados. Documentos de layout com 1, 2 e 14 paginas, nenhum caractere fora das paginas; paginas renderizadas inspecionadas, incluindo tabela em continuacao e aceite/rodape. Os tres QR foram decodificados tanto dos PNGs incorporados quanto das paginas PDF rasterizadas. `git diff --check` sem erros. Render nao foi executado.

## Limites e proxima fase

- Sem deploy: compatibilidade efetiva com o pacote/runtime Linux e storage persistente deve ser verificada antes de producao.
- Geracao sincrona segura uma linha bloqueada ate concluir; documentos muito extensos podem atingir timeout do servidor. Fila/limites operacionais nao foram implementados nesta fase.
- Fontes PDF padrao atendem texto portugues; alfabetos adicionais/emoji exigem fontes incorporadas e novos testes.
- Snapshot do produtor, campos proprios de prazo/validade, retencao e object storage nao foram introduzidos.
- Fase D (nao iniciada): envio, registro de envio e regras de status/aprovacao, mediante autorizacao. Sem e-mail, aprovacao, producao, pagamento real, commit, push ou deploy nesta fase.

# Banco de dados

Execute os comandos abaixo dentro de `backend/`, com o venv ativo e a
configuracao do ambiente preparada. Nunca coloque credenciais nos comandos.
O FastAPI nao cria tabelas; seu startup apenas inicializa dados em tabelas existentes.

## Banco existente

**Nao use bootstrap.** Para um banco ja gerenciado pelo historico atual:

```sh
alembic upgrade head
```

Se o schema existe sem uma revision confiavel, pare e confira sua origem.
O bootstrap nao repara esse caso e nao deve ser usado para registrar sua revision.

## Banco novo e completamente vazio

```sh
python -m scripts.bootstrap_database
alembic upgrade head
```

O bootstrap e manual e one-time. Ele descobre a unica head em `alembic.ini`,
cria o schema atual dos models e registra essa revision usando a API do Alembic,
na mesma conexao/transacao. Nao executa migrations antigas. O upgrade seguinte
deve ser um no-op; upgrades futuros continuam sendo responsabilidade do Alembic.
Use models e migrations da mesma versao do projeto, sem mudancas de schema
ainda nao representadas por migrations.

O script recusa qualquer objeto de relacao de usuario (tabelas, views, sequencias,
indices etc.) e tipos definidos pelo usuario no PostgreSQL, em todos os schemas
nao internos. Exige `public` como schema ativo. Mesmo uma `alembic_version`
vazia provoca recusa. Catalogos PostgreSQL e objetos internos `sqlite_*` nao
contam como tabelas da aplicacao; bancos SQLite anexados sao recusados.

Um projeto Supabase pode nascer com tabelas `auth`/`storage` e outros objetos.
Nesse caso este bootstrap conservador **aborta**, mesmo com `public` vazio.
Nao ha excecao automatica, `--force`, limpeza ou reparo. Um procedimento futuro
restrito ao schema da aplicacao precisara de analise propria; nao contorne a recusa.

## Falhas e operacao

Pare aplicacao, workers, migrations e outros escritores durante o bootstrap.
O bloqueio transacional PostgreSQL coordena apenas outras execucoes deste script;
nao bloqueia administradores ou ferramentas que ignorem esse bloqueio.
SQLite usa `BEGIN IMMEDIATE`, inclusive para tornar o DDL transacional.

Criacao e registro da revision compartilham uma transacao. Em falha, o comando
termina com codigo diferente de zero e tenta rollback pela conexao, sem imprimir
credenciais nem executar DROP/TRUNCATE. Nao faz limpeza automatica.

Depois de interrupcao ou perda de conexao no commit, inspecione o banco em modo
somente leitura: se estiver realmente vazio, o comando pode ser repetido; se
schema completo e revision estiverem confirmados, nao repita; se houver estado
parcial ou duvida, interrompa o procedimento e investigue. Nao registre uma
revision manualmente nem apague objetos para forcar o bootstrap.

O historico antigo permanece intacto: sua primeira revision pressupoe tabelas
anteriores. Por isso `alembic upgrade head` isoladamente nao prepara banco vazio.
O bootstrap cria apenas schema, nao usuarios, configuracoes ou dados de backup.

## Testes descartaveis

```sh
python -B -m unittest discover -s tests -p test_bootstrap_database.py -v
```

Os testes usam configuracao sintetica e arquivos SQLite temporarios, sem ler
`.env` nem conectar ao PostgreSQL/Supabase real. Validacao em PostgreSQL
descartavel ainda e necessaria antes do uso operacional nesse mecanismo.

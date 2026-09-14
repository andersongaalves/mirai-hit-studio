# Mirai Hit Studio - Backup e Restore

## Escopo

Backup do banco e operacao de infraestrutura. Nao existe endpoint ou botao de restore no Admin. Os scripts usam `pg_dump` e `pg_restore` oficiais, sem imprimir `DATABASE_URL` ou credenciais.

Um dump do PostgreSQL nao inclui PDFs, uploads ou object storage. Esses arquivos precisam de politica propria no provedor de storage.

## Pre-requisitos

- PostgreSQL client compativel com a versao do servidor (`pg_dump` e `pg_restore` no `PATH`).
- `DATABASE_URL` definida somente no ambiente de execucao.
- Diretorio de destino existente, privado e fora do repositorio/public web.
- Espaco suficiente e acesso restrito: o dump pode conter todos os dados pessoais do sistema.

## Backup

A partir de `backend/`:

```powershell
python -m scripts.backup_database --output-dir D:\backups\mirai
```

O arquivo e criado em formato custom como `mirai_YYYY-MM-DD_HHMMSS.dump`. O script aborta se o nome ja existir, se o diretorio for invalido, se a ferramenta faltar ou se o dump ficar vazio.

O filesystem do Render pode ser efemero. Copie o resultado para storage externo privado e duravel; um arquivo deixado apenas na instancia nao deve ser considerado backup valido.

## Restore descartavel ou staging

Restore usa `--clean --if-exists` e pode remover objetos do banco de destino. Confirme primeiro que `DATABASE_URL` aponta para um banco descartavel ou staging.

```powershell
$env:APP_ENV = "test"
python -m scripts.restore_database --backup D:\backups\mirai\mirai_YYYY-MM-DD_HHMMSS.dump --confirm-restore RESTORE
```

Depois valide:

```powershell
alembic current
alembic heads
```

Confira dados essenciais e garanta que `alembic_version` corresponde a uma revision conhecida. O script nao executa migrations automaticamente.

## Producao

Restore de producao exige procedimento deliberado, janela de manutencao, backup anterior verificado e duas confirmacoes explicitas:

```powershell
$env:APP_ENV = "production"
python -m scripts.restore_database --backup D:\backups\mirai\backup-validado.dump --confirm-restore RESTORE_PRODUCTION --allow-production
```

Antes de executar:

1. interrompa escritas da aplicacao;
2. confirme destino e arquivo com uma segunda pessoa;
3. preserve um backup anterior;
4. valide o restore primeiro em ambiente descartavel;
5. registre horario, responsavel e resultado fora do dump.

Se qualquer checagem falhar, aborte. Nao tente reparar automaticamente um restore parcial; preserve evidencias, mantenha a aplicacao sem escrita e decida entre repetir a partir de um banco limpo ou restaurar o backup anterior.

## Frequencia e verificacao

- Preferir backups gerenciados pelo provedor quando disponiveis.
- Gerar dump operacional antes de migrations ou releases de risco.
- Executar restore drill periodico em banco descartavel.
- Verificar retencao, criptografia e acesso no storage externo.

Backup existente sem restore testado possui valor limitado. Banco e object storage devem ter rotinas independentes.

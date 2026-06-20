# 🎵 Mirai Hit Studio

> Plataforma Full Stack para gerenciamento de produção musical, portfólio e orçamentos.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-00D4FF)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6-F7DF1E?logo=javascript)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📖 Sobre o Projeto

A **Mirai Hit Studio Platform** é uma aplicação Full Stack desenvolvida para automatizar o gerenciamento de um estúdio de produção musical.

O sistema permite que clientes solicitem orçamentos através de uma calculadora dinâmica enquanto o administrador gerencia serviços, portfólio, configurações e propostas através de um painel administrativo protegido por autenticação JWT.

---

## ✨ Funcionalidades

### 🌐 Frontend

- Landing Page
- Portfólio dinâmico
- Calculadora inteligente de serviços
- Atualização de preço em tempo real
- Solicitação de orçamento
- Componentes reutilizáveis
- Interface responsiva
- Tema Cyberpunk

### 🔐 Painel Administrativo

- Login com JWT
- CRUD de Serviços
- CRUD de Portfólio
- Gerenciamento de Orçamentos
- Configurações da Calculadora
- Dashboard Administrativo

### ⚙️ Backend

- API REST com FastAPI
- SQLAlchemy ORM
- Pydantic Schemas
- JWT Authentication
- CRUD modular
- SQLite Database
- Arquitetura organizada por camadas

---

# 📂 Estrutura do Projeto

```
mirai_hit_studios/

├── backend/
│
│   ├── alembic/
│   ├── core/
│   ├── crud/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   ├── scripts/
│   ├── services/
│   ├── tests/
│   ├── utils/
│   │
│   ├── database.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
│
├── front/
│
│   ├── components/
│   ├── css/
│   ├── fonts/
│   ├── img/
│   ├── js/
│   │
│   ├── admin.html
│   ├── calculadora.html
│   ├── index.html
│   └── portfolio.html
│
├── .gitignore
├── LICENSE
└── README.md
```

---

# 🚀 Tecnologias

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- Alembic
- JWT
- Bcrypt
- SQLite

## Frontend

- HTML5
- CSS3
- JavaScript (ES6 Modules)

---

# ⚡ Instalação

## 1 - Clone o projeto

```bash
git clone https://github.com/seu-usuario/mirai-hit-studio.git

cd mirai-hit-studio
```

---

## 2 - Backend

Entre na pasta

```bash
cd backend
```

Crie um ambiente virtual

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux

```bash
source venv/bin/activate
```

Instale as dependências

```bash
pip install -r requirements.txt
```

---

## 3 - Configuração

Crie um arquivo

```
.env
```

baseado em

```
.env.example
```

Exemplo:

```env
SECRET_KEY=your_secret_key_here

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=60

DATABASE_URL=sqlite:///mirai.db
```

---

## 4 - Executar API

```bash
uvicorn main:app --reload
```

API disponível em

```
http://localhost:8000
```

Swagger

```
http://localhost:8000/docs
```

---

## 5 - Frontend

Abra a pasta

```
front/
```

e execute utilizando uma extensão como

```
Live Server
```

ou qualquer servidor HTTP estático.

---

# 🔒 Autenticação

O painel administrativo utiliza autenticação JWT.

Fluxo:

```
Login

↓

JWT Token

↓

LocalStorage

↓

Authorization Bearer

↓

Rotas Protegidas
```

---

# 🎯 Funcionalidades Implementadas

- [x] Login Administrativo
- [x] Autenticação JWT
- [x] CRUD de Serviços
- [x] CRUD de Portfólio
- [x] CRUD de Orçamentos
- [x] Configurações Dinâmicas
- [x] Calculadora Inteligente
- [x] Portfólio Dinâmico
- [x] Dashboard Administrativo
- [x] API REST

---

# 🚧 Próximas Funcionalidades

- Upload de imagens
- Upload de áudio
- Dashboard com estatísticas
- Sistema de propostas PDF
- Área do cliente
- Integração Mercado Pago
- Integração WhatsApp
- Sistema de notificações
- Analytics
- Docker

---

# 📸 Screenshots

### Landing Page

```
/docs/images/home.png
```

### Calculadora

```
/docs/images/calculadora.png
```

### Painel Administrativo

```
/docs/images/admin.png
```

---

# 👨‍💻 Arquitetura

```
Cliente

↓

Frontend HTML/CSS/JS

↓

API FastAPI

↓

JWT Authentication

↓

SQLAlchemy

↓

SQLite Database
```

---

# 💡 Objetivo

Este projeto foi desenvolvido para demonstrar conhecimentos em:

- Desenvolvimento Full Stack
- Arquitetura de APIs
- FastAPI
- JavaScript Modular
- Autenticação JWT
- CRUD Completo
- Organização de Projetos
- Integração Frontend/Backend

---

# 📄 Licença

Este projeto está sob a licença MIT.

---

# 🎵 Mirai Hit Studio

Produção Musical • Mixagem • Masterização • Sound Design

**Transformando ideias em experiências sonoras.**
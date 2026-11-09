# 🦁 Leãozito - Assistente Inteligente de Auditoria IRPF

![Badge Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Badge FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Badge Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![Badge SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)

O **Leãozito** é um sistema automatizado ponta a ponta projetado para facilitar a organização, auditoria e armazenamento de despesas dedutíveis para o Imposto de Renda Pessoa Física (IRPF). 

Utilizando um bot do Telegram como interface de entrada e a inteligência artificial do **Google Gemini** para extração de dados de notas fiscais (fotos e PDFs), o sistema compila tudo em um banco de dados local e exibe as informações num Dashboard Web responsivo e seguro.

---

## ✨ Funcionalidades Principais

* 🤖 **Leitura Inteligente (OCR + IA):** Envie fotos ou PDFs de recibos médicos, escolares, etc., e o Gemini extrai automaticamente o Emissor, CNPJ/CPF, Data, Categoria e Valor.
* 🔒 **Autenticação via Magic Link:** Sem necessidade de senhas no front-end. O bot gera um link temporário e criptografado (`/painel`) vinculando a sessão web diretamente ao `chat_id` do usuário.
* 🛡️ **Sistema de Whitelist:** O bot responde apenas a usuários cadastrados mediante uma senha de convite configurada pelo administrador (`/registrar`).
* 📊 **Dashboard "Liquid Glass":** Interface web minimalista com suporte nativo a *Dark Mode* e *Light Mode*, gráficos interativos (Evolução Mensal e Categorias) e design responsivo.
* 📥 **Exportação de Dados:** Geração de planilhas Excel (`.xlsx`), arquivos CSV e relatórios textuais formatados diretamente pelo painel web.
* 📚 **Guia Interativo IRPF:** Módulo de consulta integrado ao painel e ao bot sobre o que é ou não dedutível segundo a Receita Federal.

---

## 🛠️ Arquitetura e Tecnologias

* **Back-end:** Python 3.10+, FastAPI, Uvicorn, SQLite3.
* **Integrações:** API do Telegram (via Webhooks), Google Generative AI (Gemini 1.5 Flash).
* **Front-end:** HTML5, CSS3 moderno (Variáveis CSS, CSS Grid, Glassmorphism) e JavaScript (Vanilla ES6+). Sem dependências pesadas de frameworks externos.
* **Segurança:** `python-dotenv` para gerenciamento de variáveis de ambiente.

---

## 🚀 Como Executar o Projeto Localmente

### 1. Pré-requisitos
* Python 3 instalado na máquina.
* Uma chave de API do [Google AI Studio](https://aistudio.google.com/).
* Um Token de Bot criado via [@BotFather](https://t.me/BotFather) no Telegram.
* [Ngrok](https://ngrok.com/) (para expor o localhost e configurar o Webhook do Telegram).

### 2. Instalação

Clone este repositório e acesse a pasta do projeto:
```bash
git clone https://github.com/seu-usuario/leaozito.git
cd leaozito
```

Crie um ambiente virtual e instale as dependências:
```bash
python -m venv venv
# Ative o ambiente virtual (Windows)
venv\Scripts\activate
# Ative o ambiente virtual (Linux/Mac)
source venv/bin/activate

pip install fastapi uvicorn requests google-generativeai python-dotenv openpyxl
```

### 3. Configuração do `.env`
Na raiz do projeto, crie um arquivo chamado `.env` e preencha com as suas credenciais:
```env
TOKEN_TELEGRAM=seu_token_do_telegram_aqui
CHAVE_GEMINI=sua_chave_do_google_aqui
SENHA_CADASTRO=senha_para_novos_usuarios
```

### 4. Executando o Servidor
Inicie o back-end via Uvicorn:
```bash
python -m uvicorn main:app --reload
```
O servidor estará rodando em `http://127.0.0.1:8000`.

### 5. Configurando o Webhook
Em uma nova janela de terminal, inicie o Ngrok na porta 8000:
```bash
ngrok http 8000
```
Copie a URL HTTPS gerada pelo Ngrok e configure o Webhook do Telegram fazendo uma requisição no navegador:
```text
https://api.telegram.org/bot<SEU_TOKEN_TELEGRAM>/setWebhook?url=<URL_DO_NGROK>/webhook
```

---

## 📱 Comandos do Bot (Telegram)

* `/start` - Inicia o bot e apresenta o Leãozito.
* `/registrar <senha>` - Libera o acesso ao sistema para o seu usuário.
* `/painel` - Gera o seu **Magic Link** seguro para acessar o Dashboard Web.
* `/relatorio` - Exibe um extrato rápido via chat.
* `/exportar` - Envia o arquivo `.xlsx` com todas as notas salvas no chat.
* `/dicas` - Abre o menu interativo com as regras da Receita Federal.
* `/limpar` - Apaga todo o seu histórico do banco de dados (Ação irreversível).

---

## 📸 Screenshots


---

**Desenvolvido com ☕ e 🐍.**
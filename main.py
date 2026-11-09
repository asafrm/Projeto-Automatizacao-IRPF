from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import requests
import google.generativeai as genai
import json
import database
import os
from dotenv import load_dotenv  
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from starlette.background import BackgroundTask
import sqlite3 
from fastapi.staticfiles import StaticFiles

# Carrega as chaves do arquivo .env para a memória do sistema
load_dotenv()

app = FastAPI()
database.inicializar_banco()
# Permite que o navegador carregue ficheiros da pasta "static" (como o seu style.css)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Puxa as senhas de forma invisível através do os.getenv()
TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}"

CHAVE_GEMINI = os.getenv("CHAVE_GEMINI")
genai.configure(api_key=CHAVE_GEMINI)

modelo = genai.GenerativeModel(
    model_name="gemini-3.8-flash",
    generation_config={"response_mime_type": "application/json"}
)

MODO_TESTE = False

# "Estacionamento" temporário: guarda o JSON da IA até o usuário apertar o botão "Salvar"
despesas_pendentes = {}

@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()

    # O Telegram envia mensagens de texto/foto aqui
    if "message" in update:
        background_tasks.add_task(processar_mensagem, update["message"])
    
    # O Telegram envia cliques de botões aqui (Callback Query)
    elif "callback_query" in update:
        background_tasks.add_task(processar_clique_botao, update["callback_query"])

    return {"status": "ok"}


def processar_mensagem(mensagem: dict):
    chat_id = mensagem["chat"]["id"]
    
    # Extrai o texto se existir (usado para comandos e senhas)
    texto = mensagem.get("text", "")

    # 1. VERIFICAÇÃO DE CADASTRO (O Porteiro)
    # Se a pessoa mandar o comando /registrar com a senha correta
    if texto.startswith("/registrar"):
        partes = texto.split()
        senha_correta = os.getenv("SENHA_CADASTRO")
        
        if len(partes) == 2 and partes[1] == senha_correta:
            database.registrar_usuario(chat_id)
            enviar_mensagem(chat_id, "✅ *Cadastro realizado com sucesso!*\n\nVocê já pode enviar suas notas fiscais e recibos para auditoria.", parse_mode="Markdown")
            mensagem_boas_vindas = (
                "Olá! Eu sou o **Leãozito** 🦁, seu assistente automatizado de auditoria para o Imposto de Renda.\n\n"
                "Estou aqui para organizar a sua vida fiscal. Basta me enviar a **foto ou PDF** de uma nota fiscal ou recibo (saúde, educação, etc.), e eu usarei inteligência artificial para extrair os dados e salvar tudo para você!\n\n"
                "🛠️ **Meus Comandos:**\n"
                "📊 /relatorio - Ver o total acumulado por categoria\n"
                "📥 /exportar - Baixar sua base de dados em planilha Excel\n"
                "🗑️ /limpar - Apagar todo o seu histórico do sistema\n\n"
                "🚀 *Para começar, me envie o seu primeiro comprovante!*"
            ) 
            enviar_mensagem(chat_id, mensagem_boas_vindas, parse_mode="Markdown")
        else:
            enviar_mensagem(chat_id, "❌ *Senha incorreta ou formato inválido.*\nPara acessar, digite: `/registrar SuaSenhaAqui`", parse_mode="Markdown")
        return

    # Bloqueia qualquer pessoa que não esteja cadastrada no banco de dados
    if not database.verificar_autorizacao(chat_id):
        enviar_mensagem(chat_id, "🔒 *Acesso Negado.*\n\nVocê não está cadastrado neste sistema.\nSe você tem um convite, libere seu acesso digitando:\n`/registrar SenhaDeAcesso`", parse_mode="Markdown")
        return

    # 2. FLUXO NORMAL (Só roda se o usuário passou pelo porteiro)
    if texto:
        if texto == "/start":
            mensagem_boas_vindas = (
                "Olá! Eu sou o **Leãozito** 🦁, seu assistente automatizado de auditoria para o Imposto de Renda.\n\n"
                "Estou aqui para organizar a sua vida fiscal. Basta me enviar a **foto ou PDF** de uma nota fiscal ou recibo (saúde, educação, etc.), e eu usarei inteligência artificial para extrair os dados e salvar tudo para você!\n\n"
                "🛠️ **Meus Comandos:**\n"
                "📊 /relatorio - Ver o total acumulado por categoria\n"
                "📥 /exportar - Baixar sua base de dados em planilha Excel\n"
                "🗑️ /limpar - Apagar todo o seu histórico do sistema\n\n"
                "🌐 /painel - Seu Painel Exclusivo\n\n"
                "🚀 *Para começar, me envie o seu primeiro comprovante!*"
            )
            enviar_mensagem(chat_id, mensagem_boas_vindas, parse_mode="Markdown")
        
        elif texto == "/relatorio":
            relatorio = database.gerar_relatorio(chat_id)
            enviar_mensagem(chat_id, relatorio, parse_mode="Markdown")
            
        elif texto == "/limpar":
            database.limpar_dados(chat_id)
            enviar_mensagem(chat_id, "🗑️ *Todos os seus dados de despesas foram apagados com sucesso!*", parse_mode="Markdown")
            
        elif texto == "/exportar":
            enviar_mensagem(chat_id, "⏳ Gerando sua planilha Excel...")
            try:
                caminho_xlsx = database.gerar_xlsx(chat_id)
                enviar_documento(chat_id, caminho_xlsx)
                if os.path.exists(caminho_xlsx):
                    os.remove(caminho_xlsx)
            except Exception as e:
                enviar_mensagem(chat_id, f"❌ Erro interno ao gerar o XLSX: {e}")
        elif texto == "/painel":
            # Passa o chat_id do usuário na URL de forma invisível
            link = f"http://127.0.0.1:8000/dashboard?user={chat_id}"
            enviar_mensagem(chat_id, f"🌐 *Seu Painel Exclusivo:*\n[Clique aqui para acessar o seu Dashboard]({link})", parse_mode="Markdown")
                
        # Se for um texto que não é comando, avisa
        elif not texto.startswith("/"):
            enviar_mensagem(chat_id, "Comando não reconhecido. Envie uma nota fiscal ou digite /relatorio.")

    elif "photo" in mensagem or "document" in mensagem:
        enviar_mensagem(chat_id, "📥 Arquivo recebido! Analisando com Leãozito...")

        if "photo" in mensagem:
            file_id = mensagem["photo"][-1]["file_id"]
            mime_type = "image/jpeg"
        elif "document" in mensagem:
            file_id = mensagem["document"]["file_id"]
            mime_type = mensagem["document"].get("mime_type", "")

            if mime_type != "application/pdf" and not mime_type.startswith("image/"):
                enviar_mensagem(chat_id, "❌ Formato inválido. Envie imagem ou PDF.")
                return

        try:
            dados_arquivo = baixar_arquivo_telegram(file_id)
            dados_json = extrair_dados_com_ia(dados_arquivo, mime_type)

            despesas_pendentes[chat_id] = dados_json

            valor_num = dados_json.get("valor_total")
            valor_formatado = f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(valor_num, (int, float)) else "Não identificado"

            resposta = (
                f"🔎 *Confirme os dados extraídos:*\n\n"
                f"🏥 *Emissor:* {dados_json.get('emissor', 'Não identificado')}\n"
                f"💰 *Valor:* {valor_formatado}\n"
                f"🏷️ *Categoria:* {dados_json.get('categoria', 'Outros')}\n\n"
                f"Deseja salvar esta nota no banco de dados?"
            )
            
            botoes = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Salvar", "callback_data": "acao_salvar"},
                        {"text": "❌ Descartar", "callback_data": "acao_descartar"}
                    ]
                ]
            }
            enviar_mensagem(chat_id, resposta, parse_mode="Markdown", reply_markup=botoes)

        except Exception as e:
            enviar_mensagem(chat_id, f"❌ Ocorreu um erro: {e}")


def processar_clique_botao(callback_query: dict):
    """Lida com a ação quando o usuário clica em 'Salvar' ou 'Descartar'."""
    chat_id = callback_query["message"]["chat"]["id"]
    mensagem_id = callback_query["message"]["message_id"]
    acao = callback_query["data"]  # Pode ser 'acao_salvar' ou 'acao_descartar'

    # Verifica se os dados ainda estão na memória
    if chat_id not in despesas_pendentes:
        editar_mensagem(chat_id, mensagem_id, "⚠️ Esta nota já foi processada ou expirou.")
        return

    if acao == "acao_salvar":
        dados_json = despesas_pendentes[chat_id]
        database.salvar_despesa(chat_id, dados_json)
        editar_mensagem(chat_id, mensagem_id, "✅ *Nota salva com sucesso no banco de dados!*", parse_mode="Markdown")
    
    elif acao == "acao_descartar":
        editar_mensagem(chat_id, mensagem_id, "🗑️ *Nota descartada.* Os dados não foram salvos.", parse_mode="Markdown")

    # Remove da fila de espera independentemente da escolha
    del despesas_pendentes[chat_id]


def enviar_mensagem(chat_id: int, texto: str, parse_mode: str = None, reply_markup: dict = None):
    url = f"{TELEGRAM_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)


def editar_mensagem(chat_id: int, message_id: int, texto: str, parse_mode: str = None):
    """Apaga os botões e altera o texto da mensagem antiga para confirmar a ação."""
    url = f"{TELEGRAM_URL}/editMessageText"
    payload = {
        "chat_id": chat_id, 
        "message_id": message_id, 
        "text": texto,
        "reply_markup": {"inline_keyboard": []} # Remove os botões
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    requests.post(url, json=payload)


def baixar_arquivo_telegram(file_id: str) -> bytes:
    url_info = f"{TELEGRAM_URL}/getFile?file_id={file_id}"
    response_info = requests.get(url_info)
    caminho_do_arquivo = response_info.json()["result"]["file_path"]

    url_download = f"https://api.telegram.org/file/bot{TOKEN_TELEGRAM}/{caminho_do_arquivo}"
    resposta_download = requests.get(url_download)

    return resposta_download.content


def extrair_dados_com_ia(dados_arquivo: bytes, mime_type: str) -> dict:
    if MODO_TESTE:
        return {
            "emissor": "Clínica Médica Brasília S/A",
            "documento_emissor": "12.345.678/0001-99",
            "data_emissao": "08/11/2026",
            "valor_total": 450.00,
            "categoria": "Saúde"
        }

    prompt = """
    Você é um assistente especializado em auditoria fiscal do Imposto de Renda Pessoa Física (IRPF) brasileiro.
    Retorne EXATAMENTE um objeto JSON com os campos: emissor, documento_emissor, data_emissao, valor_total (como float decimal), categoria (Saúde, Educação ou Outros).
    """
    blob_arquivo = {"mime_type": mime_type, "data": dados_arquivo}
    resposta = modelo.generate_content([prompt, blob_arquivo])
    return json.loads(resposta.text)

def enviar_documento(chat_id: int, caminho_arquivo: str):
    """Faz o upload do arquivo gerado para o chat do usuário no Telegram."""
    url = f"{TELEGRAM_URL}/sendDocument"
    try:
        with open(caminho_arquivo, 'rb') as arquivo:
            payload = {"chat_id": chat_id}
            files = {"document": arquivo}
            resposta = requests.post(url, data=payload, files=files)
            
            # Se o Telegram recusar o envio, ele avisa no chat
            if resposta.status_code != 200:
                enviar_mensagem(chat_id, f"❌ Erro na API do Telegram: {resposta.text}")
    except Exception as e:
        enviar_mensagem(chat_id, f"❌ Erro ao tentar ler ou enviar o arquivo: {e}")

@app.get("/dashboard", response_class=HTMLResponse)
def abrir_dashboard():
    """Abre a interface visual do sistema no navegador."""
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Erro: Arquivo dashboard.html não encontrado.</h1>"

@app.get("/api/despesas/{chat_id}")
def api_listar_despesas_usuario(chat_id: int):
    """Fornece os dados do banco apenas para o usuário logado via link mágico."""
    with sqlite3.connect(database.NOME_BANCO) as conexao:
        conexao.row_factory = sqlite3.Row 
        cursor = conexao.cursor()
        
        # O filtro WHERE chat_id = ? garante que o cliente A nunca veja os dados do cliente B
        cursor.execute("SELECT id, chat_id, emissor, documento_emissor, data_emissao, valor_total, categoria FROM despesas WHERE chat_id = ?", (chat_id,))
        resultados = cursor.fetchall()
        return [dict(linha) for linha in resultados]


@app.get("/api/exportar/{chat_id}")
def api_exportar_xlsx(chat_id: int):
    """Entrega o XLSX gerado por database.gerar_xlsx() (o mesmo do comando /exportar)."""
    if not database.verificar_autorizacao(chat_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    caminho = database.gerar_xlsx(chat_id)
    return FileResponse(
        caminho,
        filename=os.path.basename(caminho),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(os.remove, caminho),  # apaga o arquivo temporário após o envio
    )


@app.get("/api/relatorio/{chat_id}", response_class=PlainTextResponse)
def api_relatorio(chat_id: int):
    """Devolve o texto de database.gerar_relatorio() (o mesmo do comando /relatorio)."""
    if not database.verificar_autorizacao(chat_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return database.gerar_relatorio(chat_id)

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("static/favicon.png")
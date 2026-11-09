from fastapi import FastAPI, Request, BackgroundTasks
import requests
import google.generativeai as genai
import json
import database
import os

app = FastAPI()
database.inicializar_banco()

TOKEN_TELEGRAM = "9219114965:AAEQ5TLAiz2NoQFdaKwKHJuzOejSA2bUjo8"
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}"

CHAVE_GEMINI = "AQ.Ab8RN6K-Kcb4flwH-8FD-IzqPh6XQh8xc0MdYbHiIMGUQOV64A"
genai.configure(api_key=CHAVE_GEMINI)

modelo = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config={"response_mime_type": "application/json"}
)

MODO_TESTE = True

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

    if "text" in mensagem:
        texto = mensagem["text"]
        
        # COMANDOS DE TEXTO
        if texto == "/start":
            enviar_mensagem(chat_id, "Olá! Envie uma foto ou um PDF de sua nota fiscal.\n\nUse /relatorio para ver o total das suas despesas dedutíveis.")
        elif texto == "/relatorio":
            relatorio = database.gerar_relatorio(chat_id)
            enviar_mensagem(chat_id, relatorio, parse_mode="Markdown")
        elif texto == "/limpar":
            database.limpar_dados(chat_id)
            enviar_mensagem(chat_id, "🗑️ *Todos os seus dados foram apagados com sucesso!*", parse_mode="Markdown")
        elif texto == "/exportar":
            enviar_mensagem(chat_id, "⏳ Gerando sua planilha Excel...")
            try:
                # Chama a nova função XLSX
                caminho_xlsx = database.gerar_xlsx(chat_id)
                enviar_documento(chat_id, caminho_xlsx)
                
                # Remove a planilha do seu computador para não acumular lixo
                if os.path.exists(caminho_xlsx):
                    os.remove(caminho_xlsx)
            except Exception as e:
                enviar_mensagem(chat_id, f"❌ Erro interno ao gerar o XLSX: {e}")
                
        else:
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

            # Coloca os dados na fila de espera associados ao chat_id do usuário
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
            
            # Monta os botões que aparecerão embaixo da mensagem
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
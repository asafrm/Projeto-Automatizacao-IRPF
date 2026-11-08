from xml.parsers.expat import model
from fastapi import FastAPI, Request, BackgroundTasks
import requests
import google.generativeai as genai
import json
import database  # Importa o módulo database.py para inicializar o banco de dados

app = FastAPI()

database.inicializar_banco()  # Inicializa o banco de dados ao iniciar a aplicação

# -------------- CONFIGURAÇÃO --------------
TOKEN_TELEGRAM = "9219114965:AAEQ5TLAiz2NoQFdaKwKHJuzOejSA2bUjo8"
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}"

CHAVE_GEMINI = "AQ.Ab8RN6K-Kcb4flwH-8FD-IzqPh6XQh8xc0MdYbHiIMGUQOV64A"
genai.configure(api_key=CHAVE_GEMINI)
# Força a resposta do modelo a ser sempre um JSON válido
modelo = genai.GenerativeModel(
    model_name="gemini-3.8-flash",
    generation_config={"response_mime_type": "application/json"}
) 

MODO_TESTE = True

@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()

    # Passa apenas update["message"] para rodar em segundo plano
    if "message" in update:
        background_tasks.add_task(processar_mensagem, update["message"])

    # Responde 200 OK imediatamente para evitar loop no Telegram
    return {"status": "ok"}


def processar_mensagem(mensagem: dict):
    """Função que roda em segundo plano sem travar a resposta para o Telegram."""
    chat_id = mensagem["chat"]["id"]

    if "text" in mensagem:
        texto = mensagem["text"]
        if texto == "/start":
            enviar_mensagem(chat_id, "Olá! Envie uma foto ou um PDF de sua nota fiscal para extrairmos os dados.")
        else:
            enviar_mensagem(chat_id, "Por favor, envie uma foto ou PDF da nota fiscal.")

    elif "photo" in mensagem or "document" in mensagem:
        enviar_mensagem(chat_id, "📥 Arquivo recebido! Analisando com Leãozito...")

        if "photo" in mensagem:
            file_id = mensagem["photo"][-1]["file_id"]
            mime_type = "image/jpeg"
        elif "document" in mensagem:
            file_id = mensagem["document"]["file_id"]
            mime_type = mensagem["document"].get("mime_type", "")

            if mime_type != "application/pdf" and not mime_type.startswith("image/"):
                enviar_mensagem(chat_id, "❌ Tipo de arquivo não suportado. Por favor, envie uma imagem ou um PDF.")
                return

        try:
            dados_arquivo = baixar_arquivo_telegram(file_id)

            # Agora retorna um dicionário Python estruturado (dict)
            dados_json = extrair_dados_com_ia(dados_arquivo, mime_type)

            # Formatar o valor para exibição amigável no padrão brasileiro
            valor_num = dados_json.get("valor_total")
            valor_formatado = f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(valor_num, (int, float)) else "Não identificado"            

            resposta = (
                f"✅ *Dados Extraídos (JSON Estruturado):*\n\n"
                f"🏥 *Emissor:* {dados_json.get('emissor', 'Não identificado')}\n"
                f"📄 *Documento:* {dados_json.get('documento_emissor', 'Não identificado')}\n"
                f"📅 *Data:* {dados_json.get('data_emissao', 'Não identificado')}\n"
                f"💰 *Valor:* {valor_formatado}\n"
                f"🏷️ *Categoria:* {dados_json.get('categoria', 'Outros')}\n\n"
                f"⚙️ _Objeto salvo em memória pronto para o banco de dados._"
            )
            enviar_mensagem(chat_id, resposta, parse_mode="Markdown")

        except Exception as e:
            enviar_mensagem(chat_id, f"❌ Ocorreu um erro ao processar o arquivo: {e}")

def enviar_mensagem(chat_id: int, texto: str, parse_mode: str = None):
    """Função auxiliar para o bot responder ao usuário."""
    url = f"{TELEGRAM_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    requests.post(url, json=payload)


def baixar_arquivo_telegram(file_id: str) -> bytes:
    """Faz o download do arquivo em formato binário (bytes)."""
    url_info = f"{TELEGRAM_URL}/getFile?file_id={file_id}"
    response_info = requests.get(url_info)
    caminho_do_arquivo = response_info.json()["result"]["file_path"]

    url_download = f"https://api.telegram.org/file/bot{TOKEN_TELEGRAM}/{caminho_do_arquivo}"
    resposta_download = requests.get(url_download)

    return resposta_download.content


def extrair_dados_com_ia(dados_arquivo: bytes, mime_type: str) -> str:
    """Envia o arquivo e o prompt para o Gemini."""

    # Simulação para desenvolvimento sem consumir cota da API
    if MODO_TESTE:
        return {
            "emissor": "Clínica Médica Brasília S/A (Simulado)",
            "documento_emissor": "12.345.678/0001-99",
            "data_emissao": "08/11/2026",
            "valor_total": 450.00,
            "categoria": "Saúde"
        }
    
    prompt = """
    Você é um assistente especializado em auditoria fiscal do Imposto de Renda Pessoa Física (IRPF) brasileiro.
    Analise cuidadosamente a nota fiscal ou recibo fornecido e extraia os dados do prestador do serviço (nunca do paciente/cliente).

    Retorne EXATAMENTE um objeto JSON seguindo este esquema:
    {
        "emissor": "Nome completo da clínica, empresa ou profissional, ou 'Não identificado'",
        "documento_emissor": "CNPJ ou CPF do prestador formatado, ou 'Não identificado'",
        "data_emissao": "Data de emissão no formato DD/MM/AAAA, ou 'Não identificado'",
        "valor_total": 0.00,
        "categoria": "Saúde, Educação ou Outros"
    }

    Regras:
    - 'valor_total' deve ser estritamente um número decimal (float) usando ponto como separador (ex: 1250.50). Se não encontrar, retorne null.
    - 'categoria' deve ser estritamente uma das três opções: "Saúde", "Educação" ou "Outros".
    - Não deduza ou invente dados ausentes.
    """

    # Empacota os bytes e o mime_type (funciona tanto para image/jpeg quanto para application/pdf)
    blob_arquivo = {
        "mime_type": mime_type,
        "data": dados_arquivo
    }

    resposta = modelo.generate_content([prompt, blob_arquivo])
    
    # Converte a string JSON devolvida pela IA em um dicionário real do Python
    dados_estruturados = json.loads(resposta.text)
    return dados_estruturados
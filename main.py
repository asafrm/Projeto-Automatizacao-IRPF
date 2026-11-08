from fastapi import FastAPI, Request, BackgroundTasks
import requests
import google.generativeai as genai

app = FastAPI()

# -------------- CONFIGURAÇÃO --------------
TOKEN_TELEGRAM = "9219114965:AAEQ5TLAiz2NoQFdaKwKHJuzOejSA2bUjo8"
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}"

CHAVE_GEMINI = "AQ.Ab8RN6K-Kcb4flwH-8FD-IzqPh6XQh8xc0MdYbHiIMGUQOV64A"
genai.configure(api_key=CHAVE_GEMINI)
modelo = genai.GenerativeModel("gemini-3.8-flash") # Modelo rápido com suporte a imagens

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
            dados_extraidos = extrair_dados_com_ia(dados_arquivo, mime_type)

            resposta = f"✅ Dados extraídos:\n{dados_extraidos}"
            enviar_mensagem(chat_id, resposta)

        except Exception as e:
            enviar_mensagem(chat_id, f"❌ Ocorreu um erro ao processar o arquivo: {e}")


def enviar_mensagem(chat_id: int, texto: str):
    """Função auxiliar para o seu bot responder ao usuário."""
    url = f"{TELEGRAM_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
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
    prompt = """
    Você é um **assistente especializado em auditoria fiscal do Imposto de Renda Pessoa Física (IRPF) brasileiro**.

    Sua função é analisar notas fiscais, recibos e comprovantes de pagamento, identificando e extraindo informações relevantes para a declaração do IRPF.

    Analise cuidadosamente o documento fornecido e extraia os seguintes dados:

    - **Emissor:** Nome completo da clínica, empresa ou profissional que prestou o serviço.
    - **CNPJ ou CPF do emissor:** Identificação fiscal do prestador do serviço.
    - **Data de emissão:** Data em que a nota fiscal ou recibo foi emitido, no formato DD/MM/AAAA.
    - **Valor total:** Valor total do serviço ou despesa, no formato R$ 0.000,00.
    - **Categoria provável:** Classifique a despesa em uma das seguintes categorias:
      - Saúde: consultas médicas, odontológicas, psicológicas, exames, hospitais e demais serviços de saúde.
      - Educação: mensalidades escolares, ensino superior, educação profissional e demais despesas educacionais potencialmente dedutíveis.
      - Outros: despesas que não se enquadrem nas categorias anteriores.

    ### Regras de análise e validação

    1. Identifique exclusivamente os dados do emissor/prestador do serviço. Não confunda com os dados do paciente, cliente ou tomador do serviço.
    2. Não confunda a data de emissão com a data de prestação do serviço ou de pagamento.
    3. Considere o valor total efetivamente informado no documento, sem somar valores já incluídos no total.
    4. Não deduza, invente ou presuma informações que não estejam claramente presentes no documento.
    5. Caso uma informação não esteja disponível ou não possa ser lida com segurança, retorne exatamente: "Não identificado".
    6. A classificação deve considerar a natureza do serviço ou produto descrito no documento, e não apenas o nome do estabelecimento.
    7. Não considere automaticamente que uma despesa classificada como Saúde ou Educação seja dedutível no IRPF. A classificação é apenas indicativa e não substitui a análise das regras fiscais da Receita Federal.

    ### Formato obrigatório de resposta

    Emissor: 
    CNPJ ou CPF do emissor:
    Data da emissão:
    Valor total:
    Categoria provável:

    **IMPORTANTE:** Retorne exclusivamente os cinco campos solicitados, sem introduções, explicações, observações ou comentários adicionais.
    """

    # Empacota os bytes e o mime_type (funciona tanto para image/jpeg quanto para application/pdf)
    blob_arquivo = {
        "mime_type": mime_type,
        "data": dados_arquivo
    }

    resposta = modelo.generate_content([prompt, blob_arquivo])
    return resposta.text
import sqlite3
from datetime import datetime

NOME_BANCO = "imposto_renda.db"

def inicializar_banco():
    """ Cria o banco de dados e a tabela se não existirem. """
    with sqlite3.connect(NOME_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                emissor TEXT,
                documento_emissor TEXT,
                data_emissao TEXT,
                valor_total REAL,
                categoria TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def salvar_despesa(chat_id: int, dados_json: dict):
    """ Insere o JSON extraído na tabela de despesas. """
    with sqlite3.connect(NOME_BANCO) as conn:
        cursor = conn.cursor()
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("""
            INSERT INTO documentos (chat_id, emissor, documento_emissor, data_emissao, valor_total, categoria)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            dados_json.get("emissor"),
            dados_json.get("documento_emissor"),
            dados_json.get("data_emissao"),
            dados_json.get("valor_total"),
            dados_json.get("categoria")
        ))
        conn.commit()
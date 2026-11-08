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

def gerar_relatorio(chat_id: int) -> str:
    """ Soma as despesas do usuário por categoria e retorna um texto formatado. """
    with sqlite3.connect(NOME_BANCO) as conn:
        cursor = conn.cursor()

        # O SQL SUM() soma os valores e o GRUPO BY agrupa por categoria
        cursor.execute("""
            SELECT categoria, SUM(valor_total)
            FROM despesas
            WHERE chat_id = ?
            GROUP BY categoria
        """, (chat_id,))

        resultados = cursor.fetchall()

        if not resultados:
            return "Nenhuma despesa registrada."

        relatorio = "📊 *Relatório de Despesas por Categoria:*\n\n"
        total_geral = 0.0

        for categoria, total in resultados:
            total_formatado = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            relatorio += f"🏷️ *{categoria}:* {total_formatado}\n"
            total_geral += total

        total_geral_format = f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        relatorio += f"\n💰 *Total Geral:* {total_geral_format}"

        return relatorio
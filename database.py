import sqlite3
from datetime import datetime
import csv

NOME_BANCO = "imposto_renda.db"

def inicializar_banco():
    """Cria o banco de dados e a tabela se eles ainda não existirem."""
    with sqlite3.connect(NOME_BANCO) as conexao:
        cursor = conexao.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS despesas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                emissor TEXT,
                documento_emissor TEXT,
                data_emissao TEXT,
                valor_total REAL,
                categoria TEXT,
                data_registro TEXT
            )
        """)
        conexao.commit()

def salvar_despesa(chat_id: int, dados_json: dict):
    """Insere o JSON extraído na tabela de despesas."""
    with sqlite3.connect(NOME_BANCO) as conexao:
        cursor = conexao.cursor()
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO despesas (chat_id, emissor, documento_emissor, data_emissao, valor_total, categoria, data_registro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            dados_json.get("emissor"),
            dados_json.get("documento_emissor"),
            dados_json.get("data_emissao"),
            dados_json.get("valor_total"),
            dados_json.get("categoria"),
            data_atual
        ))
        conexao.commit()

def gerar_relatorio(chat_id: int) -> str:
    """Soma as despesas do usuário por categoria e retorna um texto formatado."""
    with sqlite3.connect(NOME_BANCO) as conexao:
        cursor = conexao.cursor()
        
        # O SQL SUM() soma os valores e o GROUP BY separa por Saúde, Educação, etc.
        cursor.execute("""
            SELECT categoria, SUM(valor_total)
            FROM despesas
            WHERE chat_id = ?
            GROUP BY categoria
        """, (chat_id,))
        
        resultados = cursor.fetchall()
        
        if not resultados:
            return "Nenhuma despesa registrada ainda."
        
        relatorio = "📊 *Resumo de Despesas para o IRPF:*\n\n"
        total_geral = 0
        
        for categoria, total in resultados:
            # Formata o número para o padrão brasileiro (ex: 1.250,00)
            total_formatado = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            relatorio += f"🔹 *{categoria}:* {total_formatado}\n"
            total_geral += total
            
        total_geral_format = f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        relatorio += f"\n💵 *Total Geral:* {total_geral_format}"
        
        return relatorio

def limpar_dados(chat_id: int):
    """Apaga todos os registros de um usuário específico."""
    with sqlite3.connect(NOME_BANCO) as conexao:
        cursor = conexao.cursor()
        # CORREÇÃO: Adicionada a vírgula após chat_id (chat_id,)
        cursor.execute("DELETE FROM despesas WHERE chat_id = ?", (chat_id,))
        conexao.commit()

def gerar_csv(chat_id: int) -> str:
    """Gerar um arquivo CSV com as despesas do usuário e retorna o caminho do arquivo."""
    with sqlite3.connect(NOME_BANCO) as conexao:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT emissor, documento_emissor, data_emissao, valor_total, categoria, data_registro
            FROM despesas
            WHERE chat_id = ?
        """, (chat_id,))
        resultados = cursor.fetchall()

    caminho_arquivo = f"despesas_irpf_{chat_id}.csv"

    with open(caminho_arquivo, mode='w', newline='', encoding='utf-8-sig') as arquivo_csv:
        escritor = csv.writer(arquivo_csv, delimiter=';')
        escritor.writerow(['Emissor', 'CNPJ/CPF', 'Data da Emissão', 'Valor Total', 'Categoria', 'Data de Registro'])

        for linha in resultados:
            linha_formatada = list(linha)
            linha_formatada[3] = str(linha_formatada[3]).replace('.', ',')
            
            escritor.writerow(linha_formatada)
            
    return caminho_arquivo

    #Criando o arquivo CSV
    with open(caminho_arquivo, mode='w', newline='', encoding='utf-8-sig') as arquivo_csv:
        #Usamos o delimitados ';' para o Excel abrir colunas automaticamento no Brasil
        escritor = csv.writer(arquivo_csv, delimiter=';')

        #Cabeçalho da planilha
        escritor.writerow(['Emissor', 'CNPJ/CPF', 'Data da Emissão', 'Valor Total', 'Categoria', 'Data de Registro'])

        #Escreve os dados
        for linha in resultados:
            linha_formatada = list(linha)
            #Troca o ponto do banco de dados por vírgula
            linha_formatada[3] = str(linha_formatada[3]).replace('.', ',')
    return caminho_arquivo
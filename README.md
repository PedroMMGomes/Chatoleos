# Chatoleos

Sistema de chat WhatsApp com LLM e RAG (Retrieval-Augmented Generation) para produtos da Óleos da Terra.

## 📋 Descrição

Este projeto realiza web scraping do site Óleos da Terra, processa os dados dos produtos e os armazena em um banco de dados vetorial (ChromaDB) para uso em um sistema RAG. O objetivo é criar um assistente inteligente capaz de responder perguntas sobre os produtos usando informações atualizadas.

## 🚀 Funcionalidades

- **Web Scraping**: Coleta automática de dados de produtos do site Óleos da Terra
- **Processamento de Dados**: Extração e formatação de informações relevantes dos produtos
- **Geração de Embeddings**: Criação de representações vetoriais dos produtos usando Ollama
- **Armazenamento Vetorial**: Indexação dos produtos no ChromaDB para busca semântica eficiente
- **Sistema RAG**: Preparado para integração com LLMs para respostas contextualizadas

## 📦 Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/chatoleos.git
cd chatoleos
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Instale e configure o Ollama:
   - Baixe o Ollama de [ollama.ai](https://ollama.ai)
   - Execute: `ollama pull mxbai-embed-large`

## 🛠️ Configuração

O arquivo `ingest_to_rag.py` contém as seguintes configurações principais:

```python
PRODUCTS_FILE = "products_data.json"  # Arquivo de dados dos produtos
CHROMA_DB_PATH = "chroma_db_store"    # Pasta do banco vetorial
EMBEDDING_MODEL_NAME = "mxbai-embed-large"  # Modelo de embeddings
SCRAPER_MAX_PRODUCTS = 200  # Máximo de produtos para coletar
```

## 📖 Uso

### 1. Executar o Scraper e Ingestão

```bash
python ingest_to_rag.py
```

Este comando irá:
- Verificar se existe um arquivo de produtos
- Executar o scraper se necessário
- Gerar embeddings para cada produto
- Armazenar tudo no ChromaDB

### 2. Estrutura dos Dados

Cada produto contém:
- **title**: Nome do produto
- **description**: Descrição detalhada
- **price**: Preço
- **category**: Categoria
- **url**: Link do produto
- **images**: URLs das imagens
- **extra_info**: Informações adicionais

## 📁 Estrutura do Projeto

```
Chatoleos/
├── README.md           # Este arquivo
├── requirements.txt    # Dependências do projeto
├── scraper.py         # Módulo de web scraping
├── ingest_to_rag.py   # Script principal de ingestão
├── products_data.json # Dados coletados (gerado)
└── chroma_db_store/   # Banco de dados vetorial (gerado)
```

## 🔧 Troubleshooting

### Erro de Ollama
Se receber erro ao conectar com Ollama:
1. Verifique se o Ollama está rodando: `ollama list`
2. Confirme se o modelo está instalado: `ollama pull mxbai-embed-large`
3. Verifique se a API está acessível em `http://localhost:11434`

### Erro de ChromaDB
Se houver problemas com o ChromaDB:
1. Delete a pasta `chroma_db_store` e execute novamente
2. Verifique a versão: `pip show chromadb`

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:
1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🔗 Links Úteis

- [Óleos da Terra](https://oleosdaterra.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Ollama Documentation](https://github.com/ollama/ollama)

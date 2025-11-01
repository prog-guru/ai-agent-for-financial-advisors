# RAG System for Client Questions

This system implements Retrieval-Augmented Generation (RAG) to answer questions about clients using data from Gmail and HubSpot.

## Features

- **Gmail Integration**: Imports emails and creates searchable embeddings
- **HubSpot Integration**: Imports contacts and notes with embeddings
- **Semantic Search**: Uses sentence-transformers for similarity search
- **Vector Database**: PostgreSQL with pgvector for efficient similarity queries
- **AI Responses**: OpenAI generates contextual answers

## Architecture

```
User Question → Embedding → Similarity Search → Context → OpenAI → Answer
```

## API Endpoints

### 1. Sync Data
```http
POST /api/rag/sync-data
```
Syncs Gmail emails and HubSpot contacts/notes in the background.

### 2. RAG Chat
```http
POST /api/rag/chat
Content-Type: application/json

{
  "content": "Who mentioned their kid plays baseball?"
}
```

### 3. Search Documents
```http
GET /api/rag/search?query=baseball&limit=5&source_type=gmail
```

### 4. Get Statistics
```http
GET /api/rag/stats
```

## Example Questions

- "Who mentioned their kid plays baseball?"
- "Why did greg say he wanted to sell AAPL stock?"
- "Which clients are interested in real estate?"
- "Who works at Microsoft?"
- "What did Sarah say about her vacation plans?"

## Database Schema

### New Tables
- `gmail_emails`: Stores email content and metadata
- `hubspot_contacts`: Stores contact information
- `hubspot_notes`: Stores contact notes
- `document_embeddings`: Stores vector embeddings with pgvector

## Setup

1. **Install Dependencies**:
```bash
pip install psycopg2-binary pgvector sentence-transformers
```

2. **Database Setup**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

3. **Environment Variables**:
```env
DATABASE_URL=postgresql://user:pass@localhost/dbname
OPENAI_API_KEY=your_openai_key
```

## Usage Flow

1. **Connect Accounts**: User connects Gmail and HubSpot via OAuth
2. **Sync Data**: System imports emails and CRM data
3. **Generate Embeddings**: Creates vector embeddings for all content
4. **Ask Questions**: User asks natural language questions
5. **Get Answers**: AI provides contextual responses with specific details

## Technical Details

- **Embeddings**: Uses `all-MiniLM-L6-v2` (384 dimensions)
- **Vector DB**: PostgreSQL with pgvector extension
- **Similarity**: Cosine similarity search
- **Context Window**: 2000 characters max
- **Background Sync**: Async data import to avoid blocking

## Security

- User-scoped data (each user only sees their own data)
- OAuth tokens stored securely
- No cross-user data leakage in embeddings or search
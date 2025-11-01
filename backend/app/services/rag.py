# app/services/rag.py
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Tuple
import numpy as np
import logging

from ..models import DocumentEmbedding, User

logger = logging.getLogger("rag")

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def store_embedding(self, db: Session, user_id: int, source_type: str, 
                       source_id: str, content: str, metadata: Dict[str, Any] = None):
        """Store text content with its embedding"""
        embedding = self.generate_embedding(content)
        
        # Check if embedding already exists
        existing = db.query(DocumentEmbedding).filter(
            DocumentEmbedding.user_id == user_id,
            DocumentEmbedding.source_type == source_type,
            DocumentEmbedding.source_id == source_id
        ).first()
        
        if existing:
            existing.content = content
            existing.embedding = embedding
            existing.meta_data = metadata or {}
        else:
            doc_embedding = DocumentEmbedding(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                content=content,
                embedding=embedding,
                meta_data=metadata or {}
            )
            db.add(doc_embedding)
        
        db.commit()
    
    def similarity_search(self, db: Session, user_id: int, query: str, 
                         limit: int = 5, source_type: str = None) -> List[Tuple[DocumentEmbedding, float]]:
        """Find similar documents using text search"""
        # Use text search with multiple keywords
        keywords = query.lower().split()
        
        query_obj = db.query(DocumentEmbedding).filter(DocumentEmbedding.user_id == user_id)
        
        if source_type:
            query_obj = query_obj.filter(DocumentEmbedding.source_type == source_type)
        
        # Search for any keyword in content
        conditions = []
        for keyword in keywords:
            conditions.append(DocumentEmbedding.content.ilike(f"%{keyword}%"))
        
        if conditions:
            from sqlalchemy import or_
            query_obj = query_obj.filter(or_(*conditions))
        
        docs = query_obj.limit(limit).all()
        print(f"DEBUG: Found {len(docs)} documents for query: {query}")
        logger.info(f"Found {len(docs)} documents for query: {query}")
        
        # Return with similarity scores based on keyword matches
        results = []
        for doc in docs:
            score = sum(1 for keyword in keywords if keyword in doc.content.lower()) / len(keywords)
            results.append((doc, score))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def get_context_for_query(self, db: Session, user_id: int, query: str, 
                             max_context_length: int = 2000) -> str:
        """Get relevant context for a query"""
        print(f"DEBUG: Getting context for query: {query}")
        similar_docs = self.similarity_search(db, user_id, query, limit=10)
        print(f"DEBUG: Found {len(similar_docs)} similar documents")
        
        context_parts = []
        current_length = 0
        
        for doc, similarity in similar_docs:
            print(f"DEBUG: Processing doc with similarity {similarity:.3f}")
            logger.info(f"Document similarity: {similarity:.3f} for content: {doc.content[:100]}...")
            if similarity < 0.1:  # Lower threshold for more results
                print(f"DEBUG: Skipping document with low similarity: {similarity:.3f}")
                logger.info(f"Skipping document with low similarity: {similarity:.3f}")
                continue
                
            print(f"DEBUG: Processing document with similarity {similarity:.3f}")
            # Format context based on source type
            if doc.source_type == 'gmail':
                metadata = doc.meta_data or {}
                # Truncate long content
                content = doc.content[:500] + "..." if len(doc.content) > 500 else doc.content
                context = f"Email from {metadata.get('sender', 'unknown')} - Subject: {metadata.get('subject', 'No subject')}\n{content}"
            elif doc.source_type == 'hubspot':
                metadata = doc.meta_data or {}
                if metadata.get('type') == 'contact':
                    context = f"Contact: {metadata.get('name', 'Unknown')} ({metadata.get('email', '')})\n{doc.content}"
                else:
                    context = f"HubSpot Note: {doc.content}"
            else:
                context = doc.content
            
            print(f"DEBUG: Context length: {len(context)}, current_length: {current_length}, max: {max_context_length}")
            if current_length + len(context) > max_context_length:
                print(f"DEBUG: Breaking due to length limit")
                break
                
            context_parts.append(context)
            current_length += len(context)
            logger.info(f"Added context part {len(context_parts)}: {len(context)} chars")
        
        final_context = "\n\n---\n\n".join(context_parts)
        print(f"DEBUG: Final context length: {len(final_context)} chars")
        print(f"DEBUG: Context preview: {final_context[:200]}...")
        logger.info(f"Final context length: {len(final_context)} chars")
        return final_context

# Global instance
rag_service = RAGService()
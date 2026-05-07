import time
import re
import string
import numpy as np
from typing import List
from ollama import Client
from .pseudonymiser import pseudonymiser
from ..config import settings

class EmbedService:
    """
    On-premise embedding service for the UBID platform.
    Uses nomic-embed-text:latest via Ollama.
    """
    
    def __init__(self, model: str = "nomic-embed-text:latest"):
        self.model = model
        self.client = Client(host=settings.OLLAMA_HOST)
        
        # Punctuation removal translation table
        self._punct_map = str.maketrans("", "", string.punctuation)
        
        # Regex for suffixes and prefixes
        self._legal_suffixes = re.compile(
            r"\b(pvt ltd|llp|&co|pvt|ltd|private limited|proprietary|prop)\b", 
            re.IGNORECASE
        )
        self._prefixes = re.compile(
            r"\b(m/s\.|m/s|ms|mr|sri|shri|new|the)\b", 
            re.IGNORECASE
        )

    def embed_text(self, text: str) -> List[float]:
        """
        Calls local Ollama to generate a 768-dim embedding vector.
        Expects text to be ALREADY pseudonymised if it contains PII.
        """
        if not text or not text.strip():
            raise ValueError("Embedding input text cannot be empty")
            
        response = self.client.embeddings(model=self.model, prompt=text.strip())
        return response["embedding"]

    def embed_business_name(self, raw_name: str) -> List[float]:
        """
        Primary method for semantic search.
        Normalises, pseudonymises, and then embeds the name.
        """
        # 1. Normalisation
        name = raw_name.lower().strip()
        
        # Remove common prefixes (m/s, sri, etc.)
        name = self._prefixes.sub("", name)
        
        # Remove punctuation
        name = name.translate(self._punct_map)
        
        # Remove legal suffixes (pvt ltd, llp, etc.)
        name = self._legal_suffixes.sub("", name)
        
        # Final cleanup
        name = name.strip()
        
        # 2. Pseudonymisation
        pseudonym = pseudonymiser.pseudonymise_name(name)
        
        # 3. Embedding
        return self.embed_text(pseudonym)

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """
        Computes cosine similarity using numpy.
        Returns float in [-1, 1], where 1 is identical.
        """
        a = np.array(vec_a)
        b = np.array(vec_b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        return float(dot_product / (norm_a * norm_b))

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        Loops through text list to generate embeddings.
        Adds 50ms delay between calls to preserve local GPU resources.
        """
        results = []
        for text in texts:
            results.append(self.embed_text(text))
            time.sleep(0.05) # 50ms sleep
        return results

# Global singleton instance
embed_service = EmbedService()

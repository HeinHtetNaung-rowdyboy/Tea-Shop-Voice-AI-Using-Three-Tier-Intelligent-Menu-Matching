"""Optional FAISS using paraphrase-multilingual-MiniLM-L12-v2 (CPU)."""
import os
import numpy as np

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

class SemanticMatcher:
    def __init__(self, menu):
        import faiss
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(os.getenv("SEMANTIC_MODEL_ID", DEFAULT_MODEL), device="cpu")
        self.phrases=[]
        self.ids=[]
        seen=set()
        for item in menu:
            for phrase in [item["name"], *(item.get("aliases") or [])]:
                key=(str(item["id"]), phrase)
                if key in seen: continue
                seen.add(key)
                self.phrases.append(phrase)
                self.ids.append(str(item["id"]))
        vectors = self.model.encode(self.phrases, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
        vectors = np.ascontiguousarray(vectors, dtype="float32")
        self.index = faiss.IndexFlatIP(vectors.shape[1]); self.index.add(vectors)

    def search(self, phrase, top_k=4):
        if not self.ids: return []
        vector=self.model.encode([phrase], normalize_embeddings=True, convert_to_numpy=True)
        scores, indices=self.index.search(np.ascontiguousarray(vector, dtype="float32"), min(len(self.ids), max(12,top_k*6)))
        seen=set(); result=[]
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or self.ids[idx] in seen: continue
            seen.add(self.ids[idx]);result.append({"id":self.ids[idx], "score":float(score), "method":"semantic", "alias":self.phrases[idx]})
            if len(result)>=top_k: break
        return result

import chromadb 
from db import get_chroma
c =get_chroma()
result=c.query(query_texts=["how can i connect to db in python"],n_results=5,)
for id, doc, dist in zip(result["ids"][0], result["documents"][0], result["distances"][0]):
    print(id, round(dist, 3), doc)

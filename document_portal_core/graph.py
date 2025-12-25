"""
Graph extraction logic for Document Portal.

This module provides the GraphExtractor class for extracting entities/clauses and building
a relationship graph from two contract documents. Uses NetworkX for graph structure.
"""
from typing import Dict, List, Any
import networkx as nx
import re

class GraphExtractor:
    """
    Extracts a relationship graph from two documents (entities/clauses as nodes, relationships as edges).
    Modular and production-grade.

    Usage:
        extractor = GraphExtractor()
        graph_data = extractor.extract_graph(doc1, doc2)
    """
    def __init__(self):
        pass

    def extract_graph(self, doc1: str, doc2: str) -> Dict[str, Any]:
        """
        Extracts a simple relationship graph from two documents.
        Args:
            doc1 (str): Text of the first document.
            doc2 (str): Text of the second document.
        Returns:
            Dict[str, Any]: Graph data (nodes, edges).
        """
        # Example: extract capitalized words as entities/clauses
        entities1 = set(re.findall(r'\b[A-Z][a-zA-Z0-9_\-]+\b', doc1))
        entities2 = set(re.findall(r'\b[A-Z][a-zA-Z0-9_\-]+\b', doc2))
        all_entities = list(entities1 | entities2)

        # Build graph: nodes are entities, edges if entity appears in both docs
        G = nx.Graph()
        for ent in all_entities:
            G.add_node(ent, in_doc1=ent in entities1, in_doc2=ent in entities2)
        for ent in entities1 & entities2:
            G.add_edge(ent, ent, relation="common")

        # Return as node/edge lists for API
        nodes = [{"id": n, **G.nodes[n]} for n in G.nodes]
        edges = [{"source": u, "target": v, **G.edges[u, v]} for u, v in G.edges]
        return {"nodes": nodes, "edges": edges}

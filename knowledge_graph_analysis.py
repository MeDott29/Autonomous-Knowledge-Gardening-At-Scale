import os
import json
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any, Optional
import community as community_louvain
import random
import powerlaw
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

class KnowledgeGraphAnalyzer:
    """Analyzer for knowledge graphs using algorithms from the paper"""
    
    def __init__(self, garden_dir="knowledge_garden"):
        """Initialize the knowledge graph analyzer"""
        self.garden_dir = Path(garden_dir)
        self.index_path = self.garden_dir / "index.json"
        self.graph = None
        self.embeddings = {}
        self.embedding_model = None
        
        # Load the knowledge garden index
        if self.index_path.exists():
            with open(self.index_path, "r") as f:
                self.index = json.load(f)
        else:
            raise FileNotFoundError(f"Knowledge garden index not found at {self.index_path}")
        
        # Build the graph
        self.build_graph()
    
    def build_graph(self):
        """Build a NetworkX graph from the knowledge garden"""
        self.graph = nx.Graph()
        
        # Add notes as nodes
        for title, data in self.index["notes"].items():
            self.graph.add_node(
                title, 
                type="note", 
                tags=data["tags"], 
                created=data["created"],
                path=data["path"]
            )
        
        # Add tags as nodes
        for tag, notes in self.index["tags"].items():
            tag_id = f"tag:{tag}"
            self.graph.add_node(tag_id, type="tag", title=tag)
            
            # Connect tags to notes
            for note in notes:
                if note in self.graph:
                    self.graph.add_edge(tag_id, note, type="tagged")
        
        # Add paths as nodes if they exist
        if "paths" in self.index:
            for topic, path_data in self.index["paths"].items():
                path_id = f"path:{topic}"
                self.graph.add_node(
                    path_id, 
                    type="path", 
                    title=topic,
                    subtopics=path_data.get("subtopics", [])
                )
                
                # Try to connect paths to related notes
                for note in self.graph.nodes():
                    if self.graph.nodes[note].get("type") == "note":
                        note_tags = self.graph.nodes[note].get("tags", [])
                        if (topic.lower() in note_tags or 
                            topic.lower() in note.lower() or
                            any(subtopic.lower() in note.lower() for subtopic in path_data.get("subtopics", []))):
                            self.graph.add_edge(path_id, note, type="path")
        
        # Add edges between related notes
        for title, data in self.index["notes"].items():
            for related in data.get("related_notes", []):
                if related in self.graph:
                    self.graph.add_edge(title, related, type="related")
        
        print(f"Built knowledge graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
    
    def compute_graph_properties(self):
        """Compute basic graph properties using NetworkX"""
        if not self.graph:
            self.build_graph()
        
        properties = {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "density": nx.density(self.graph),
            "is_connected": nx.is_connected(self.graph),
            "num_connected_components": nx.number_connected_components(self.graph),
            "average_clustering": nx.average_clustering(self.graph),
        }
        
        # Compute average shortest path length for connected components
        if properties["is_connected"]:
            properties["average_shortest_path_length"] = nx.average_shortest_path_length(self.graph)
            properties["diameter"] = nx.diameter(self.graph)
        else:
            # Compute for the largest connected component
            largest_cc = max(nx.connected_components(self.graph), key=len)
            largest_subgraph = self.graph.subgraph(largest_cc)
            properties["largest_component_size"] = len(largest_cc)
            properties["largest_component_avg_path_length"] = nx.average_shortest_path_length(largest_subgraph)
            properties["largest_component_diameter"] = nx.diameter(largest_subgraph)
        
        return properties
    
    def compute_centrality_measures(self):
        """Compute various centrality measures for nodes in the graph"""
        if not self.graph:
            self.build_graph()
        
        # Only compute for notes (not tags or paths)
        note_nodes = [n for n, attr in self.graph.nodes(data=True) if attr.get("type") == "note"]
        note_subgraph = self.graph.subgraph(note_nodes)
        
        centrality_measures = {
            "degree": nx.degree_centrality(note_subgraph),
            "betweenness": nx.betweenness_centrality(note_subgraph),
            "closeness": nx.closeness_centrality(note_subgraph),
            "eigenvector": nx.eigenvector_centrality(note_subgraph, max_iter=1000)
        }
        
        # Normalize and combine centrality measures
        combined_centrality = {}
        for node in note_nodes:
            combined_centrality[node] = (
                centrality_measures["degree"].get(node, 0) +
                centrality_measures["betweenness"].get(node, 0) +
                centrality_measures["closeness"].get(node, 0) +
                centrality_measures["eigenvector"].get(node, 0)
            ) / 4
        
        return {
            "individual_measures": centrality_measures,
            "combined_centrality": combined_centrality
        }
    
    def detect_communities(self):
        """Detect communities in the knowledge graph using the Louvain algorithm"""
        if not self.graph:
            self.build_graph()
        
        # Apply the Louvain algorithm
        partition = community_louvain.best_partition(self.graph)
        
        # Group nodes by community
        communities = {}
        for node, community_id in partition.items():
            if community_id not in communities:
                communities[community_id] = []
            communities[community_id].append(node)
        
        # Calculate modularity
        modularity = community_louvain.modularity(partition, self.graph)
        
        return {
            "partition": partition,
            "communities": communities,
            "modularity": modularity,
            "num_communities": len(communities)
        }
    
    def k_core_decomposition(self):
        """Perform k-core decomposition to identify hierarchical structure"""
        if not self.graph:
            self.build_graph()
        
        # Compute the k-core decomposition
        core_numbers = nx.core_number(self.graph)
        
        # Group nodes by core number
        cores = {}
        for node, core in core_numbers.items():
            if core not in cores:
                cores[core] = []
            cores[core].append(node)
        
        # Find the maximum core number
        max_core = max(cores.keys()) if cores else 0
        
        return {
            "core_numbers": core_numbers,
            "cores": cores,
            "max_core": max_core
        }
    
    def analyze_degree_distribution(self):
        """Analyze the degree distribution using power-law fitting"""
        if not self.graph:
            self.build_graph()
        
        # Get degrees
        degrees = [d for _, d in self.graph.degree()]
        
        # Filter out zeros for power law fitting
        non_zero_degrees = [d for d in degrees if d > 0]
        
        if len(non_zero_degrees) < 10:
            return {
                "is_power_law": False,
                "message": "Not enough data points for power-law fitting",
                "degrees": degrees
            }
        
        # Fit power law
        try:
            fit = powerlaw.Fit(non_zero_degrees)
            
            # Compare with alternative distributions
            power_law_vs_exponential = fit.distribution_compare('power_law', 'exponential')
            power_law_vs_lognormal = fit.distribution_compare('power_law', 'lognormal')
            
            return {
                "is_power_law": power_law_vs_exponential[0] > 0 and power_law_vs_lognormal[0] > 0,
                "alpha": fit.alpha,
                "xmin": fit.xmin,
                "power_law_vs_exponential": power_law_vs_exponential,
                "power_law_vs_lognormal": power_law_vs_lognormal,
                "degrees": degrees
            }
        except Exception as e:
            return {
                "is_power_law": False,
                "error": str(e),
                "degrees": degrees
            }
    
    def initialize_embeddings(self, model_name="all-MiniLM-L6-v2"):
        """Initialize the embedding model and compute embeddings for all notes"""
        self.embedding_model = SentenceTransformer(model_name)
        
        # Compute embeddings for all notes
        for title, data in self.index["notes"].items():
            note_path = self.garden_dir / data["path"]
            if note_path.exists():
                with open(note_path, "r") as f:
                    content = f.read()
                    
                # Extract the main content (remove title and metadata)
                content = content.replace(f"# {title}", "").split("---")[0].strip()
                
                # Compute embedding
                self.embeddings[title] = self.embedding_model.encode(content)
        
        print(f"Computed embeddings for {len(self.embeddings)} notes")
    
    def find_semantic_connections(self, threshold=0.7):
        """Find semantic connections between notes based on embeddings"""
        if not self.embedding_model:
            self.initialize_embeddings()
        
        if len(self.embeddings) < 2:
            return []
        
        # Compute pairwise similarities
        titles = list(self.embeddings.keys())
        embeddings_array = np.array([self.embeddings[title] for title in titles])
        similarity_matrix = cosine_similarity(embeddings_array)
        
        # Find pairs above threshold
        connections = []
        for i in range(len(titles)):
            for j in range(i+1, len(titles)):
                if similarity_matrix[i, j] >= threshold:
                    connections.append({
                        "source": titles[i],
                        "target": titles[j],
                        "similarity": similarity_matrix[i, j]
                    })
        
        return connections
    
    def agentic_path_finding(self, start_node, end_node, num_paths=3, randomness=0.3):
        """Find diverse paths between nodes using a modified Dijkstra's algorithm with randomness"""
        if not self.graph:
            self.build_graph()
        
        if start_node not in self.graph or end_node not in self.graph:
            return []
        
        paths = []
        for _ in range(num_paths):
            # Create a copy of the graph with randomized weights
            G = self.graph.copy()
            
            # Assign random weights to edges
            for u, v in G.edges():
                # Base weight is 1.0, add randomness
                weight = 1.0 + random.random() * randomness
                G[u][v]['weight'] = weight
            
            # Try to find a path
            try:
                path = nx.shortest_path(G, start_node, end_node, weight='weight')
                if path not in paths:  # Avoid duplicates
                    paths.append(path)
            except nx.NetworkXNoPath:
                continue
        
        return paths
    
    def extract_subgraph(self, central_node, max_distance=2):
        """Extract a subgraph centered around a node with a maximum distance"""
        if not self.graph:
            self.build_graph()
        
        if central_node not in self.graph:
            return None
        
        # Use BFS to find nodes within max_distance
        nodes = {central_node}
        current_nodes = {central_node}
        
        for _ in range(max_distance):
            next_nodes = set()
            for node in current_nodes:
                next_nodes.update(self.graph.neighbors(node))
            nodes.update(next_nodes)
            current_nodes = next_nodes
        
        # Extract the subgraph
        subgraph = self.graph.subgraph(nodes)
        return subgraph
    
    def visualize_graph(self, output_path=None, show=True):
        """Visualize the knowledge graph using NetworkX and matplotlib"""
        if not self.graph:
            self.build_graph()
        
        # Create a figure
        plt.figure(figsize=(12, 10))
        
        # Define node colors based on type
        node_colors = []
        for node in self.graph.nodes():
            node_type = self.graph.nodes[node].get("type", "unknown")
            if node_type == "note":
                node_colors.append("skyblue")
            elif node_type == "tag":
                node_colors.append("salmon")
            elif node_type == "path":
                node_colors.append("lightgreen")
            else:
                node_colors.append("gray")
        
        # Define node sizes based on degree
        node_sizes = [300 + 100 * self.graph.degree(node) for node in self.graph.nodes()]
        
        # Define edge colors based on type
        edge_colors = []
        for u, v in self.graph.edges():
            edge_type = self.graph.edges[u, v].get("type", "unknown")
            if edge_type == "related":
                edge_colors.append("blue")
            elif edge_type == "tagged":
                edge_colors.append("red")
            elif edge_type == "path":
                edge_colors.append("green")
            else:
                edge_colors.append("gray")
        
        # Use spring layout for node positioning
        pos = nx.spring_layout(self.graph, seed=42)
        
        # Draw the graph
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8)
        nx.draw_networkx_edges(self.graph, pos, edge_color=edge_colors, width=1.5, alpha=0.6)
        nx.draw_networkx_labels(self.graph, pos, font_size=10, font_family="sans-serif")
        
        plt.axis("off")
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def generate_graph_report(self):
        """Generate a comprehensive report on the knowledge graph"""
        if not self.graph:
            self.build_graph()
        
        # Compute various metrics
        properties = self.compute_graph_properties()
        centrality = self.compute_centrality_measures()
        communities = self.detect_communities()
        cores = self.k_core_decomposition()
        degree_distribution = self.analyze_degree_distribution()
        
        # Find top nodes by centrality
        top_nodes = sorted(
            centrality["combined_centrality"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Generate report
        report = {
            "graph_properties": properties,
            "top_central_nodes": top_nodes,
            "community_structure": {
                "num_communities": communities["num_communities"],
                "modularity": communities["modularity"],
                "largest_community_size": max(len(c) for c in communities["communities"].values())
            },
            "hierarchical_structure": {
                "max_core": cores["max_core"],
                "core_distribution": {k: len(v) for k, v in cores["cores"].items()}
            },
            "degree_distribution": {
                "is_power_law": degree_distribution.get("is_power_law", False),
                "alpha": degree_distribution.get("alpha", None),
                "max_degree": max(degree_distribution["degrees"]) if degree_distribution["degrees"] else 0,
                "avg_degree": sum(degree_distribution["degrees"]) / len(degree_distribution["degrees"]) if degree_distribution["degrees"] else 0
            }
        }
        
        return report

def main():
    """Main function to demonstrate the knowledge graph analysis"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge Graph Analysis")
    parser.add_argument("--garden", default="knowledge_garden", help="Directory for the knowledge garden")
    parser.add_argument("--visualize", action="store_true", help="Visualize the knowledge graph")
    parser.add_argument("--report", action="store_true", help="Generate a report on the knowledge graph")
    parser.add_argument("--find-connections", action="store_true", help="Find semantic connections between notes")
    parser.add_argument("--output", type=str, help="Output file for visualization or report")
    
    args = parser.parse_args()
    
    try:
        analyzer = KnowledgeGraphAnalyzer(args.garden)
        
        if args.visualize:
            output_path = args.output if args.output else "knowledge_graph.png"
            analyzer.visualize_graph(output_path=output_path)
            print(f"Graph visualization saved to {output_path}")
        
        if args.report:
            report = analyzer.generate_graph_report()
            
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(report, f, indent=2)
                print(f"Graph report saved to {args.output}")
            else:
                print(json.dumps(report, indent=2))
        
        if args.find_connections:
            connections = analyzer.find_semantic_connections()
            
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(connections, f, indent=2)
                print(f"Semantic connections saved to {args.output}")
            else:
                print(json.dumps(connections, indent=2))
        
        if not (args.visualize or args.report or args.find_connections):
            # Default behavior: print basic graph properties
            properties = analyzer.compute_graph_properties()
            print("Knowledge Graph Properties:")
            print(json.dumps(properties, indent=2))
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 
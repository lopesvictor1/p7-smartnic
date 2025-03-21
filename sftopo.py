import json
#import networkx as nx
#import matplotlib.pyplot as plt

class SFTopo:
    def __init__(self):
        self.topology = {
            "switches": [],
            "links": []
        }

    def add_switch(self, name):
        """Adds a switch to the topology."""
        if name not in self.topology["switches"]:
            self.topology["switches"].append(name)

    def add_link(self, src, dst, link_type="SF"):
        """Adds a link between two nodes."""
        self.topology["links"].append({"src": src, "dst": dst, "type": link_type})

    def to_json(self, file_path=None):
        """Converts the topology to JSON format."""
        json_data = json.dumps(self.topology, indent=4)
        if file_path:
            with open(file_path, "w") as f:
                f.write(json_data)
        return json_data

    def show_topology(self):
        """Prints the topology as text (e.g., s1 --> s2)."""
        print("\nStored Topology:")
        for link in self.topology["links"]:
            print(f"{link['src']} --> {link['dst']} ({link['type']})")

    '''def visualize_topology(self):
        """Displays the topology graphically using NetworkX and Matplotlib."""
        G = nx.Graph()

        # Add nodes
        for switch in self.topology["switches"]:
            G.add_node(switch)

        # Add edges
        for link in self.topology["links"]:
            G.add_edge(link["src"], link["dst"])

        # Draw the graph
        plt.figure(figsize=(8, 6))
        pos = nx.spring_layout(G)  # Positioning algorithm for better visualization
        nx.draw(G, pos, with_labels=True, node_color="lightblue", edge_color="gray", node_size=3000, font_size=10)
        plt.title("SFTopo Network Topology")
        plt.show()'''

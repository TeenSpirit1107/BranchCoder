"""
Graph rendering module
Prints graphs to console using ASCII characters
"""


def render_graph(graph, start_node=None, path=None):
    """
    Print a directed graph using ASCII characters
    
    Parameters:
    graph: dictionary, keys are nodes, values are lists containing tuples of (target_node, weight)
    start_node: starting node (optional)
    path: path list (optional), used to highlight the path
    """
    # Part 1: Print graph structure
    print("=" * 50)
    print("Graph Structure:")
    print("=" * 50)

    path_nodes = set(path) if path else set()

    for node in sorted(graph.keys()):
        node_label = f"Node {node}"
        if start_node is not None and node == start_node:
            node_label += " [Start]"
        if node in path_nodes:
            node_label += " [Path]"
        print(f"\n{node_label}")

        if not graph.get(node):
            print("  └─> (no outgoing edges)")
        else:
            for i, (target, weight) in enumerate(graph[node]):
                is_last = (i == len(graph[node]) - 1)
                prefix = "  └─>" if is_last else "  ├─>"
                target_label = f"Node {target}"
                if target in path_nodes:
                    target_label += " [Path]"
                print(f"{prefix} {target_label} (weight: {weight})")
    print("=" * 50)

    # Part 2: Print adjacency matrix representation
    print("\nAdjacency Matrix Representation:")
    print("=" * 50)

    nodes = sorted(graph.keys())
    n = len(nodes)

    # Header row
    print("     ", end="")
    for node in nodes:
        print(f"{node:4}", end="")
    print()

    # Matrix rows
    for i in nodes:
        print(f"{i:4} ", end="")
        for j in nodes:
            weight = None
            for target, w in graph.get(i, []):
                if target == j:
                    weight = w
                    break
            if weight is not None:
                print(f"{weight:4}", end="")
            elif i == j:
                print(f"{0:4}", end="")
            else:
                print(f"{'-':4}", end="")
        print()
    print("=" * 50)


def render_path(path, distances=None):
    """
    Print the found path
    
    Parameters:
    path: path list
    distances: distance dictionary (optional)
    """
    if not path:
        print("No path found")
        return

    print("=" * 50)
    print("Shortest Path:")
    print("=" * 50)

    path_str = " -> ".join([f"Node {node}" for node in path])
    print(f"Path: {path_str}")

    if distances and path:
        total_distance = distances.get(path[-1], "Unknown")
        print(f"Total Distance: {total_distance}")

    print("=" * 50 + "\n")


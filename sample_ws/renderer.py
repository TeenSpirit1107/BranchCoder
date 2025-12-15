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
    # TODO: Implement the render_graph function
    # Part 1: Print graph structure
    #   1. Print separator line with "="*50 and newline
    #   2. Print "Graph Structure:" header
    #   3. Print another separator line
    #   4. For each node in sorted(graph.keys()):
    #      - Create node_label = f"Node {node}"
    #      - If start_node is not None and node == start_node, append " [Start]" to node_label
    #      - If path exists and node is in path, append " [Path]" to node_label
    #      - Print node_label with newline before it
    #      - If graph[node] is empty, print "  └─> (no outgoing edges)"
    #      - Else, for each edge (target, weight) in graph[node]:
    #        * Determine if it's the last edge: is_last = (i == len(graph[node]) - 1)
    #        * Set prefix = "  └─>" if is_last, else "  ├─>"
    #        * Create target_label = f"Node {target}"
    #        * If path exists and target is in path, append " [Path]" to target_label
    #        * Print "{prefix} {target_label} (weight: {weight})"
    #   5. Print separator line with "="*50 and newline
    #
    # Part 2: Print adjacency matrix representation
    #   1. Print "\nAdjacency Matrix Representation:"
    #   2. Print separator line with "="*50
    #   3. Create nodes = sorted(graph.keys()) and n = len(nodes)
    #   4. Print header row:
    #      - Print 5 spaces with end=""
    #      - For each node, print node number with right alignment and width 4
    #      - Print newline
    #   5. Print matrix rows:
    #      - For each node i in nodes:
    #        * Print i with right alignment, width 4, and a space, with end=""
    #        * For each node j in nodes:
    #          - Check if there's an edge from i to j:
    #            * Initialize weight = None
    #            * Iterate through graph.get(i, []) to find edge to j
    #            * If found, set weight = w and break
    #          - If weight is not None, print weight with right alignment and width 4
    #          - Else:
    #            * If i == j, print 0 with right alignment and width 4
    #            * Else, print '-' with right alignment and width 4
    #        * Print newline after each row
    #   6. Print separator line with "="*50 and newline
    pass


def render_path(path, distances=None):
    """
    Print the found path
    
    Parameters:
    path: path list
    distances: distance dictionary (optional)
    """
    # TODO: Implement the render_path function
    # If path is empty, print "No path found" and return
    # Otherwise:
    #   1. Print a separator line with "="*50
    #   2. Print "Shortest Path:" header
    #   3. Print another separator line
    #   4. Create a path string by joining nodes with " -> " (format: "Node 0 -> Node 1 -> ...")
    #   5. Print the path string with "Path: " prefix
    #   6. If distances dictionary is provided and path is not empty:
    #      - Get the total distance using distances.get(path[-1], "Unknown")
    #      - Print "Total Distance: {total_distance}"
    #   7. Print a final separator line with "="*50 and a newline
    pass


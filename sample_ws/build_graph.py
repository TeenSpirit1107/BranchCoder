"""
Module for building directed graphs
Creates a directed graph with 6 nodes and specifies a start node
"""


def build_graph():
    """
    Build a directed graph with 6 nodes
    Returns: (graph, start_node)
    graph: dictionary, keys are nodes, values are lists containing tuples of (target_node, weight)
    start_node: starting node
    """
    graph = {
        0: [(1, 4), (2, 2)],
        1: [(2, 1), (3, 5)],
        2: [(3, 8), (4, 10)],
        3: [(4, 2), (5, 6)],
        4: [(5, 3)],
        5: []
    }
    start_node = 0
    return (graph, start_node)


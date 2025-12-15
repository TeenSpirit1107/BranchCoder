"""
Algorithm strategy module
Contains various shortest path algorithms: Dijkstra, Floyd, Greedy, etc.
"""

import heapq
from collections import defaultdict


def dijkstra(graph, start, end):
    """
    Dijkstra's algorithm - single-source shortest path
    
    Parameters:
    graph: dictionary, keys are nodes, values are lists containing tuples of (target_node, weight)
    start: starting node
    end: target node
    
    Returns:
    (path, distances): path list and distance dictionary
    """
    # Initialize distance dictionary
    distances = {node: float('inf') for node in graph.keys()}
    distances[start] = 0
    
    # Previous node dictionary, used to reconstruct path
    previous = {node: None for node in graph.keys()}
    
    # Priority queue: (distance, node)
    pq = [(0, start)]
    visited = set()
    
    while pq:
        current_dist, current_node = heapq.heappop(pq)
        
        if current_node in visited:
            continue
        
        visited.add(current_node)
        
        # If reached target node, can exit early
        if current_node == end:
            break
        
        # Traverse neighbor nodes
        for neighbor, weight in graph.get(current_node, []):
            if neighbor in visited:
                continue
            
            new_dist = current_dist + weight
            
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                previous[neighbor] = current_node
                heapq.heappush(pq, (new_dist, neighbor))
    
    # Reconstruct path
    path = []
    if distances[end] != float('inf'):
        current = end
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()
    
    return path, distances


def floyd_warshall(graph):
    """
    Floyd-Warshall algorithm - all-pairs shortest path
    
    Parameters:
    graph: dictionary, keys are nodes, values are lists containing tuples of (target_node, weight)
    
    Returns:
    (distances, paths): distance matrix and path matrix
    """
    nodes = sorted(graph.keys())
    n = len(nodes)
    node_to_index = {node: i for i, node in enumerate(nodes)}
    
    # Initialize distance matrix
    dist = [[float('inf')] * n for _ in range(n)]
    # Initialize path matrix
    next_node = [[None] * n for _ in range(n)]
    
    # Diagonal is 0
    for i in range(n):
        dist[i][i] = 0
    
    # Initialize direct edges
    for u in nodes:
        for v, weight in graph.get(u, []):
            i = node_to_index[u]
            j = node_to_index[v]
            dist[i][j] = weight
            next_node[i][j] = j
    
    # Floyd-Warshall main algorithm
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
                    next_node[i][j] = next_node[i][k]
    
    def get_path(start, end):
        """Reconstruct path based on next_node matrix"""
        if dist[node_to_index[start]][node_to_index[end]] == float('inf'):
            return []
        
        path = [start]
        i = node_to_index[start]
        j = node_to_index[end]
        
        while i != j:
            i = next_node[i][j]
            if i is None:
                return []
            path.append(nodes[i])
        
        return path
    
    return dist, get_path


def greedy_shortest_path(graph, start, end):
    """
    Greedy algorithm - always choose the edge with minimum weight
    
    Parameters:
    graph: dictionary, keys are nodes, values are lists containing tuples of (target_node, weight)
    start: starting node
    end: target node
    
    Returns:
    (path, total_distance): path list and total distance
    """
    # TODO: Implement the greedy_shortest_path function
    # Initialize:
    #   - path = [start]
    #   - current = start
    #   - visited = {start}
    #   - total_distance = 0
    # 
    # While current != end:
    #   1. Find all unvisited neighbors of current node (filter out visited nodes)
    #   2. If no neighbors found, return ([], float('inf'))
    #   3. Use greedy strategy: choose the neighbor with minimum weight using min() with key=lambda x: x[1]
    #   4. Add the chosen node to path, mark it as visited, add weight to total_distance, update current
    # 
    # After loop completes:
    #   - Create distances dictionary where distances[end] = total_distance, others = float('inf')
    #   - Return (path, distances)
    pass


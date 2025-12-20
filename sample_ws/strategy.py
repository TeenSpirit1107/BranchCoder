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
    
    distances = {node: float('inf') for node in graph}
    distances[start] = 0
    previous = {}
    
    priority_queue = [(0, start)]  # (distance, node)

    while priority_queue:
        dist_u, u = heapq.heappop(priority_queue)

        if dist_u > distances[u]:
            continue

        if u == end:
            break  # Optional: early exit if target found

        for v, weight in graph.get(u, []):
            new_dist = dist_u + weight
            if new_dist < distances[v]:
                distances[v] = new_dist
                previous[v] = u
                heapq.heappush(priority_queue, (new_dist, v))

    path = []
    current = end
    while current in previous:
        path.insert(0, current)
        current = previous[current]
    if current == start:
        path.insert(0, start)
    else:
        return ([], {node: float('inf') for node in graph}) # End is unreachable

    return (path, distances)


def floyd_warshall(graph):
    """
    Floyd-Warshall algorithm - all-pairs shortest path
    
    Parameters:
    graph: dictionary, keys are nodes, values are lists containing tuples of (target_node, weight)
    
    Returns:
    (distances, paths): distance matrix and path matrix
    """
    nodes = sorted(list(graph.keys()))
    node_to_index = {node: i for i, node in enumerate(nodes)}
    n = len(nodes)

    dist = [[float('inf')] * n for _ in range(n)]
    next_node = [[None] * n for _ in range(n)]

    for i in range(n):
        dist[i][i] = 0

    for u, edges in graph.items():
        for v, weight in edges:
            i, j = node_to_index[u], node_to_index[v]
            dist[i][j] = weight
            next_node[i][j] = v

    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] != float('inf') and dist[k][j] != float('inf') and dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
                    next_node[i][j] = next_node[i][k]

    def get_path(start, end):
        if start not in node_to_index or end not in node_to_index:
            return []

        i, j = node_to_index[start], node_to_index[end]
        if dist[i][j] == float('inf'):
            return []

        path = [start]
        current = start
        while current != end:
            current = next_node[node_to_index[current]][j]
            if current is None:  # Should not happen if dist[i][j] is not inf, but as a safeguard
                return []
            path.append(current)
        return path

    return (dist, get_path)


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
    path = [start]
    current = start
    visited = {start}
    total_distance = 0

    while current != end:
        unvisited_neighbors = []
        if current in graph:
            for neighbor, weight in graph[current]:
                if neighbor not in visited:
                    unvisited_neighbors.append((neighbor, weight))

        if not unvisited_neighbors:
            return ([], float('inf'))

        # Choose the neighbor with the minimum weight
        next_node, edge_weight = min(unvisited_neighbors, key=lambda x: x[1])

        path.append(next_node)
        visited.add(next_node)
        total_distance += edge_weight
        current = next_node
    
    distances = {end: total_distance}
    return (path, distances)

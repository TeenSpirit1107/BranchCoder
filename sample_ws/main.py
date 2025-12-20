"""
Main program
Users can choose different algorithms to find shortest paths in the graph
"""

from build_graph import build_graph
from renderer import render_graph, render_path
from strategy import dijkstra, floyd_warshall, greedy_shortest_path


def execute_dijkstra(graph, start_node, end_node):
    """Execute Dijkstra's algorithm and display results"""
    print("\nUsing Dijkstra's Algorithm:")
    path, distances = dijkstra(graph, start_node, end_node)
    if path:
        render_graph(graph, start_node, path)
        render_path(path, distances)
    else:
        print(f"Cannot reach node {end_node} from node {start_node}")


def execute_floyd_warshall(graph, start_node, end_node):
    """Execute Floyd-Warshall algorithm and display results"""
    print("\nUsing Floyd-Warshall Algorithm:")
    dist_matrix, get_path = floyd_warshall(graph)
    path = get_path(start_node, end_node)

    nodes = sorted(graph.keys())
    node_to_index = {node: i for i, node in enumerate(nodes)}
    start_idx = node_to_index[start_node]
    end_idx = node_to_index[end_node]
    total_distance = dist_matrix[start_idx][end_idx]

    if path:
        render_graph(graph, start_node, path)
        render_path(path, {end_node: total_distance})

        print("\nAll-Pairs Shortest Path Distance Matrix:")
        print("=" * 50)
        header = "     " + "".join([f"{node:6}" for node in nodes])
        print(header)
        for i, node_i in enumerate(nodes):
            row_str = f"{node_i:<4} "
            for j, node_j in enumerate(nodes):
                if dist_matrix[i][j] == float('inf'):
                    row_str += "   INF"
                else:
                    row_str += f"{dist_matrix[i][j]:6}"
            print(row_str)
        print("=" * 50)
    else:
        print(f"Cannot reach node {end_node} from node {start_node}")


def execute_greedy(graph, start_node, end_node):
    """Execute Greedy algorithm and display results"""
    print("\nUsing Greedy Algorithm:")
    path, distances = greedy_shortest_path(graph, start_node, end_node)
    if path:
        render_graph(graph, start_node, path)
        render_path(path, distances)
    else:
        print(f"Cannot reach node {end_node} from node {start_node}")
        print("Note: Greedy algorithm may not find the optimal solution")


def main():
    """Main function"""
    # Build graph
    graph, start_node = build_graph()
    
    # Display graph structure (only once at the beginning)
    print("\nWelcome to the Shortest Path Algorithm Demo Program!")
    render_graph(graph, start_node)
    
    # Main loop
    while True:
        # Get target node
        print("\nPlease enter target node (0-5) or 'q' to quit: ", end="")
        user_input = input().strip()
        
        # Check if user wants to quit
        if user_input.lower() == 'q':
            print("\nThank you for using the Shortest Path Algorithm Demo Program!")
            break
        
        try:
            end_node = int(user_input)
            if end_node not in graph.keys():
                print(f"Error: Node {end_node} does not exist!")
                continue
        except ValueError:
            print("Error: Please enter a valid number or 'q' to quit!")
            continue
        
        # Display available algorithms
        print("\n" + "="*50)
        print("Available Algorithms:")
        print("="*50)
        print("1. Dijkstra's Algorithm (single-source shortest path, for non-negative weights)")
        print("2. Floyd-Warshall Algorithm (all-pairs shortest path)")
        print("3. Greedy Algorithm (greedy strategy)")
        print("="*50)
        
        # Choose algorithm
        print("\nPlease select an algorithm (1-3) or 'q' to quit: ", end="")
        user_input = input().strip()
        
        # Check if user wants to quit
        if user_input.lower() == 'q':
            print("\nThank you for using the Shortest Path Algorithm Demo Program!")
            break
        
        try:
            choice = int(user_input)
        except ValueError:
            print("Error: Please enter a valid number or 'q' to quit!")
            continue
        
        # Execute selected algorithm
        print("\n" + "="*50)
        print("Execution Results:")
        print("="*50)
        
        if choice == 1:
            execute_dijkstra(graph, start_node, end_node)
        elif choice == 2:
            execute_floyd_warshall(graph, start_node, end_node)
        elif choice == 3:
            execute_greedy(graph, start_node, end_node)
        else:
            print("Error: Invalid choice! Please select 1, 2, or 3.")


if __name__ == "__main__":
    main()

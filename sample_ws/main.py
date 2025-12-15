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
    # TODO: Implement the execute_floyd_warshall function
    # 1. Print "\nUsing Floyd-Warshall Algorithm:"
    # 2. Call floyd_warshall(graph) to get dist_matrix and get_path function
    # 3. Call get_path(start_node, end_node) to get the path
    # 4. Create nodes list by sorting graph.keys()
    # 5. Create node_to_index dictionary mapping node to index
    # 6. Get start_idx and end_idx from node_to_index
    # 7. Get total_distance from dist_matrix[start_idx][end_idx]
    # 8. If path is not empty:
    #    - Call render_graph(graph, start_node, path) to display the graph with path highlighted
    #    - Call render_path(path, {end_node: total_distance}) to display the path and distance
    #    - Display the all-pairs shortest path distance matrix:
    #      * Print "\nAll-Pairs Shortest Path Distance Matrix:"
    #      * Print separator line with "="*50
    #      * Print header row with 5 spaces, then each node number with width 6
    #      * For each row i (node_i):
    #        - Print node_i with width 4 and a space
    #        - For each column j:
    #          * If dist_matrix[i][j] == float('inf'), print "   INF"
    #          * Else, print dist_matrix[i][j] with width 6
    #        - Print newline
    #      * Print separator line with "="*50
    # 9. Else:
    #    - Print error message: "Cannot reach node {end_node} from node {start_node}"
    pass


def execute_greedy(graph, start_node, end_node):
    """Execute Greedy algorithm and display results"""
    # TODO: Implement the execute_greedy function
    # 1. Print "\nUsing Greedy Algorithm:"
    # 2. Call greedy_shortest_path(graph, start_node, end_node) to get path and distances
    # 3. If path is not empty:
    #    - Call render_graph(graph, start_node, path) to display the graph with path highlighted
    #    - Call render_path(path, distances) to display the path and distance
    # 4. Else:
    #    - Print error message: "Cannot reach node {end_node} from node {start_node}"
    #    - Print note: "Note: Greedy algorithm may not find the optimal solution"
    pass


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

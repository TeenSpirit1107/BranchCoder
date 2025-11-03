import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import { ChatPanel } from './ChatPanel';

let chatPanel: ChatPanel | undefined;
let ragInitializationInProgress = false;
let ragUpdateInProgress = false;
let fileWatcher: vscode.FileSystemWatcher | undefined;
let fileChangeDebounceTimer: NodeJS.Timeout | undefined;
const pendingChangedFiles = new Set<string>();
const pendingDeletedFiles = new Set<string>();

// Code file extensions to watch
const CODE_FILE_EXTENSIONS = new Set([
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', 
    '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala'
]);

// Directories to exclude from watching
const EXCLUDE_DIRS = new Set([
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', 
    'build', 'dist', '.rag_store', 'out', '.next', '.cache', 
    'target', '.idea', '.vscode', '.vs'
]);

function isCodeFile(filePath: string): boolean {
    const ext = path.extname(filePath).toLowerCase();
    return CODE_FILE_EXTENSIONS.has(ext);
}

function shouldWatchFile(filePath: string, workspaceDir: string): boolean {
    const relativePath = path.relative(workspaceDir, filePath);
    // Check if file is in excluded directory
    for (const excludedDir of EXCLUDE_DIRS) {
        if (relativePath.includes(excludedDir)) {
            return false;
        }
    }
    return isCodeFile(filePath);
}

function getRelativePath(filePath: string, workspaceDir: string): string {
    return path.relative(workspaceDir, filePath).replace(/\\/g, '/');
}

// Initialize RAG service for the current workspace
async function initializeRAG(workspaceDir: string, extensionPath: string, outputChannel: vscode.OutputChannel): Promise<void> {
    // Prevent concurrent initializations
    if (ragInitializationInProgress) {
        console.log('RAG initialization already in progress, skipping...');
        return;
    }

    ragInitializationInProgress = true;

    return new Promise((resolve, reject) => {
        // Get Python path from configuration
        const config = vscode.workspace.getConfiguration('aiChat');
        let pythonPath = config.get<string>('pythonPath', '.venv/bin/python');
        
        // Resolve relative Python path relative to extension path
        let resolvedPythonPath = pythonPath;
        if (!path.isAbsolute(pythonPath)) {
            resolvedPythonPath = path.join(extensionPath, pythonPath);
        }
        
        // RAG init script path
        const ragInitScriptPath = path.join(extensionPath, 'python', 'rag_init_service.py');
        
        if (!fs.existsSync(ragInitScriptPath)) {
            const errorMsg = `RAG init script not found at: ${ragInitScriptPath}`;
            console.error(errorMsg);
            outputChannel.appendLine(`ERROR: ${errorMsg}`);
            ragInitializationInProgress = false;
            reject(new Error(errorMsg));
            return;
        }

        console.log(`Initializing RAG for workspace: ${workspaceDir}`);
        outputChannel.appendLine(`[RAG Init] Starting RAG initialization for workspace: ${workspaceDir}`);

        // Spawn Python process with extension path as working directory
        // This ensures Python can find the modules in the python/ directory
        const pythonProcess = spawn(resolvedPythonPath, [ragInitScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe'],
            cwd: extensionPath  // Set working directory to extension path
        });

        let output = '';
        let errorOutput = '';

        // Send workspace directory to Python process
        const inputData = JSON.stringify({ workspace_dir: workspaceDir });
        pythonProcess.stdin.write(inputData);
        pythonProcess.stdin.end();

        // Collect output
        pythonProcess.stdout.on('data', (data: Buffer) => {
            output += data.toString();
        });

        // Collect stderr logs
        pythonProcess.stderr.on('data', (data: Buffer) => {
            const logMessage = data.toString();
            errorOutput += logMessage;
            outputChannel.append(logMessage);
        });

        pythonProcess.on('close', (code: number | null) => {
            ragInitializationInProgress = false;
            
            if (code === 0) {
                try {
                    const response = JSON.parse(output.trim());
                    if (response.status === 'success') {
                        console.log('RAG initialization completed successfully');
                        outputChannel.appendLine(`[RAG Init] ✅ Success: ${response.message}`);
                        vscode.window.showInformationMessage(`RAG indexing completed for workspace`);
                        resolve();
                    } else {
                        const errorMsg = response.message || 'RAG initialization failed';
                        console.error('RAG initialization failed:', errorMsg);
                        outputChannel.appendLine(`[RAG Init] ❌ Failed: ${errorMsg}`);
                        vscode.window.showWarningMessage(`RAG initialization failed: ${errorMsg}`);
                        reject(new Error(errorMsg));
                    }
                } catch (e) {
                    const errorMsg = `Failed to parse RAG init response: ${e}`;
                    outputChannel.appendLine(`[RAG Init] ❌ Error: ${errorMsg}`);
                    // Log raw output for debugging if parsing fails
                    if (output) {
                        outputChannel.appendLine(`[RAG Init] Raw output (first 500 chars): ${output.substring(0, 500)}`);
                    }
                    reject(new Error(errorMsg));
                }
            } else {
                const errorMsg = errorOutput || `Python process exited with code ${code}`;
                console.error('RAG initialization error:', errorMsg);
                outputChannel.appendLine(`[RAG Init] ❌ Error (exit code ${code}): ${errorMsg}`);
                vscode.window.showErrorMessage(`RAG initialization failed: ${errorMsg}`);
                outputChannel.show(true);
                reject(new Error(errorMsg));
            }
        });

        pythonProcess.on('error', (error: Error) => {
            ragInitializationInProgress = false;
            const errorMsg = `Failed to start Python process: ${error.message}`;
            console.error('RAG initialization error:', errorMsg);
            outputChannel.appendLine(`ERROR: ${errorMsg}`);
            reject(new Error(errorMsg));
        });

        // Timeout after 5 minutes (RAG indexing can take time)
        setTimeout(() => {
            pythonProcess.kill();
            ragInitializationInProgress = false;
            const errorMsg = 'RAG initialization timed out after 5 minutes';
            outputChannel.appendLine(`ERROR: ${errorMsg}`);
            reject(new Error(errorMsg));
        }, 300000); // 5 minutes
    });
}

// Update RAG service for changed files
async function updateRAG(workspaceDir: string, extensionPath: string, outputChannel: vscode.OutputChannel): Promise<void> {
    // Prevent concurrent updates
    if (ragUpdateInProgress) {
        console.log('RAG update already in progress, skipping...');
        return;
    }

    // Check if we have any files to process
    if (pendingChangedFiles.size === 0 && pendingDeletedFiles.size === 0) {
        return;
    }

    ragUpdateInProgress = true;

    // Convert Sets to Arrays and clear pending sets
    const changedFiles = Array.from(pendingChangedFiles);
    const deletedFiles = Array.from(pendingDeletedFiles);
    pendingChangedFiles.clear();
    pendingDeletedFiles.clear();

    return new Promise((resolve, reject) => {
        // Get Python path from configuration
        const config = vscode.workspace.getConfiguration('aiChat');
        let pythonPath = config.get<string>('pythonPath', '.venv/bin/python');
        
        // Resolve relative Python path relative to extension path
        let resolvedPythonPath = pythonPath;
        if (!path.isAbsolute(pythonPath)) {
            resolvedPythonPath = path.join(extensionPath, pythonPath);
        }
        
        // RAG update script path
        const ragUpdateScriptPath = path.join(extensionPath, 'python', 'rag_update_service.py');
        
        if (!fs.existsSync(ragUpdateScriptPath)) {
            const errorMsg = `RAG update script not found at: ${ragUpdateScriptPath}`;
            console.error(errorMsg);
            outputChannel.appendLine(`ERROR: ${errorMsg}`);
            ragUpdateInProgress = false;
            reject(new Error(errorMsg));
            return;
        }

        console.log(`Updating RAG for workspace: ${workspaceDir}`);
        outputChannel.appendLine(`[RAG Update] Updating ${changedFiles.length} changed files and ${deletedFiles.length} deleted files`);

        // Spawn Python process
        const pythonProcess = spawn(resolvedPythonPath, [ragUpdateScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe'],
            cwd: extensionPath
        });

        let output = '';
        let errorOutput = '';

        // Send workspace directory and file paths to Python process
        const inputData = JSON.stringify({
            workspace_dir: workspaceDir,
            changed_files: changedFiles,
            deleted_files: deletedFiles
        });
        pythonProcess.stdin.write(inputData);
        pythonProcess.stdin.end();

        // Collect output
        pythonProcess.stdout.on('data', (data: Buffer) => {
            output += data.toString();
        });

        // Collect stderr logs
        pythonProcess.stderr.on('data', (data: Buffer) => {
            const logMessage = data.toString();
            errorOutput += logMessage;
            outputChannel.append(logMessage);
        });

        pythonProcess.on('close', (code: number | null) => {
            ragUpdateInProgress = false;
            
            if (code === 0) {
                try {
                    const response = JSON.parse(output.trim());
                    if (response.status === 'success') {
                        console.log('RAG update completed successfully');
                        outputChannel.appendLine(`[RAG Update] ✅ Success: ${response.message}`);
                        resolve();
                    } else {
                        const errorMsg = response.message || 'RAG update failed';
                        console.error('RAG update failed:', errorMsg);
                        outputChannel.appendLine(`[RAG Update] ❌ Failed: ${errorMsg}`);
                        reject(new Error(errorMsg));
                    }
                } catch (e) {
                    const errorMsg = `Failed to parse RAG update response: ${e}`;
                    outputChannel.appendLine(`[RAG Update] ❌ Error: ${errorMsg}`);
                    if (output) {
                        outputChannel.appendLine(`[RAG Update] Raw output (first 500 chars): ${output.substring(0, 500)}`);
                    }
                    reject(new Error(errorMsg));
                }
            } else {
                const errorMsg = errorOutput || `Python process exited with code ${code}`;
                console.error('RAG update error:', errorMsg);
                outputChannel.appendLine(`[RAG Update] ❌ Error (exit code ${code}): ${errorMsg}`);
                reject(new Error(errorMsg));
            }
        });

        pythonProcess.on('error', (error: Error) => {
            ragUpdateInProgress = false;
            const errorMsg = `Failed to start Python process: ${error.message}`;
            console.error('RAG update error:', errorMsg);
            outputChannel.appendLine(`ERROR: ${errorMsg}`);
            reject(new Error(errorMsg));
        });

        // Timeout after 5 minutes
        setTimeout(() => {
            pythonProcess.kill();
            ragUpdateInProgress = false;
            const errorMsg = 'RAG update timed out after 5 minutes';
            outputChannel.appendLine(`ERROR: ${errorMsg}`);
            reject(new Error(errorMsg));
        }, 300000); // 5 minutes
    });
}

// Setup file watcher for a workspace
function setupFileWatcher(workspaceDir: string, extensionPath: string, outputChannel: vscode.OutputChannel): void {
    // Dispose existing watcher if any
    if (fileWatcher) {
        fileWatcher.dispose();
    }

    // Create pattern to watch all code files in workspace
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(workspaceDir));
    if (!workspaceFolder) {
        console.log('No workspace folder found for file watching');
        return;
    }

    // Create file system watcher
    const pattern = new vscode.RelativePattern(workspaceFolder, '**/*');
    fileWatcher = vscode.workspace.createFileSystemWatcher(pattern);

    // Handle file changes
    fileWatcher.onDidChange(async (uri: vscode.Uri) => {
        const filePath = uri.fsPath;
        if (shouldWatchFile(filePath, workspaceDir)) {
            const relativePath = getRelativePath(filePath, workspaceDir);
            console.log(`File changed: ${relativePath}`);
            pendingChangedFiles.add(relativePath);
            
            // Clear existing timer and set new one (debounce)
            if (fileChangeDebounceTimer) {
                clearTimeout(fileChangeDebounceTimer);
            }
            
            // Wait 1 second before triggering update (debounce)
            fileChangeDebounceTimer = setTimeout(() => {
                updateRAG(workspaceDir, extensionPath, outputChannel).catch((error: any) => {
                    console.error('Failed to update RAG:', error);
                });
            }, 1000);
        }
    });

    // Handle file creation
    fileWatcher.onDidCreate(async (uri: vscode.Uri) => {
        const filePath = uri.fsPath;
        if (shouldWatchFile(filePath, workspaceDir)) {
            const relativePath = getRelativePath(filePath, workspaceDir);
            console.log(`File created: ${relativePath}`);
            pendingChangedFiles.add(relativePath);
            
            // Clear existing timer and set new one (debounce)
            if (fileChangeDebounceTimer) {
                clearTimeout(fileChangeDebounceTimer);
            }
            
            // Wait 1 second before triggering update (debounce)
            fileChangeDebounceTimer = setTimeout(() => {
                updateRAG(workspaceDir, extensionPath, outputChannel).catch((error: any) => {
                    console.error('Failed to update RAG:', error);
                });
            }, 1000);
        }
    });

    // Handle file deletion
    fileWatcher.onDidDelete(async (uri: vscode.Uri) => {
        const filePath = uri.fsPath;
        if (shouldWatchFile(filePath, workspaceDir)) {
            const relativePath = getRelativePath(filePath, workspaceDir);
            console.log(`File deleted: ${relativePath}`);
            pendingDeletedFiles.add(relativePath);
            // Also remove from changed files if it was there
            pendingChangedFiles.delete(relativePath);
            
            // Clear existing timer and set new one (debounce)
            if (fileChangeDebounceTimer) {
                clearTimeout(fileChangeDebounceTimer);
            }
            
            // Wait 1 second before triggering update (debounce)
            fileChangeDebounceTimer = setTimeout(() => {
                updateRAG(workspaceDir, extensionPath, outputChannel).catch((error: any) => {
                    console.error('Failed to update RAG:', error);
                });
            }, 1000);
        }
    });

    console.log(`File watcher set up for workspace: ${workspaceDir}`);
}

export function activate(context: vscode.ExtensionContext) {
    console.log('AI Chat Extension is activating...');
    
    // Create output channel for AI service logs
    const outputChannel = vscode.window.createOutputChannel('AI Service');
    
    // Dispose output channel when extension deactivates
    context.subscriptions.push(outputChannel);

    // Initialize RAG when workspace is opened
    const initializeRAGForWorkspace = async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            // Use the first workspace folder
            const workspaceDir = workspaceFolders[0].uri.fsPath;
            console.log(`Workspace detected: ${workspaceDir}`);
            
            try {
                await initializeRAG(workspaceDir, context.extensionPath, outputChannel);
                // Setup file watcher after successful initialization
                setupFileWatcher(workspaceDir, context.extensionPath, outputChannel);
            } catch (error: any) {
                console.error('Failed to initialize RAG:', error);
                // Don't show error to user as this might be expected in some cases
            }
        } else {
            console.log('No workspace folder detected, skipping RAG initialization');
        }
    };

    // Initialize RAG on activation if workspace is already open
    initializeRAGForWorkspace();

    // Listen for workspace folder changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeWorkspaceFolders(async (event) => {
            console.log('Workspace folders changed');
            // When workspace folders are added, initialize RAG for new folders
            if (event.added.length > 0) {
                for (const folder of event.added) {
                    const workspaceDir = folder.uri.fsPath;
                    console.log(`New workspace folder added: ${workspaceDir}`);
                    try {
                        await initializeRAG(workspaceDir, context.extensionPath, outputChannel);
                        // Setup file watcher after successful initialization
                        setupFileWatcher(workspaceDir, context.extensionPath, outputChannel);
                    } catch (error: any) {
                        console.error(`Failed to initialize RAG for ${workspaceDir}:`, error);
                    }
                }
            }
        })
    );

    // Dispose file watcher when extension deactivates
    context.subscriptions.push({
        dispose: () => {
            if (fileWatcher) {
                fileWatcher.dispose();
            }
            if (fileChangeDebounceTimer) {
                clearTimeout(fileChangeDebounceTimer);
            }
        }
    });
    
    // Register the chat view
    const provider = new ChatViewProvider(context.extensionUri, context.extensionPath, outputChannel);
    
    try {
        const registration = vscode.window.registerWebviewViewProvider(
            ChatViewProvider.viewType, 
            provider, 
            {
                webviewOptions: {
                    retainContextWhenHidden: true
                }
            }
        );
        
        context.subscriptions.push(registration);
        console.log('AI Chat Extension registered view provider:', ChatViewProvider.viewType);
        
        // Verify view type matches
        const fullViewId = `aiChat.chatView`;
        if (ChatViewProvider.viewType !== fullViewId) {
            console.warn('View type mismatch:', ChatViewProvider.viewType, 'vs', fullViewId);
        }
    } catch (error) {
        console.error('Failed to register AI Chat view provider:', error);
        vscode.window.showErrorMessage(`AI Chat Extension failed to activate: ${error}`);
    }

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('aiChat.openChat', async () => {
            try {
                // First ensure the view container is shown
                await vscode.commands.executeCommand('workbench.view.extension.aiChat');
                // Give VS Code a moment to resolve the view
                await new Promise(resolve => setTimeout(resolve, 100));
                // Show the chat view if it exists
                if (provider._view) {
                    provider._view.show(true);
                }
            } catch (error) {
                console.error('Error opening AI Chat view:', error);
                vscode.window.showErrorMessage(`Failed to open AI Chat: ${error}`);
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('aiChat.sendMessage', () => {
            provider.sendMessage();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('aiChat.clearChat', () => {
            provider.clearChat();
        })
    );
}

export function deactivate() {
    if (chatPanel) {
        chatPanel.dispose();
    }
}

class ChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aiChat.chatView';
    public _view?: vscode.WebviewView;
    private chatPanel?: ChatPanel;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _extensionPath: string,
        private readonly _outputChannel: vscode.OutputChannel,
    ) { }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        console.log('Resolving webview view:', ChatViewProvider.viewType);
        
        try {
            this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri
            ]
        };

        // Create chat panel and set initial content
        this.chatPanel = new ChatPanel(webviewView.webview, this._extensionUri, this._extensionPath, this._outputChannel);
        this.chatPanel.update();

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(
            async (message: { command: string; text?: string }) => {
                switch (message.command) {
                    case 'sendMessage':
                        if (message.text) {
                            await this.chatPanel?.sendMessage(message.text);
                        }
                        return;
                    case 'clearChat':
                        this.chatPanel?.clearChat();
                        return;
                }
            },
            null,
            []
        );
        } catch (error) {
            console.error('Error in resolveWebviewView:', error);
            vscode.window.showErrorMessage(`Failed to resolve AI Chat view: ${error}`);
        }
    }

    public sendMessage() {
        if (this._view) {
            this._view.webview.postMessage({ command: 'focusInput' });
        }
    }

    public clearChat() {
        this.chatPanel?.clearChat();
    }
}


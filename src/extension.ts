import * as vscode from 'vscode';
import { ChatPanel } from './ChatPanel';

let chatPanel: ChatPanel | undefined;

export function activate(context: vscode.ExtensionContext) {
    console.log('AI Chat Extension is activating...');
    
    // Register the chat view
    const provider = new ChatViewProvider(context.extensionUri, context.extensionPath);
    
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
        this.chatPanel = new ChatPanel(webviewView.webview, this._extensionUri, this._extensionPath);
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


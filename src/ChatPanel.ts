import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';

export class ChatPanel {
    private chatHistory: Array<{ role: string; content: string }> = [];

    constructor(
        private readonly webview: vscode.Webview,
        private readonly extensionUri: vscode.Uri,
        private readonly extensionPath?: string,
        private readonly outputChannel?: vscode.OutputChannel
    ) {
        // Don't update here, wait for webview to be ready
    }

    public async sendMessage(userMessage: string) {
        if (!userMessage.trim()) {
            return;
        }

        // Add user message to history
        this.chatHistory.push({ role: 'user', content: userMessage });
        this.update();

        // Show loading indicator
        this.webview.postMessage({
            command: 'addMessage',
            role: 'assistant',
            content: '',
            isLoading: true
        });

        try {
            // Call Python AI service
            const aiResponse = await this.callPythonAI(userMessage);
            
            // Remove loading indicator and add actual response
            this.chatHistory.push({ role: 'assistant', content: aiResponse });
            this.update();
        } catch (error: any) {
            const errorMessage = error.message || 'Failed to get AI response';
            this.chatHistory.push({ 
                role: 'assistant', 
                content: `Error: ${errorMessage}` 
            });
            this.update();
        }
    }

    public clearChat() {
        this.chatHistory = [];
        this.update();
    }

    public dispose() {
        // Cleanup if needed
    }

    private async callPythonAI(message: string): Promise<string> {
        return new Promise((resolve, reject) => {
            // Get Python AI script path from configuration
            const config = vscode.workspace.getConfiguration('aiChat');
            const pythonPath = config.get<string>('pythonPath', 'python3');
            // Get extension path - use the provided extensionPath directly
            let extPath = this.extensionPath;
            if (!extPath) {
                // Fallback: try to get path from extensionUri
                if (this.extensionUri.scheme === 'file') {
                    extPath = path.dirname(path.dirname(this.extensionUri.fsPath));
                } else {
                    reject(new Error('Extension path is not set and cannot be determined'));
                    return;
                }
            }
            const defaultScriptPath = path.join(
                extPath,
                'python',
                'ai_service.py'
            );
            console.log('Extension path:', extPath);
            console.log('Python script path:', defaultScriptPath);
            console.log('Script exists:', fs.existsSync(defaultScriptPath));
            if (!fs.existsSync(defaultScriptPath)) {
                console.error('Python script not found at:', defaultScriptPath);
            }
            let aiScriptPath = config.get<string>('aiScriptPath');
            if (!aiScriptPath) {
                aiScriptPath = defaultScriptPath;
            }
            // Resolve relative paths relative to extension path
            if (!path.isAbsolute(aiScriptPath)) {
                aiScriptPath = path.join(extPath, aiScriptPath);
            }
            console.log('Using Python script:', aiScriptPath);

            // Spawn Python process
            const pythonProcess = spawn(pythonPath, [aiScriptPath], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let output = '';
            let errorOutput = '';

            // Add separator to output channel for this request
            if (this.outputChannel) {
                const timestamp = new Date().toLocaleString();
                this.outputChannel.appendLine(`\n${'='.repeat(80)}`);
                this.outputChannel.appendLine(`[${timestamp}] Processing request: ${message.substring(0, 50)}${message.length > 50 ? '...' : ''}`);
                this.outputChannel.appendLine('='.repeat(80));
            }

            // Send message to Python process
            pythonProcess.stdin.write(JSON.stringify({
                message: message,
                history: this.chatHistory.slice(0, -1) // Send history except current message
            }));
            pythonProcess.stdin.end();

            // Collect output
            pythonProcess.stdout.on('data', (data: Buffer) => {
                output += data.toString();
            });

            // Send stderr logs to OutputChannel
            pythonProcess.stderr.on('data', (data: Buffer) => {
                const logMessage = data.toString();
                errorOutput += logMessage;
                
                // Output to VS Code OutputChannel for better visibility
                if (this.outputChannel) {
                    this.outputChannel.append(logMessage);
                }
            });

            pythonProcess.on('close', (code: number | null) => {
                if (code === 0) {
                    try {
                        const response = JSON.parse(output.trim());
                        if (this.outputChannel) {
                            this.outputChannel.appendLine(`[SUCCESS] Request completed successfully\n`);
                        }
                        resolve(response.response || response.message || output.trim());
                    } catch (e) {
                        if (this.outputChannel) {
                            this.outputChannel.appendLine(`[ERROR] Error parsing JSON response: ${e}\n`);
                        }
                        resolve(output.trim());
                    }
                } else {
                    const errorMsg = errorOutput || `Python process exited with code ${code}`;
                    if (this.outputChannel) {
                        this.outputChannel.appendLine(`[ERROR] Python process error (exit code ${code}): ${errorMsg}\n`);
                        this.outputChannel.show(true); // Show output channel on error
                    }
                    reject(new Error(errorMsg));
                }
            });

            pythonProcess.on('error', (error: Error) => {
                const errorMsg = `Failed to start Python process: ${error.message}`;
                if (this.outputChannel) {
                    this.outputChannel.appendLine(`ERROR: ${errorMsg}`);
                }
                reject(new Error(errorMsg));
            });

            // Timeout after 30 seconds
            setTimeout(() => {
                pythonProcess.kill();
                reject(new Error('AI request timed out'));
            }, 30000);
        });
    }

    public update() {
        const webview = this.webview;
        webview.html = this.getHtmlForWebview(webview);
    }

    private getHtmlForWebview(webview: vscode.Webview) {
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.extensionUri, 'media', 'chat.css')
        );

        const nonce = this.getNonce();

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="${styleUri}" rel="stylesheet">
                <title>AI Chat</title>
            </head>
            <body>
                <div class="chat-container">
                    <div class="chat-messages" id="chatMessages">
                        ${this.chatHistory.map(msg => `
                            <div class="message ${msg.role}">
                                <div class="message-content">${this.escapeHtml(msg.content)}</div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="chat-input-container">
                        <textarea 
                            id="messageInput" 
                            placeholder="Type your message here..."
                            rows="2"
                        ></textarea>
                        <button id="sendButton">Send</button>
                    </div>
                </div>
                <script nonce="${nonce}">
                    const vscode = acquireVsCodeApi();
                    const chatHistory = ${JSON.stringify(this.chatHistory)};
                    
                    const chatMessages = document.getElementById('chatMessages');
                    const messageInput = document.getElementById('messageInput');
                    const sendButton = document.getElementById('sendButton');
                    
                    function scrollToBottom() {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    
                    function sendMessage() {
                        const text = messageInput.value.trim();
                        if (text) {
                            vscode.postMessage({
                                command: 'sendMessage',
                                text: text
                            });
                            messageInput.value = '';
                        }
                    }
                    
                    sendButton.addEventListener('click', sendMessage);
                    messageInput.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            sendMessage();
                        }
                    });
                    
                    // Handle messages from extension
                    window.addEventListener('message', event => {
                        const message = event.data;
                        switch (message.command) {
                            case 'addMessage':
                                const messageDiv = document.createElement('div');
                                messageDiv.className = \`message \${message.role}\`;
                                messageDiv.innerHTML = \`<div class="message-content">\${message.isLoading ? '<em>Thinking...</em>' : message.content}</div>\`;
                                chatMessages.appendChild(messageDiv);
                                scrollToBottom();
                                break;
                            case 'focusInput':
                                messageInput.focus();
                                break;
                            case 'clearMessages':
                                chatMessages.innerHTML = '';
                                break;
                        }
                    });
                    
                    // Initial scroll
                    scrollToBottom();
                </script>
            </body>
            </html>`;
    }

    private escapeHtml(text: string): string {
        const map: { [key: string]: string } = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]).replace(/\n/g, '<br>');
    }

    private getNonce() {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }
}


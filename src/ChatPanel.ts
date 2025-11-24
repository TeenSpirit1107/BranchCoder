import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import { marked } from 'marked';
import { applyPatchToText } from './patchUtils';

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

        try {
            // Call Python AI service (events will be streamed and displayed automatically)
            const aiResponse = await this.callPythonAI(userMessage);
            
            // Add final response to history
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

    private async handleApplyPatchToolCall(msg: any): Promise<void> {
        try {
            const toolArgs = msg.tool_args || {};
            const patchContent = toolArgs.patch_content;
            const targetFilePath = toolArgs.target_file_path;

            if (!patchContent || !targetFilePath) {
                console.warn('apply_patch tool_call missing required parameters');
                return;
            }

            // Resolve target file URI
            let targetUri: vscode.Uri;
            if (path.isAbsolute(targetFilePath)) {
                targetUri = vscode.Uri.file(targetFilePath);
            } else {
                // Relative path - resolve from workspace
                const workspaceFolders = vscode.workspace.workspaceFolders;
                if (!workspaceFolders || workspaceFolders.length === 0) {
                    throw new Error('No workspace folder found');
                }
                const workspaceDir = workspaceFolders[0].uri.fsPath;
                targetUri = vscode.Uri.file(path.join(workspaceDir, targetFilePath));
            }

            // Read current file content as beforeText
            let beforeText: string;
            try {
                const doc = await vscode.workspace.openTextDocument(targetUri);
                beforeText = doc.getText();
            } catch (error: any) {
                // File might not exist yet - use empty string
                if (error.code === 'ENOENT' || error.message.includes('not found')) {
                    beforeText = '';
                } else {
                    throw error;
                }
            }

            // Apply patch to generate afterText
            const afterText = applyPatchToText(beforeText, patchContent, targetFilePath);

            // Show patch preview
            await vscode.commands.executeCommand(
                'aiChat.showPatchPreview',
                targetUri,
                beforeText,
                afterText,
                patchContent
            );
        } catch (error: any) {
            console.error('Error handling apply_patch tool_call:', error);
            if (this.outputChannel) {
                this.outputChannel.appendLine(`[ERROR] Failed to handle apply_patch: ${error.message}`);
            }
            vscode.window.showErrorMessage(`Failed to show patch preview: ${error.message}`);
        }
    }

    private async callPythonAI(message: string): Promise<string> {
        return new Promise((resolve, reject) => {
            // Get Python AI script path from configuration
            const config = vscode.workspace.getConfiguration('aiChat');
            let pythonPath = config.get<string>('pythonPath', '.venv/bin/python');
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

            // Resolve relative Python path relative to extension path
            let resolvedPythonPath = pythonPath;
            if (!path.isAbsolute(pythonPath)) {
                resolvedPythonPath = path.join(extPath, pythonPath);
            }
            console.log('Using Python interpreter:', resolvedPythonPath);

            // Spawn Python process
            const pythonProcess = spawn(resolvedPythonPath, [aiScriptPath], {
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

            // Get workspace directory
            const workspaceFolders = vscode.workspace.workspaceFolders;
            const workspaceDir = workspaceFolders && workspaceFolders.length > 0 
                ? workspaceFolders[0].uri.fsPath 
                : undefined;

            // Send message to Python process
            const requestData: any = {
                message: message,
                history: this.chatHistory.slice(0, -1) // Send history except current message
            };
            
            // Add workspace_dir if available
            if (workspaceDir) {
                requestData.workspace_dir = workspaceDir;
            }
            
            pythonProcess.stdin.write(JSON.stringify(requestData));
            pythonProcess.stdin.end();

            // Buffer for incomplete lines
            let buffer = '';
            let finalMessage = '';

            // Collect output line by line (streaming JSON)
            pythonProcess.stdout.on('data', (data: Buffer) => {
                buffer += data.toString();
                const lines = buffer.split('\n');
                // Keep the last incomplete line in buffer
                buffer = lines.pop() || '';

                // Process each complete line
                for (const line of lines) {
                    if (!line.trim()) continue;
                    
                    try {
                        const msg = JSON.parse(line);
                        // Directly pass the event to frontend, no transformation needed
                        this.webview.postMessage({
                            command: 'addEvent',
                            event: msg
                        });

                        // Handle apply_patch tool_call - show preview
                        if (msg.type === 'tool_call' && msg.tool_name === 'apply_patch') {
                            this.handleApplyPatchToolCall(msg).catch(error => {
                                console.error('Error handling apply_patch tool_call:', error);
                                if (this.outputChannel) {
                                    this.outputChannel.appendLine(`[ERROR] Failed to handle apply_patch: ${error.message}`);
                                }
                            });
                        }

                        // Track final message for history
                        if (msg.type === 'final_message') {
                            finalMessage = msg.message || '';
                        }
                    } catch (e) {
                        // If JSON parsing fails, log but continue
                        if (this.outputChannel) {
                            this.outputChannel.appendLine(`[WARN] Failed to parse message line: ${line}`);
                        }
                    }
                }
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
                    // Process any remaining buffer
                    if (buffer.trim()) {
                        try {
                            const msg = JSON.parse(buffer.trim());
                            this.webview.postMessage({
                                command: 'addEvent',
                                event: msg
                            });
                            if (msg.type === 'final_message' && msg.message) {
                                finalMessage = msg.message;
                            }
                        } catch (e) {
                            // Ignore parse errors for remaining buffer
                        }
                    }

                    if (this.outputChannel) {
                        this.outputChannel.appendLine(`[SUCCESS] Request completed successfully\n`);
                    }
                    
                    // Resolve with final message (or empty if none)
                    resolve(finalMessage || '');
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

            // // Timeout after 30 seconds
            // setTimeout(() => {
            //     pythonProcess.kill();
            //     reject(new Error('AI request timed out'));
            // }, 30000);
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

        // Configure marked options for better security and rendering
        marked.setOptions({
            breaks: true,
            gfm: true,
        });

        // Get marked library script content
        const markedScript = this.getMarkedScript(webview);

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
                                <div class="message-content">${this.renderMarkdown(msg.content)}</div>
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
                    ${markedScript}
                    
                    const vscode = acquireVsCodeApi();
                    const chatHistory = ${JSON.stringify(this.chatHistory)};
                    
                    const chatMessages = document.getElementById('chatMessages');
                    const messageInput = document.getElementById('messageInput');
                    const sendButton = document.getElementById('sendButton');
                    
                    // Markdown renderer function
                    function renderMarkdown(text) {
                        if (!text || typeof text !== 'string') {
                            return '';
                        }
                        try {
                            if (typeof marked !== 'undefined') {
                                return marked.parse(text);
                            } else {
                                // Fallback: simple markdown-like rendering
                                const backtick = String.fromCharCode(96);
                                return text
                                    .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
                                    .replace(/\\*([^*]+)\\*/g, '<em>$1</em>')
                                    .replace(new RegExp(backtick + '([^' + backtick + ']+)' + backtick, 'g'), '<code>$1</code>')
                                    .replace(/\\n/g, '<br>');
                            }
                        } catch (e) {
                            console.error('Markdown rendering error:', e);
                            return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\\n/g, '<br>');
                        }
                    }
                    
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
                        const data = event.data;
                        switch (data.command) {
                            case 'addEvent':
                                // Directly render backend event
                                const evt = data.event;
                                const msgDiv = document.createElement('div');
                                let className = 'message assistant';
                                
                                // Add CSS class based on event type
                                if (evt.type === 'tool_call') {
                                    className += ' tool-call';
                                } else if (evt.type === 'tool_result') {
                                    className += ' tool-result';
                                }
                                
                                msgDiv.className = className;
                                
                                // Build content based on event type
                                let contentHtml = '';
                                if (evt.type === 'tool_call' || evt.type === 'tool_result') {
                                    const toolName = evt.tool_name || 'unknown';
                                    const toolLabel = evt.type === 'tool_call' ? '🔧 调用工具' : '✅ 工具完成';
                                    contentHtml = \`<div class="tool-header"><strong>\${toolLabel}:</strong> <code>\${toolName}</code></div>\`;
                                    if (evt.message) {
                                        contentHtml += \`<div class="tool-message">\${renderMarkdown(evt.message)}</div>\`;
                                    }
                                } else {
                                    // Normal message (notification_message or final_message)
                                    if (evt.type === 'notification_message') {
                                        contentHtml = '<em>' + (evt.message || 'Thinking...') + '</em>';
                                    } else {
                                        contentHtml = renderMarkdown(evt.message || '');
                                    }
                                }
                                
                                msgDiv.innerHTML = \`<div class="message-content">\${contentHtml}</div>\`;
                                chatMessages.appendChild(msgDiv);
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

    private renderMarkdown(text: string): string {
        if (!text) {
            return '';
        }
        try {
            // Configure marked for rendering
            marked.setOptions({
                breaks: true,
                gfm: true,
            });
            const result = marked.parse(text);
            // marked.parse can return string or Promise<string>
            // For our use case, we expect synchronous rendering
            return typeof result === 'string' ? result : String(result);
        } catch (error) {
            // Fallback to HTML escaping if markdown parsing fails
            return this.escapeHtml(text);
        }
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

    private getMarkedScript(webview: vscode.Webview): string {
        // Try to read marked from node_modules (different possible locations)
        const possiblePaths = [
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'lib', 'marked.esm.js'),
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'lib', 'marked.umd.js'),
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'marked.min.js'),
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'marked.js'),
        ];
        
        for (const markedPath of possiblePaths) {
            try {
                if (fs.existsSync(markedPath)) {
                    const markedContent = fs.readFileSync(markedPath, 'utf-8');
                    // Wrap UMD/ESM code to work in webview context
                    if (markedPath.includes('.umd.js')) {
                        return markedContent;
                    } else if (markedPath.includes('.esm.js')) {
                        // For ESM, we need to create a simple wrapper
                        // Actually, let's use a simpler inline markdown parser for webviews
                        return this.getInlineMarkdownParser();
                    } else {
                        return markedContent;
                    }
                }
            } catch (error) {
                // Continue to next path
            }
        }
        
        // Fallback: use inline markdown parser
        return this.getInlineMarkdownParser();
    }

    private getInlineMarkdownParser(): string {
        // Simple but effective markdown parser for common cases
        // Use string concatenation to avoid template literal escaping issues
        return [
            '// Simple Markdown parser',
            '(function() {',
            '    const Marked = {};',
            '    ',
            '    Marked.parse = function(text) {',
            '        if (!text) return "";',
            '        ',
            '        let html = text;',
            '        ',
            '        // Store code blocks temporarily to avoid escaping them',
            '        const codeBlocks = [];',
            '        const inlineCodes = [];',
            '        const backtick = String.fromCharCode(96);',
            '        const backtick3 = backtick + backtick + backtick;',
            '        html = html.replace(new RegExp(backtick3 + \'([\\\\s\\\\S]*?)\' + backtick3, \'g\'), function(match, code) {',
            "            const placeholder = '___CODE_BLOCK_' + codeBlocks.length + '___';",
            "            codeBlocks.push('<pre><code>' + escapeHtml(code.trim()) + '</code></pre>');",
            '            return placeholder;',
            '        });',
            '        ',
            '        // Store inline code temporarily',
            '        html = html.replace(new RegExp(backtick + \'([^\' + backtick + \'\\\\n]+)\' + backtick, \'g\'), function(match, code) {',
            "            const placeholder = '___INLINE_CODE_' + inlineCodes.length + '___';",
            "            inlineCodes.push('<code>' + escapeHtml(code) + '</code>');",
            '            return placeholder;',
            '        });',
            '        ',
            '        // Now escape HTML to prevent XSS',
            '        html = escapeHtml(html);',
            '        ',
            '        // Restore code blocks and inline code',
            '        codeBlocks.forEach(function(block, index) {',
            "            html = html.replace('___CODE_BLOCK_' + index + '___', block);",
            '        });',
            '        inlineCodes.forEach(function(code, index) {',
            "            html = html.replace('___INLINE_CODE_' + index + '___', code);",
            '        });',
            '        ',
            '        // Headers (process before other formatting)',
            "        html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>');",
            "        html = html.replace(/^## (.*)$/gm, '<h2>$1</h2>');",
            "        html = html.replace(/^# (.*)$/gm, '<h1>$1</h1>');",
            '        ',
            '        // Horizontal rules',
            "        html = html.replace(/^---$/gm, '<hr>');",
            "        html = html.replace(/^\\*\\*\\*$/gm, '<hr>');",
            '        ',
            '        // Lists (unordered) - process line by line',
            '        const lines = html.split(\'\\n\');',
            '        const result = [];',
            '        let inList = false;',
            '        ',
            '        for (let i = 0; i < lines.length; i++) {',
            '            const line = lines[i];',
            "            const listMatch = line.match(/^(\\*|-)\\s+(.+)$/);",
            '            ',
            '            if (listMatch) {',
            "                if (!inList) {",
            "                    result.push('<ul>');",
            '                    inList = true;',
            '                }',
            "                result.push('<li>' + listMatch[2] + '</li>');",
            '            } else {',
            '                if (inList) {',
            "                    result.push('</ul>');",
            '                    inList = false;',
            '                }',
            '                result.push(line);',
            '            }',
            '        }',
            '        ',
            '        if (inList) {',
            "            result.push('</ul>');",
            '        }',
            '        ',
            '        html = result.join(\'\\n\');',
            '        ',
            '        // Bold (avoid conflicts with code)',
            "        html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');",
            "        html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');",
            '        ',
            '        // Italic (avoid conflicts with bold)',
            "        html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');",
            "        html = html.replace(/_([^_]+)_/g, '<em>$1</em>');",
            '        ',
            '        // Links [text](url)',
            "        html = html.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g, '<a href=\"$2\" target=\"_blank\" rel=\"noopener noreferrer\">$1</a>');",
            '        ',
            '        // Paragraphs and line breaks',
            "        html = html.replace(/\\n\\n+/g, '</p><p>');",
            "        html = '<p>' + html + '</p>';",
            "        html = html.replace(/\\n/g, '<br>');",
            '        ',
            '        // Clean up empty paragraphs and fix block elements',
            "        html = html.replace(/<p><\\/p>/g, '');",
            "        html = html.replace(/<p>(<[^>]+>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<h[1-6]>)/g, '$1');",
            "        html = html.replace(/(<\\/h[1-6]>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<pre>)/g, '$1');",
            "        html = html.replace(/(<\\/pre>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<ul>)/g, '$1');",
            "        html = html.replace(/(<\\/ul>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<hr>)/g, '$1');",
            "        html = html.replace(/(<hr>)<\\/p>/g, '$1');",
            '        ',
            '        return html;',
            '    };',
            '    ',
            '    function escapeHtml(text) {',
            '        const map = {',
            "            '&': '&amp;',",
            "            '<': '&lt;',",
            "            '>': '&gt;',",
            '            \'"\': \'&quot;\',',
            "            \"'\": '&#039;'",
            '        };',
            "        return text.replace(/[&<>\"']/g, function(m) { return map[m]; });",
            '    }',
            '    ',
            '    window.marked = Marked;',
            '})();'
        ].join('\n');
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


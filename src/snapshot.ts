import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

/**
 * Get workspace storage path (same logic as Python's get_workspace_storage_path)
 * This function should be called from extension.ts which has access to extensionPath
 */
export function getWorkspaceStoragePath(workspaceDir: string, extensionPath: string): string {
    const workspacePath = path.resolve(workspaceDir);
    const hash = crypto.createHash('md5').update(workspacePath).digest('hex').substring(0, 12);
    
    // Find python directory relative to extension path
    const pythonDir = path.join(extensionPath, 'python');
    const ragStoreDir = path.join(pythonDir, '.rag_store');
    const workspaceStorageDir = path.join(ragStoreDir, `workspace_${hash}`);
    
    return workspaceStorageDir;
}

export interface FileSnapshot {
    path: string;  // Relative path
    hash: string;  // File content hash
    mtime?: number; // File modification time (optional, for faster comparison)
}

export interface Snapshot {
    files: Map<string, FileSnapshot>;  // key: relative path
    timestamp: number;
}

/**
 * Compute MD5 hash of a file
 */
async function computeFileHash(fileUri: vscode.Uri): Promise<string | null> {
    try {
        const content = await vscode.workspace.fs.readFile(fileUri);
        const hash = crypto.createHash('md5').update(content).digest('hex');
        return hash;
    } catch (error) {
        console.error(`Failed to compute hash for ${fileUri.fsPath}:`, error);
        return null;
    }
}

/**
 * Get file stat (modification time)
 */
async function getFileStat(fileUri: vscode.Uri): Promise<{ mtime: number } | null> {
    try {
        const stat = await vscode.workspace.fs.stat(fileUri);
        return { mtime: stat.mtime };
    } catch (error) {
        return null;
    }
}

/**
 * Create a snapshot of all code files in workspace
 */
export async function createSnapshot(
    workspaceDir: string,
    excludePattern: string = '**/{node_modules,.git,__pycache__,.venv,venv,env,build,dist,.rag_store,out,.next,.cache,target,.idea,.vscode,.vs}/**'
): Promise<Snapshot> {
    const workspaceUri = vscode.Uri.file(workspaceDir);
    const snapshot: Snapshot = {
        files: new Map(),
        timestamp: Date.now()
    };

    console.log(`Creating snapshot for workspace: ${workspaceDir}`);

    // Use vscode.workspace.findFiles to get all files, excluding patterns
    const files = await vscode.workspace.findFiles(
        '**/*',
        excludePattern
    );

    // Filter to only code files
    const codeExtensions = new Set([
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
        '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala'
    ]);

    const codeFiles = files.filter(uri => {
        const ext = path.extname(uri.fsPath).toLowerCase();
        return codeExtensions.has(ext);
    });

    console.log(`Found ${codeFiles.length} code files to snapshot`);

    // Process files in batches to avoid overwhelming the system
    const batchSize = 50;
    for (let i = 0; i < codeFiles.length; i += batchSize) {
        const batch = codeFiles.slice(i, i + batchSize);
        await Promise.all(batch.map(async (uri) => {
            const relativePath = path.relative(workspaceDir, uri.fsPath).replace(/\\/g, '/');
            
            // Compute hash
            const hash = await computeFileHash(uri);
            if (hash) {
                const stat = await getFileStat(uri);
                snapshot.files.set(relativePath, {
                    path: relativePath,
                    hash: hash,
                    mtime: stat?.mtime
                });
            }
        }));
    }

    console.log(`Snapshot created with ${snapshot.files.size} files`);
    return snapshot;
}

/**
 * Compare two snapshots and return changes
 */
export function compareSnapshots(oldSnapshot: Snapshot, newSnapshot: Snapshot): {
    added: string[];
    deleted: string[];
    changed: string[];
} {
    const added: string[] = [];
    const deleted: string[] = [];
    const changed: string[] = [];

    // Find added and changed files
    for (const [relativePath, newFile] of newSnapshot.files) {
        const oldFile = oldSnapshot.files.get(relativePath);
        if (!oldFile) {
            // New file
            added.push(relativePath);
        } else if (oldFile.hash !== newFile.hash) {
            // File changed
            changed.push(relativePath);
        }
        // If hash is the same, file hasn't changed, skip it
    }

    // Find deleted files
    for (const [relativePath] of oldSnapshot.files) {
        if (!newSnapshot.files.has(relativePath)) {
            deleted.push(relativePath);
        }
    }

    return { added, deleted, changed };
}

/**
 * Save snapshot to RAG workspace storage directory
 */
export async function saveSnapshot(
    snapshot: Snapshot,
    workspaceDir: string,
    extensionPath: string
): Promise<void> {
    const storageDir = getWorkspaceStoragePath(workspaceDir, extensionPath);
    const snapshotPath = path.join(storageDir, 'snapshot.json');
    
    // Ensure directory exists
    if (!fs.existsSync(storageDir)) {
        fs.mkdirSync(storageDir, { recursive: true });
    }

    // Convert Map to object for JSON serialization
    // Convert files Map to object with proper structure
    const filesObj: { [key: string]: FileSnapshot } = {};
    snapshot.files.forEach((fileSnapshot, relativePath) => {
        filesObj[relativePath] = fileSnapshot;
    });

    const snapshotData = {
        timestamp: snapshot.timestamp,
        files: filesObj
    };

    fs.writeFileSync(snapshotPath, JSON.stringify(snapshotData, null, 2), 'utf-8');
    console.log(`Snapshot saved to: ${snapshotPath}`);
}

/**
 * Load snapshot from RAG workspace storage directory
 */
export async function loadSnapshot(workspaceDir: string, extensionPath: string): Promise<Snapshot | null> {
    const storageDir = getWorkspaceStoragePath(workspaceDir, extensionPath);
    const snapshotPath = path.join(storageDir, 'snapshot.json');
    
    if (!fs.existsSync(snapshotPath)) {
        console.log(`Snapshot not found at: ${snapshotPath}`);
        return null;
    }

    try {
        const data = fs.readFileSync(snapshotPath, 'utf-8');
        const snapshotData = JSON.parse(data);
        
        // Convert object back to Map
        const files = new Map<string, FileSnapshot>();
        if (snapshotData.files) {
            Object.entries(snapshotData.files).forEach(([relativePath, fileSnapshot]: [string, any]) => {
                files.set(relativePath, fileSnapshot as FileSnapshot);
            });
        }
        
        const snapshot: Snapshot = {
            timestamp: snapshotData.timestamp || Date.now(),
            files: files
        };

        console.log(`Snapshot loaded with ${snapshot.files.size} files from: ${snapshotPath}`);
        return snapshot;
    } catch (error) {
        console.error(`Failed to load snapshot:`, error);
        return null;
    }
}


#!/usr/bin/env node
/**
 * E2E Test Runner
 *
 * Orchestrates E2E tests:
 * 1. Start backend on port 7778
 * 2. Build and preview frontend on port 4173
 * 3. Run Cypress tests
 * 4. Cleanup processes and ports
 */

import { spawn, exec } from 'child_process';
import { promisify } from 'util';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import cypress from 'cypress';
import { platform } from 'os';

const execAsync = promisify(exec);
const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '..');

// Configuration
const TEST_PORT_BACKEND = 7778;
const TEST_PORT_FRONTEND = 4173;
const BACKEND_DIR = join(rootDir, 'apps', 'backend');
const FRONTEND_DIR = join(rootDir, 'apps', 'frontend');

let backendProcess = null;
let frontendProcess = null;

// Colors
const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m'
};

function log(msg, color = colors.cyan) {
  console.log(`${color}${msg}${colors.reset}`);
}

function logInfo(msg) { log(`[INFO] ${msg}`, colors.cyan); }
function logSuccess(msg) { log(`[SUCCESS] ${msg}`, colors.green); }
function logError(msg) { log(`[ERROR] ${msg}`, colors.red); }
function logSection(msg) {
  console.log('');
  log('========================================', colors.magenta);
  log(msg, colors.magenta);
  log('========================================', colors.magenta);
  console.log('');
}

/**
 * Kill process on port (cross-platform)
 */
async function killPort(port) {
  try {
    if (platform() === 'win32') {
      const { stdout } = await execAsync(`netstat -ano | findstr :${port}`);
      const lines = stdout.trim().split('\n');

      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0') {
          try {
            await execAsync(`taskkill /F /PID ${pid}`);
            log(`  Killed process ${pid} on port ${port}`, colors.yellow);
          } catch (e) {
            // Already dead
          }
        }
      }
    } else {
      await execAsync(`lsof -ti:${port} | xargs kill -9`);
    }
  } catch (error) {
    // Port already free
  }
}

/**
 * Wait for HTTP endpoint to become available
 */
async function waitForEndpoint(url, maxRetries = 30, retryDelay = 1000) {
  log(`[DEBUG] Polling ${url} (max ${maxRetries} retries)...`, colors.yellow);

  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        log(`[DEBUG] Endpoint ready after ${i + 1} attempts`, colors.green);
        return true;
      }
      log(`[DEBUG] Attempt ${i + 1}/${maxRetries}: Status ${response.status}`, colors.yellow);
    } catch (error) {
      log(`[DEBUG] Attempt ${i + 1}/${maxRetries}: ${error.message}`, colors.yellow);
    }
    await new Promise(resolve => setTimeout(resolve, retryDelay));
  }
  throw new Error(`Endpoint ${url} did not become available after ${maxRetries} retries`);
}

/**
 * Start backend server
 */
async function startBackend() {
  logInfo('Starting backend on port 7778...');

  await killPort(TEST_PORT_BACKEND);

  const pythonCmd = platform() === 'win32'
    ? join(rootDir, '.venv', 'Scripts', 'python.exe')
    : join(rootDir, '.venv', 'bin', 'python');

  log(`[DEBUG] Python path: ${pythonCmd}`, colors.yellow);

  // Set PYTHONPATH to src directory (required for non-editable installs)
  const pythonPath = join(BACKEND_DIR, 'src');

  const env = {
    ...process.env,
    PYTHONPATH: pythonPath,
    OCT_PORT: String(TEST_PORT_BACKEND),
    OCT_MOCK_MODE: 'true',
    OCT_ALLOW_DANGEROUS_OPERATIONS: 'true',
    OCT_LOG_LEVEL: 'WARNING'
  };

  backendProcess = spawn(
    pythonCmd,
    ['-m', 'uvicorn', 'opencloudtouch.main:app', '--host', '0.0.0.0', '--port', String(TEST_PORT_BACKEND)],
    { cwd: BACKEND_DIR, env, stdio: 'inherit' }
  );

  backendProcess.on('error', (error) => {
    logError(`Backend process error: ${error.message}`);
    throw error;
  });

  log('[DEBUG] Waiting for backend health endpoint...', colors.yellow);

  // Wait for backend to be ready (health check)
  await waitForEndpoint(`http://localhost:${TEST_PORT_BACKEND}/health`);

  // Wait for API to be fully initialized (database ready for queries)
  log('[DEBUG] Waiting for backend API endpoints to be ready...', colors.yellow);
  await waitForEndpoint(`http://localhost:${TEST_PORT_BACKEND}/api/devices`);

  logSuccess('Backend started successfully');
}

/**
 * Build and start frontend preview
 */
async function startFrontend() {
  logInfo('Building frontend (production build)...');

  await killPort(TEST_PORT_FRONTEND);

  // Build frontend without VITE_API_BASE_URL so the app uses relative /api/* URLs.
  // The Vite preview proxy then forwards them to the backend at port 7778.
  // This is required so cy.intercept('/api/...') works correctly in Cypress.
  const frontendEnv = { ...process.env };

  const buildProcess = spawn(
    'npm',
    ['run', 'build'],
    { cwd: FRONTEND_DIR, stdio: 'inherit', shell: true, env: frontendEnv }
  );

  await new Promise((resolve, reject) => {
    buildProcess.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Build failed with code ${code}`));
    });
  });

  logSuccess('Frontend built successfully');
  logInfo(`Starting frontend preview server on port ${TEST_PORT_FRONTEND}...`);

  // Start preview server
  frontendProcess = spawn(
    'npm',
    ['run', 'preview', '--', '--port', String(TEST_PORT_FRONTEND), '--strictPort'],
    { cwd: FRONTEND_DIR, stdio: 'pipe', shell: true, env: frontendEnv }
  );

  frontendProcess.stderr.on('data', (data) => {
    const msg = data.toString();
    if (msg.includes('ERROR')) {
      logError(msg.trim());
    }
  });

  // Wait for frontend to be ready
  await waitForEndpoint(`http://localhost:${TEST_PORT_FRONTEND}`);
  logSuccess('Frontend started successfully');
}

/**
 * Run Cypress tests using the Cypress Node.js Module API.
 * Avoids subprocess spawning which causes Electron crash (STATUS_ILLEGAL_INSTRUCTION)
 * when the parent process has no real console (e.g. git commit from VSCode GUI).
 */
async function runCypressTests() {
  logInfo('Running Cypress E2E tests...');

  const result = await cypress.run({
    project: FRONTEND_DIR,
    browser: 'electron',
    headless: true,
  });

  if (result.status === 'failed' || result.totalFailed > 0) {
    throw new Error(
      `Cypress tests failed: ${result.totalFailed ?? '?'} test(s) failed`
    );
  }

  return result;
}

/**
 * Cleanup processes and ports
 */
async function cleanup() {
  logInfo('Cleaning up...');

  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill('SIGTERM');
  }

  if (frontendProcess && !frontendProcess.killed) {
    frontendProcess.kill('SIGTERM');
  }

  await new Promise(resolve => setTimeout(resolve, 500));

  await killPort(TEST_PORT_BACKEND);
  await killPort(TEST_PORT_FRONTEND);

  logSuccess('Cleanup complete');
}

/**
 * Main execution
 */
async function main() {
  logSection('OpenCloudTouch E2E Test Runner');

  let exitCode = 0;

  try {
    // Step 1: Start backend
    await startBackend();

    // Step 2: Build and start frontend
    await startFrontend();

    // Step 3: Run Cypress tests
    await runCypressTests();

    logSection('E2E Tests PASSED ✅');
  } catch (error) {
    logError(error.message);
    logSection('E2E Tests FAILED ❌');
    exitCode = 1;
  } finally {
    await cleanup();
  }

  process.exit(exitCode);
}

// Handle SIGINT (Ctrl+C)
process.on('SIGINT', async () => {
  console.log('');
  logInfo('Received SIGINT, cleaning up...');
  await cleanup();
  process.exit(130);
});

// Run
main().catch(async (error) => {
  logError(`Fatal error: ${error.message}`);
  await cleanup();
  process.exit(1);
});

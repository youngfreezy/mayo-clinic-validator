#!/usr/bin/env node
/**
 * Mayo Clinic Validator — one-time setup (macOS / Linux)
 *
 * Usage:  npm run setup
 *
 * What it does:
 *   1. Checks prerequisites (Docker, Python 3.11, Node)
 *   2. Creates backend Python venv + installs pip deps
 *   3. Starts PostgreSQL+pgvector container
 *   4. Waits for Postgres, then seeds the RAG knowledge base
 *   5. Installs frontend npm dependencies
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "..");
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");

const c = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  cyan: "\x1b[36m",
};

function log(msg) {
  console.log(`${c.cyan}${c.bold}[setup]${c.reset} ${msg}`);
}

function ok(msg) {
  console.log(`${c.green}${c.bold}  ✓${c.reset} ${msg}`);
}

function warn(msg) {
  console.log(`${c.yellow}${c.bold}  ⚠${c.reset} ${msg}`);
}

function fail(msg) {
  console.error(`${c.red}${c.bold}  ✗${c.reset} ${msg}`);
}

function run(cmd, opts = {}) {
  return execSync(cmd, { stdio: "inherit", ...opts });
}

function runQuiet(cmd, opts = {}) {
  return execSync(cmd, { stdio: "pipe", ...opts }).toString().trim();
}

function which(cmd) {
  try {
    return runQuiet(`which ${cmd}`);
  } catch {
    return null;
  }
}

// ── find Python 3.11 ──────────────────────────────────────────────────────────
function findPython() {
  // Prefer Homebrew python3.11
  const brewPath = "/opt/homebrew/bin/python3.11";
  if (fs.existsSync(brewPath)) return brewPath;

  // Try generic python3.11 on PATH
  const onPath = which("python3.11");
  if (onPath) return onPath;

  // Fall back to python3 and check version
  const py3 = which("python3");
  if (py3) {
    try {
      const ver = runQuiet(`${py3} --version`);
      if (ver.includes("3.11")) return py3;
    } catch {}
  }

  return null;
}

// ── main ──────────────────────────────────────────────────────────────────────
(async () => {
  try {
  log("Mayo Clinic Validator — one-time setup\n");

  // 1. Check prerequisites
  log("Checking prerequisites…");

  // Docker
  if (!which("docker")) {
    fail("Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/");
    process.exit(1);
  }
  ok("Docker found");

  // Python 3.11
  const python = findPython();
  if (!python) {
    fail("Python 3.11 not found. Install with: brew install python@3.11");
    process.exit(1);
  }
  ok(`Python 3.11 found: ${python}`);

  // Node
  if (!which("node")) {
    fail("Node.js not found. Install with: brew install node@20");
    process.exit(1);
  }
  ok("Node.js found");

  // .env file
  const envFile = path.join(BACKEND, ".env");
  const envExample = path.join(BACKEND, ".env.example");
  if (!fs.existsSync(envFile)) {
    if (fs.existsSync(envExample)) {
      fs.copyFileSync(envExample, envFile);
      warn("Created backend/.env from .env.example — edit it to add your OPENAI_API_KEY");
    } else {
      warn("No backend/.env found — create one with your OPENAI_API_KEY before running");
    }
  } else {
    ok("backend/.env exists");
  }

  // 2. Python venv + deps
  log("\nSetting up Python backend…");
  const venvDir = path.join(BACKEND, "venv");
  if (!fs.existsSync(venvDir)) {
    log("Creating virtualenv…");
    run(`${python} -m venv venv`, { cwd: BACKEND });
    ok("Virtualenv created");
  } else {
    ok("Virtualenv already exists");
  }

  log("Installing Python dependencies…");
  const pip = path.join(venvDir, "bin", "pip");
  run(`${pip} install -r requirements.txt`, { cwd: BACKEND });
  ok("Python dependencies installed");

  // 3. Docker compose (Postgres + pgvector)
  log("\nStarting PostgreSQL container…");
  try {
    run("docker info", { stdio: "pipe" });
  } catch {
    warn("Docker daemon not running — starting Docker Desktop…");
    try { runQuiet("open -a Docker"); } catch {}
    log("Waiting for Docker daemon (up to 2 min)…");
    const deadline = Date.now() + 120_000;
    while (Date.now() < deadline) {
      try { runQuiet("docker info"); break; } catch {}
      await new Promise((r) => setTimeout(r, 5000));
    }
    try { runQuiet("docker info"); } catch {
      fail("Docker daemon did not start in time. Start Docker Desktop manually and re-run.");
      process.exit(1);
    }
  }

  run("docker compose up -d", { cwd: BACKEND });
  ok("PostgreSQL container started");

  // 4. Wait for Postgres + seed
  log("Waiting for Postgres to accept connections…");
  const deadline = Date.now() + 60_000;
  let pgReady = false;
  while (Date.now() < deadline) {
    try {
      runQuiet("docker exec mayo_validator_db pg_isready -U postgres -d mayo_validation");
      pgReady = true;
      break;
    } catch {}
    await new Promise((r) => setTimeout(r, 2000));
  }
  if (!pgReady) {
    fail("Postgres did not become ready in time.");
    process.exit(1);
  }
  ok("Postgres ready");

  log("Seeding RAG knowledge base…");
  const pythonBin = path.join(venvDir, "bin", "python");
  run(`${pythonBin} scripts/seed_knowledge.py`, { cwd: BACKEND });
  ok("Knowledge base seeded");

  // 5. Frontend npm install
  log("\nInstalling frontend dependencies…");
  run("npm install", { cwd: FRONTEND });
  ok("Frontend dependencies installed");

  // Done
  console.log(`\n${c.green}${c.bold}Setup complete!${c.reset}`);
  console.log(`\nRun ${c.cyan}npm start${c.reset} to launch the app.\n`);
  } catch (err) {
    fail(err.message || err);
    process.exit(1);
  }
})();

import { execSync, execFileSync } from "child_process";
import { existsSync, writeFileSync, statSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CA_BUNDLE = join(__dirname, "ca-bundle.pem");
const WORKER = join(__dirname, "fetch-worker.mjs");
const CA_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

// On Windows, export system root CAs so Node can verify all certs
if (process.platform === "win32" && !process.env.NODE_EXTRA_CA_CERTS) {
  let needsRefresh = !existsSync(CA_BUNDLE);
  if (!needsRefresh) {
    const age = Date.now() - statSync(CA_BUNDLE).mtimeMs;
    needsRefresh = age > CA_MAX_AGE_MS;
  }

  if (needsRefresh) {
    try {
      const pem = execSync(
        'powershell.exe -Command "Get-ChildItem -Path Cert:\\\\LocalMachine\\\\Root | ForEach-Object { \'-----BEGIN CERTIFICATE-----\'; [Convert]::ToBase64String($_.RawData, \'InsertLineBreaks\'); \'-----END CERTIFICATE-----\' }"',
        { encoding: "utf-8", timeout: 10000 }
      );
      writeFileSync(CA_BUNDLE, pem);
    } catch {
      // Continue without extra certs — will fail with clear TLS error
    }
  }

  if (existsSync(CA_BUNDLE)) {
    // Re-exec with NODE_EXTRA_CA_CERTS set
    try {
      const result = execFileSync(process.execPath, [WORKER, ...process.argv.slice(2)], {
        env: { ...process.env, NODE_EXTRA_CA_CERTS: CA_BUNDLE },
        encoding: "utf-8",
        maxBuffer: 50 * 1024 * 1024,
        timeout: 60000,
      });
      process.stdout.write(result);
      process.exit(0);
    } catch (e) {
      if (e.stdout) process.stdout.write(e.stdout);
      if (e.stderr) process.stderr.write(e.stderr);
      process.exit(e.status || 1);
    }
  }
}

// Non-Windows or NODE_EXTRA_CA_CERTS already set: run worker inline
const { run } = await import("./fetch-worker.mjs");
await run();

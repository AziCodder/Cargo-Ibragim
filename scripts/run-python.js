/**
 * Запуск backend или bot через найденный в системе Python.
 * Решает проблему "python не найден" и кириллицы в путях при npm run dev на Windows.
 */
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const isWin = process.platform === "win32";
const root = path.resolve(__dirname, "..");

function findPython() {
  // Можно задать путь вручную: set PYTHON_CMD=C:\Python312\python.exe
  const manual = process.env.PYTHON_CMD || process.env.PYTHON;
  if (manual && manual.trim()) return manual.trim();

  // Приоритет: .venv в корне проекта (путь собираем сами — без искажения кириллицы в Windows)
  const venvPython = isWin
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python");
  if (fs.existsSync(venvPython)) return venvPython;

  // Иначе ищем в PATH (на Windows с кириллицей в путях может возвращать битый путь)
  const tries = isWin ? ["python", "python3", "py"] : ["python3", "python"];
  const skipPath = (p) => p.includes("WindowsApps"); // заглушка Microsoft Store

  for (const cmd of tries) {
    try {
      const result = require("child_process").execSync(
        isWin ? `where ${cmd}` : `which ${cmd}`,
        { encoding: "utf-8", windowsHide: true }
      );
      const lines = result
        .trim()
        .split(/\r?\n/)
        .filter((l) => l && !l.startsWith("INFO:") && !skipPath(l));
      if (lines.length) return lines[0].trim();
    } catch (_) {
      continue;
    }
  }
  console.error("Python не найден. Установите Python с python.org и добавьте в PATH или создайте .venv в корне проекта.");
  process.exit(1);
}

const target = process.argv[2];
if (!target || !["backend", "bot"].includes(target)) {
  console.error("Использование: node scripts/run-python.js <backend|bot>");
  process.exit(1);
}

const python = findPython();
const base = path.basename(python).toLowerCase();
const isPyLauncher = isWin && (base === "py.exe" || base === "py");
const pyPrefix = isPyLauncher ? ["-3"] : [];

const args =
  target === "backend"
    ? [...pyPrefix, "-m", "uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8800"]
    : [...pyPrefix, path.join(root, "telegram_bot", "bot.py")];

// На Windows с путями в кириллице/пробелах запускаем через shell и заключаем пути в кавычки
const useShell = isWin;
const needQuote = (s) => typeof s === "string" && /[\s"]/.test(s);
const quoted = (s) => (needQuote(s) ? `"${String(s).replace(/"/g, '""')}"` : s);

let child;
if (useShell) {
  const cmd = [quoted(python), ...args.map((a) => quoted(a))].join(" ");
  child = spawn(cmd, {
    cwd: root,
    stdio: "inherit",
    shell: true,
    windowsHide: true,
  });
} else {
  child = spawn(python, args, {
    cwd: root,
    stdio: "inherit",
    shell: false,
    windowsHide: true,
  });
}

child.on("error", (err) => {
  console.error(err);
  process.exit(1);
});
child.on("exit", (code) => {
  process.exit(code ?? 0);
});

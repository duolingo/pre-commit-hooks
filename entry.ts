#!/usr/bin/env node

import { exec } from "child_process";
import { createReadStream, readFile, writeFile } from "fs";
import { createInterface } from "readline";

/**
 * Path to an empty file that we can provide to linters/formatters as a config
 * file in order to force those tools' default behavior
 */
const EMPTY_FILE = "/emptyfile";

/** Minified JS files to exclude from formatting */
const MINIFIED_JS_REGEX = /\bmin\b|\.(custom|pack)\./;

/** CLI options to use in all Prettier invocations */
const PRETTIER_OPTIONS = [
  "--arrow-parens",
  "avoid",
  // We don't enable or benefit from caching, but we must still specify a
  // location or else Prettier will fail with the error `EPERM: operation not
  // permitted, mkdir '/src/node_modules/.cache/prettier'`
  "--cache-location",
  "/tmp/prettier-cache",
  "--end-of-line",
  "auto",
  "--ignore-path",
  EMPTY_FILE,
  "--log-level",
  "warn",
  "--no-config",
  "--no-editorconfig",
  "--object-wrap",
  "collapse",
  "--write",
];

/** Runs a shell command, promising combined stdout and stderr */
const run = (...args: string[]) =>
  new Promise<string>((resolve, reject) => {
    exec(
      args.map(arg => `'${arg.replace(/'/g, "'\"'\"'")}'`).join(" "),
      { maxBuffer: Infinity },
      (ex, stdout, stderr) => (ex ? reject : resolve)(stdout + stderr),
    );
  });

/** Type guard that returns true iff the given value is truthy */
export const isTruthy = <T>(value: T): value is NonNullable<T> => !!value;

/** Reads a file, transforms its contents, and writes the result if different */
const transformFile = (path: string, transform: (before: string) => string) =>
  new Promise<void>((resolve, reject) => {
    readFile(path, "utf8", (err, data) => {
      // File unreadable
      if (err) {
        reject(err);
        return;
      }

      // File empty
      if (data === "") {
        resolve();
        return;
      }

      // File unmodified
      const after = transform(data);
      if (data === after) {
        resolve();
        return;
      }

      // File modified
      writeFile(path, after, "utf8", err => (err ? reject(err) : resolve()));
    });
  });

const enum HookName {
  Autoflake = "autoflake",
  Black = "Black",
  ClangFormat = "ClangFormat",
  EsLint = "ESLint",
  Gofmt = "gofmt",
  GoogleJavaFormat = "google-java-format",
  GradleDependenciesSorter = "gradle-dependencies-sorter",
  Isort = "isort",
  Ktfmt = "ktfmt",
  PackerFmt = "packer fmt",
  PrettierJs = "Prettier (JS)",
  PrettierNonJs = "Prettier (non-JS)",
  Ruff = "Ruff",
  Scalafmt = "scalafmt",
  Sed = "sed",
  Shfmt = "shfmt",
  Svgo = "SVGO",
  Taplo = "Taplo",
  TerraformFmt = "terraform fmt",
  Xsltproc = "xsltproc",
}

/** Arguments passed into this hook via the `args` pre-commit config key */
type Args = Partial<Record<Arg, string>>;
type Arg = "python-version" | "scala-version";

interface Hook {
  /**
   * Runs the tool and throws a display message iff violations were found that
   * the user must fix manually.
   *
   * Formatters should return their combined stdout+stderr output only in case
   * of parsing errors due to malformed source code, while linters should
   * return their detected violations.
   *
   * The message is thrown (instead of returned) both so that unexpected
   * linter crashes are surfaced to the user and for simplicity in the case of
   * the many linters that exit with nonzero iff there are violations.
   */
  action: (sources: string[], args: Args) => any;
  /** Source files to exclude */
  exclude?: RegExp;
  /** Source files to include */
  include: RegExp;
  /** Hooks that must complete before this one begins */
  runAfter?: HookName[];
}

interface LockableHook extends Hook {
  /** Upon resolution, indicates that this hook has completed */
  lock: Promise<unknown>;
  /** Promise that must resolve before this hook begins execution */
  locksToWaitFor?: Promise<unknown>;
  /** Marks this hook as complete */
  unlock: () => void;
}

/** Wraps a non-lockable hook to add properties used for locking */
const createLockableHook = (hook: Hook): LockableHook => {
  let unlock = () => undefined as void;
  const lock = new Promise<void>(resolve => {
    unlock = resolve;
  });
  return { ...hook, lock, unlock };
};

/** Hooks expressed in a format similar to .pre-commit-config.yaml */
const HOOKS: Record<HookName, LockableHook> = {
  [HookName.Autoflake]: createLockableHook({
    action: sources =>
      run(
        "autoflake",
        "--ignore-init-module-imports",
        "--imports=attrs,boto,boto3,flask,pyramid,pytest,pytz,requests,simplejson,six",
        "--in-place",
        "--remove-duplicate-keys",
        "--remove-unused-variables",
        ...sources,
      ),
    include: /\.py$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.Black]: createLockableHook({
    action: async (sources, args) =>
      args["python-version"]?.startsWith("2") &&
      run(
        // Black 21.x was the last major version with Python 2 support. It also
        // had a bug that requires pinning click==8.0.4. Both packages should
        // be removed once we drop Python 2 support.
        // https://github.com/psf/black/issues/2964
        "black21",
        "--fast",
        "--target-version",
        "py27",
        "--config",
        EMPTY_FILE,
        "--line-length",
        "100",
        "--quiet",
        ...sources,
      ),
    include: /\.py$/,
    runAfter: [HookName.Isort],
  }),
  [HookName.ClangFormat]: createLockableHook({
    action: sources =>
      run(
        "/clang-format",
        "-i", // Edit files in-place
        "--style=file:/.clang-format",
        ...sources,
      ),
    include: /\.(cpp|proto$)/,
    runAfter: [HookName.Sed],
  }),
  [HookName.EsLint]: createLockableHook({
    action: async sources => {
      try {
        await run(
          "eslint",
          "--fix",
          "--config",
          "/eslint.config.js",
          ...sources,
        );
      } catch {
        // We swallow nonzero exit codes because we care only about autofixable
        // errors (which should now be fixed), not about non-autofixable errors
      }
    },
    exclude: MINIFIED_JS_REGEX,
    include: /\.[jt]sx?$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.Gofmt]: createLockableHook({
    action: sources => run("/gofmt", "-s", "-w", ...sources),
    include: /\.go$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.GoogleJavaFormat]: createLockableHook({
    action: sources =>
      run("java", "-jar", "/google-java-format", "--replace", ...sources),
    include: /\.java$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.GradleDependenciesSorter]: createLockableHook({
    action: sources =>
      run("java", "-jar", "/gradle-dependencies-sorter", ...sources),
    include: /build\.gradle(\.kts)?$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.Isort]: createLockableHook({
    // isort's automatic config file detection is broken
    // https://github.com/PyCQA/isort/issues/1907
    // https://github.com/samueljsb/qaz/pull/104
    action: (sources, args) =>
      args["python-version"]?.startsWith("2") &&
      run("isort", "--settings", "/.editorconfig", ...sources),
    include: /\.py$/,
    runAfter: [HookName.Autoflake],
  }),
  [HookName.Ktfmt]: createLockableHook({
    action: async sources => {
      /** Try to avoid ktfmt OOMs presumably caused by too many input files */
      const MAX_FILES_PER_PROCESS = 200;
      for (let i = 0; i < sources.length; i += MAX_FILES_PER_PROCESS) {
        await run(
          "java",
          // By default, ktfmt was OOMing our 36-core CI server with errors
          // like "There is insufficient memory for the Java Runtime
          // Environment to continue. Native memory allocation (mmap) failed to
          // map 3697278976 bytes for committing reserved memory." Capping at
          // 256m works and only increases my laptop's time to format a test
          // repo from 64s to 72s
          "-Xmx256m",
          "-jar",
          "/ktfmt",
          "--google-style",
          ...sources.slice(i, i + MAX_FILES_PER_PROCESS),
        );
      }
    },
    include: /\.kts?$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.PackerFmt]: createLockableHook({
    action: sources => run("/packer", "fmt", ...sources),
    include: /\.pkr\.hcl$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.PrettierJs]: createLockableHook({
    action: sources =>
      run(
        "prettier",
        ...PRETTIER_OPTIONS,
        "--trailing-comma",
        "es5",
        ...sources,
      ),
    exclude: MINIFIED_JS_REGEX,
    include: /\.jsx?$/,
    runAfter: [HookName.Sed, HookName.EsLint],
  }),
  [HookName.PrettierNonJs]: createLockableHook({
    action: sources =>
      run(
        "prettier",
        ...PRETTIER_OPTIONS,
        "--plugin",
        // https://github.com/prettier/prettier/issues/15141#issuecomment-1685112479
        "/usr/local/lib/node_modules/@prettier/plugin-xml/src/plugin.js",
        ...sources,
      ),
    include: /\.(css|html?|markdown|md|scss|tsx?|xml|ya?ml)$/,
    runAfter: [HookName.Sed, HookName.Xsltproc, HookName.EsLint],
  }),
  [HookName.Ruff]: createLockableHook({
    action: async (sources, args) => {
      if (args["python-version"]?.startsWith("2")) {
        return;
      }
      // Sometimes Ruff requires multiple passes, which is ok since it's fast
      for (let i = 0; i < 2; ++i) {
        await run("ruff", "check", "--config", "/ruff.toml", ...sources);
        await run("ruff", "format", "--config", "/ruff.toml", ...sources);
      }
    },
    include: /\.py$/,
    runAfter: [HookName.Autoflake],
  }),
  [HookName.Scalafmt]: createLockableHook({
    action: async (sources, args) =>
      run(
        "/scalafmt",
        "--config-str",
        Object.entries({
          "docstrings.oneline": "fold",
          "docstrings.wrap": "no",
          preset: "IntelliJ",
          "runner.dialect": `scala${(args["scala-version"] ?? "2.12")
            .split(".")
            .slice(0, 2)
            .join("")}`,
          version: (await run("/scalafmt", "--version")).split(" ")[1],
        })
          .map(kv => kv.join("="))
          .join(","),
        "--non-interactive",
        "--quiet",
        ...sources,
      ),
    include: /\.(scala|sbt|sc)$/,
    runAfter: [HookName.Sed],
  }),
  // Mimic sed by applying arbitrary regex transformations. Before proposing a
  // new transformation, please make sure that it's both (1) safe and (2) likely
  // to ever actually be needed. At Duolingo, we determine the latter criterion
  // empirically by seeing how many existing violations our codebase contains
  [HookName.Sed]: createLockableHook({
    action: (sources, args) =>
      Promise.all(
        sources.map(source =>
          transformFile(source, data => {
            // Strip trailing whitespace, strip BOF newlines, require single EOF
            // newline
            const eol = /\r/.test(data) ? "\r\n" : "\n";
            data =
              data.replace(/[^\S\r\n]+$/gm, "").replace(/^[\r\n]+|\s+$/g, "") +
              eol;

            // Transform Kotlin
            if (source.endsWith(".kt")) {
              // Replace empty immutable collections with singletons to avoid
              // unnecessary allocations. Fun fact: Python's empty tuple `()`
              // is similarly implemented as a singleton
              data = data
                .replace(/\barrayOf\(\)/g, "emptyArray()")
                .replace(/\blistOf\(\)/g, "emptyList()")
                .replace(/\bmapOf\(\)/g, "emptyMap()")
                .replace(/\bsequenceOf\(\)/g, "emptySequence()")
                .replace(/\bsetOf\(\)/g, "emptySet()");

              // Remove unnecessary constructor keyword
              data = data.replace(/(?<=\bclass \S+) constructor(?=\()/g, "");
            }

            // Transform Python
            if (source.endsWith(".py")) {
              // Prefer empty collection literals for simplicity
              data = data.replace(/(?<=^|[ ([{=])dict\(\)/gm, "{}");
              data = data.replace(/(?<=^|[ ([{=])list\(\)/gm, "[]");
              data = data.replace(/(?<=^|[ ([{=])tuple\(\)/gm, "()");

              // Remove unnecessary [] from empty sets
              data = data.replace(
                /(?<=(?:^|[ ([{=])(?:frozen)?set\()\[\](?=\))/gm,
                "",
              );

              // Transform Python 3
              if (!args["python-version"]?.startsWith("2")) {
                // Remove unnecessary encoding declarations
                data = data.replace(/^# -\*- coding: utf-?8.*?\n/gim, "");

                // Remove unnecessary base class declarations
                data = data.replace(/(?<=^ *class \S+?)\(object\)(?=:)/gm, "");
              }
            }

            return data;
          }),
        ),
      ),
    include: /./,
  }),
  [HookName.Shfmt]: createLockableHook({
    action: async sources => {
      // Find source files that are Shell files. shfmt has a `-f` flag that
      // does this, but it sometimes returns false positives
      const shellSources = (
        await Promise.all(
          sources.map(async source => {
            // Check file extension
            if (source.split("/").slice(-1)[0].includes(".")) {
              return /\.(bash|sh|zsh)$/.test(source) ? source : undefined;
            }

            // Check shebang
            const firstLine = await new Promise<string>(resolve => {
              // https://stackoverflow.com/a/45556848
              const reader = createInterface({
                input: createReadStream(source),
              });
              reader.on("line", line => {
                reader.close();
                resolve(line);
              });
            });
            if (/^#!.*\b(bash|sh|zsh)\b/.test(firstLine)) {
              return source;
            }
          }),
        )
      ).filter(isTruthy);
      if (!shellSources.length) {
        return;
      }

      await run(
        "/shfmt",
        "-bn", // Binary operator at start of line
        "-ci", // Indent switch cases
        "-i=2", // Indent 2 spaces
        // https://github.com/mvdan/sh/blob/fa1b438/syntax/simplify.go#L13-L18
        "-s", // Simplify code
        "-sr", // Add space after redirect operators
        "-w", // Write
        ...shellSources,
      );
    },
    // pre-commit's `types: [text]` config option sometimes has false positives,
    // and removing a binary .proto file's trailing newline may corrupt it
    exclude: /\.proto$/,
    include: /./,
    runAfter: [HookName.Sed],
  }),
  [HookName.Svgo]: createLockableHook({
    action: sources => run("svgo", "--config", "/svgo.config.js", ...sources),
    include: /\.svg$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.Taplo]: createLockableHook({
    action: sources =>
      run(
        "/taplo",
        "format",
        "--colors",
        "never",
        "--no-auto-config",
        // https://taplo.tamasfe.dev/configuration/formatter-options.html
        "--option",
        "align_comments=false", // Avoid diff churn
        "--option",
        "allowed_blank_lines=1", // Match other languages (except Python)
        "--option",
        "reorder_keys=true", // Maximize consistency
        ...sources,
      ),
    include: /\.toml$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.TerraformFmt]: createLockableHook({
    action: sources =>
      Promise.all(
        // Officially `terraform fmt` only accepts a directory to recurse
        // through as its sole argument, but it secretly does still support the
        // more convenient route of supplying a single .tf file as the argument.
        // (Our problem with providing a directory as the argument is that it
        // can lead to double-formatting in the case that two sibling source
        // files get randomly assigned to different processes when pre-commit
        // parallelizes multiple runs of this hook. This in turn can create a
        // race condition that results in a source file getting unintentionally
        // deleted!) https://github.com/hashicorp/terraform/pull/20040
        sources.map(source => run("/terraform", "fmt", "-write=true", source)),
      ),
    include: /\.tf$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.Xsltproc]: createLockableHook({
    action: sources =>
      Promise.all(
        sources.map(source =>
          run("xsltproc", "--output", source, "/stylesheet.xml", source),
        ),
      ),
    include: /\.xml$/,
    runAfter: [HookName.Sed],
  }),
};

/** Files that match this pattern should never be processed */
const GLOBAL_EXCLUDES = (() => {
  const FOLDER_EXCLUDES = ["build", "node_modules"];
  const FILE_EXCLUDES = [
    "AGENTS.md", // Generated by sync-ai-rules pre-commit hook
    "CLAUDE.md", // Generated by sync-ai-rules pre-commit hook
    "copilot-instructions.md", // Generated by sync-ai-rules pre-commit hook
    "gradlew",
  ];
  return RegExp(
    `(^|/)((${FOLDER_EXCLUDES.join("|")})/|(${FILE_EXCLUDES.map(f => f.replace(/\./g, "\\.")).join("|")})$)`,
  );
})();

/** Prefixes a string to all nonempty lines of input */
const prefixLines = (() => {
  const LINES_TO_IGNORE = new RegExp(
    [
      // Empty lines
      /^\s*$/,
      // ktfmt spams this for every file that has no violations
      /\bDone formatting .+\.kts?$/,
      // Black 21.12b0 spams this when running on Python 2 source code
      /\bDEPRECATION: Python 2 support\b/,
    ]
      .map(regex => regex.source)
      .join("|"),
  );
  const maxPrefixLength = Math.max(
    ...Object.keys(HOOKS).map(name => name.length),
  );
  return (prefix: string, lines: string) =>
    lines
      .split("\n")
      .filter(line => !LINES_TO_IGNORE.test(line))
      .map(line => `${prefix}:`.padEnd(maxPrefixLength + 2) + line)
      .join("\n");
})();

(async () => {
  // Determine hook arguments and list of source files to process
  const sources: string[] = process.argv.slice(2); // Strips ['/usr/bin/node', '/entry']
  const args: Args = {};
  while (sources.length && /^--[\w-]+=./.test(sources[0])) {
    const arg = sources.shift();
    if (arg) {
      const matches = arg.match(/--([^=]+)=(.+)/);
      if (matches && matches[1] && matches[2]) {
        args[matches[1] as Arg] = matches[2] as string;
      }
    }
  }

  // Set up hook locks
  Object.values(HOOKS).forEach(hook => {
    if (hook.runAfter) {
      hook.locksToWaitFor = Promise.all(
        hook.runAfter.map(hookName => HOOKS[hookName].lock),
      );
    }
  });

  // Run all hooks in parallel
  let success = true;
  await Promise.all(
    Object.entries(HOOKS).map(
      async ([name, { action, exclude, include, locksToWaitFor, unlock }]) => {
        // Wait until necessary hooks have completed
        await locksToWaitFor;

        // Determine set of source files to process
        const includedSources = sources.filter(
          source =>
            include.test(source) &&
            !GLOBAL_EXCLUDES.test(source) &&
            !(exclude && exclude.test(source)),
        );

        // Run hook
        if (includedSources.length) {
          try {
            await action(includedSources, args);
          } catch (ex) {
            success = false;
            console.error(prefixLines(name, `${ex}`));
          }
        }

        // Mark this hook as complete
        unlock();
      },
    ),
  );

  // Exit with appropriate code
  success || process.exit(1);
})();

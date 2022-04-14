#!/usr/bin/env node

import { exec } from "child_process";
import { readFile, writeFile } from "fs";

/** Maximum characters per line in Python */
const PYTHON_LINE_LENGTH = 100;

/**
 * Path to an empty file that we can provide to linters/formatters as a config
 * file in order to force those tools' default behavior
 */
const EMPTY_FILE = "/emptyfile";

/** CLI options to use in all Prettier invocations */
const PRETTIER_OPTIONS = [
  "--arrow-parens",
  "avoid",
  "--end-of-line",
  "auto",
  "--ignore-path",
  EMPTY_FILE,
  "--loglevel",
  "warn",
  "--no-config",
  "--no-editorconfig",
  "--write",
];

/** Runs a shell command, promising combined stdout and stderr */
const run = (...args: string[]) =>
  new Promise<string>((resolve, reject) => {
    exec(
      args.map(arg => `'${arg}'`).join(" "),
      { maxBuffer: Infinity },
      (ex, stdout, stderr) => (ex ? reject : resolve)(stdout + stderr),
    );
  });

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
  GoogleJavaFormat = "google-java-format",
  Isort = "isort",
  Ktfmt = "ktfmt",
  PrettierJs = "Prettier (JS)",
  PrettierNonJs = "Prettier (non-JS)",
  Scalafmt = "scalafmt",
  Sed = "sed",
  Shfmt = "shfmt",
  Svgo = "SVGO",
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
  action: (sources: string[], args: Args) => Promise<unknown>;
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
      run(
        // Black 21.x was the last major version with Python 2 support. It also
        // had a bug that requires pinning click==8.0.4. Both packages should
        // be removed once we drop Python 2 support.
        // https://github.com/psf/black/issues/2964
        ...(args["python-version"]?.startsWith("2")
          ? ["black21", "--fast", "--target-version", "py27"]
          : ["black", "--target-version", "py310"]),
        "--config",
        EMPTY_FILE,
        "--line-length",
        `${PYTHON_LINE_LENGTH}`,
        "--quiet",
        ...sources,
      ),
    include: /\.py$/,
    runAfter: [HookName.Isort],
  }),
  [HookName.ClangFormat]: createLockableHook({
    action: sources =>
      run(
        "clang-format",
        "-i", // Edit files in-place
        "--style=Google",
        ...sources,
      ),
    include: /\.proto$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.GoogleJavaFormat]: createLockableHook({
    action: sources =>
      run("java", "-jar", "/google-java-format", "--replace", ...sources),
    include: /\.java$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.Isort]: createLockableHook({
    // isort's automatic config file detection is broken
    // https://github.com/PyCQA/isort/issues/1907
    // https://github.com/samueljsb/qaz/pull/104
    action: sources => run("isort", "--settings", "/.editorconfig", ...sources),
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
  [HookName.PrettierJs]: createLockableHook({
    action: sources => run("prettier", ...PRETTIER_OPTIONS, ...sources),
    exclude: /\b(compressed|custom|min|minified|pack|prod|production)\b/,
    include: /\.jsx?$/,
    runAfter: [HookName.Sed],
  }),
  [HookName.PrettierNonJs]: createLockableHook({
    action: sources =>
      run(
        "prettier",
        ...PRETTIER_OPTIONS,
        "--trailing-comma",
        "all",
        ...sources,
      ),
    include: /\.(css|html?|markdown|md|scss|tsx?|xml|ya?ml)$/,
    runAfter: [HookName.Sed, HookName.Xsltproc],
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
      // Find source files that are Shell files
      const shellSources = (await run("/shfmt", "-f", ...sources)).trim();
      if (!shellSources) {
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
        ...shellSources.split("\n"),
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
  const FILE_EXCLUDES = ["gradlew"];
  return RegExp(
    `(^|/)((${FOLDER_EXCLUDES.join("|")})/|(${FILE_EXCLUDES.join("|")})$)`,
  );
})();

/** Prefixes a string to all nonempty lines of input */
const prefixLines = (() => {
  const maxPrefixLength = Math.max(
    ...Object.keys(HOOKS).map(name => name.length),
  );
  return (prefix: string, lines: string) =>
    lines
      .split("\n")
      .filter(line => line.trim().length)
      // Black 21.12b0 spams this when running on Python 2 source code
      .filter(line => !line.includes("DEPRECATION: Python 2 support"))
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

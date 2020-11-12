#!/usr/bin/env node

import { exec } from "child_process";
import { readFile, writeFile } from "fs";
import { dirname } from "path";

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
  new Promise<string>((resolve, reject) => {
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
  Ktlint = "ktlint",
  PrettierJs = "Prettier (JS)",
  PrettierNonJs = "Prettier (non-JS)",
  Scalafmt = "scalafmt",
  Shfmt = "shfmt",
  Svgo = "SVGO",
  TerraformFmt = "terraform fmt",
  WhitespaceFixer = "Whitespace fixer",
}

/** Arguments passed into this hook via the `args` pre-commit config key */
type Args = Partial<Record<Arg, string>>;
type Arg = "python-version";

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
  const lock = new Promise(resolve => {
    unlock = resolve;
  });
  return { ...hook, lock, unlock };
};

/** Gets the given paths' parent directories */
const getParentDirs = (files: string[]) =>
  Array.from(new Set(files.map(file => dirname(file)))).sort();

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
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.Black]: createLockableHook({
    action: async (sources, args) => {
      const pythonVersionArgs = (args["python-version"] || "").startsWith("2")
        ? ["--fast", "--target-version", "py27"]
        : ["--target-version", "py36"];
      await run(
        "black",
        "--config",
        EMPTY_FILE,
        "--line-length",
        `${PYTHON_LINE_LENGTH}`,
        "--quiet",
        ...pythonVersionArgs,
        ...sources,
      );
    },
    include: /\.py$/,
    runAfter: [HookName.Autoflake],
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
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.GoogleJavaFormat]: createLockableHook({
    action: sources =>
      run(
        "java",
        "-jar",
        "/google-java-format-1.9-all-deps.jar",
        "--replace",
        ...sources,
      ),
    include: /\.java$/,
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.Ktlint]: createLockableHook({
    action: async sources => {
      try {
        await run("/ktlint", "--format", ...sources);
      } catch (ex) {
        // ktlint just failed to autocorrect some stuff, e.g. long lines
      }
    },
    include: /\.kt$/,
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.PrettierJs]: createLockableHook({
    action: sources => run("prettier", ...PRETTIER_OPTIONS, ...sources),
    exclude: /\b(compressed|custom|min|minified|pack|prod|production)\b/,
    include: /\.jsx?$/,
    runAfter: [HookName.WhitespaceFixer],
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
    include: /\.(html?|markdown|md|scss|tsx?|ya?ml)$/,
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.Scalafmt]: createLockableHook({
    action: sources =>
      run("/scalafmt", "--config-str", "preset=IntelliJ", ...sources),
    include: /\.(scala|sbt|sc)$/,
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.Shfmt]: createLockableHook({
    action: async sources => {
      // When given a directory to recurse through, shfmt processes only files
      // that have a shell extension or shebang. However, no such filtering is
      // done when individual files are passed to shfmt. To avoid shfmt-ing
      // non-shell source files, we first use `shfmt -f` to list all files
      // inside of the given source files' parent directories that are shell
      // files and then run shfmt only on source files contained in that list.
      const shellFilesInParentDirs = (
        await run(
          "/shfmt",
          "-f", // Find
          ...getParentDirs(sources),
        )
      ).split("\n");
      const shellSources = sources.filter(source =>
        shellFilesInParentDirs.includes(source),
      );
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
    runAfter: [HookName.WhitespaceFixer],
  }),
  [HookName.Svgo]: createLockableHook({
    action: sources =>
      run(
        "svgo",
        `--disable=${[
          "addAttributesToSVGElement",
          "addClassesToSVGElement",
          "cleanupEnableBackground",
          "cleanupIDs",
          "cleanupListOfValues",
          "cleanupNumericValues",
          "collapseGroups", // Can cause shape misalignment
          "convertColors",
          "convertEllipseToCircle",
          "convertPathData",
          "convertShapeToPath",
          "convertStyleToAttrs",
          "convertTransform",
          "inlineStyles",
          "mergePaths",
          "minifyStyles",
          "moveElemsAttrsToGroup",
          "moveGroupAttrsToElems",
          "prefixIds",
          "removeAttributesBySelector",
          "removeAttrs",
          "removeDesc",
          "removeDimensions",
          "removeDoctype",
          "removeEditorsNSData",
          "removeElementsByAttr",
          "removeEmptyAttrs",
          "removeEmptyContainers",
          "removeEmptyText",
          "removeHiddenElems",
          "removeMetadata",
          "removeNonInheritableGroupAttrs",
          "removeOffCanvasPaths",
          "removeRasterImages",
          "removeScriptElement",
          "removeStyleElement",
          "removeTitle",
          "removeUnknownsAndDefaults", // Can turn shapes black
          "removeUnusedNS",
          "removeUselessDefs", // Blows away SVG fonts
          "removeUselessStrokeAndFill",
          "removeViewBox",
          "removeXMLNS",
          "removeXMLProcInst",
          "reusePaths",
          "sortAttrs",
          "sortDefsChildren",
        ].join(",")}`,
        `--enable=${["cleanupAttrs", "removeComments"].join(",")}`,
        "--quiet",
        ...sources,
      ),
    include: /\.svg$/,
    runAfter: [HookName.WhitespaceFixer],
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
        sources.map(async source => {
          try {
            await run("/terraform", "fmt", "-write=true", source);
          } catch (ex) {
            await run("/terraform0.12", "fmt", "-write=true", source);
          }
        }),
      ),
    include: /\.tf$/,
    runAfter: [HookName.WhitespaceFixer],
  }),
  // Strip trailing whitespace, strip BOF newlines, require single EOF newline
  [HookName.WhitespaceFixer]: createLockableHook({
    action: sources =>
      Promise.all(
        sources.map(source =>
          transformFile(source, data => {
            const eol = /\r/.test(data) ? "\r\n" : "\n";
            return (
              data.replace(/[^\S\r\n]+$/gm, "").replace(/^[\r\n]+|\s+$/g, "") +
              eol
            );
          }),
        ),
      ),
    include: /./,
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

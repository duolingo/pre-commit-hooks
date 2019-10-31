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
  "--ignore-path",
  EMPTY_FILE,
  "--loglevel",
  "warn",
  "--no-config",
  "--no-editorconfig",
  "--write",
];

/** Runs a shell command, promising combined stdout and stderr */
const run = (command: string | string[]) =>
  new Promise<string>((resolve, reject) => {
    exec(
      typeof command === "string"
        ? command
        : command.map(arg => `'${arg}'`).join(" "),
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
  Black = "Black",
  GoogleJavaFormat = "google-java-format",
  Ktlint = "ktlint",
  PrettierJs = "Prettier (JS)",
  PrettierNonJs = "Prettier (non-JS)",
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
  /** Hooks that must complete before this one begins */
  dependsOn?: HookName[];
  /** Source files to exclude */
  exclude?: RegExp;
  /** Source files to include */
  include: RegExp;
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

/** Hooks expressed in a format similar to .pre-commit-config.yaml */
const HOOKS: Record<HookName, LockableHook> = {
  [HookName.Black]: createLockableHook({
    action: async (sources, args) => {
      const pythonVersionArgs = (args["python-version"] || "").startsWith("2")
        ? ["--fast", "--target-version", "py27"]
        : ["--target-version", "py36"];
      await run([
        "black",
        "--config",
        EMPTY_FILE,
        "--line-length",
        `${PYTHON_LINE_LENGTH}`,
        "--quiet",
        ...pythonVersionArgs,
        ...sources,
      ]);
    },
    dependsOn: [HookName.WhitespaceFixer],
    include: /\.py$/,
  }),
  [HookName.GoogleJavaFormat]: createLockableHook({
    action: sources =>
      run([
        "java",
        "-jar",
        "/google-java-format-1.7-all-deps.jar",
        "--replace",
        ...sources,
      ]),
    dependsOn: [HookName.WhitespaceFixer],
    include: /\.java$/,
  }),
  [HookName.Ktlint]: createLockableHook({
    action: async sources => {
      try {
        await run([
          "/ktlint",
          "--experimental", // Enables indentation formatting
          "--format",
          ...sources,
        ]);
      } catch (ex) {
        // ktlint just failed to autocorrect some stuff, e.g. long lines
      }
    },
    dependsOn: [HookName.WhitespaceFixer],
    include: /\.kt$/,
  }),
  [HookName.PrettierJs]: createLockableHook({
    action: sources =>
      run([
        "prettier",
        ...PRETTIER_OPTIONS,
        "--trailing-comma",
        "es5",
        ...sources,
      ]),
    dependsOn: [HookName.WhitespaceFixer],
    exclude: /\b(compressed|custom|min|minified|pack|prod|production)\b/,
    include: /\.js$/,
  }),
  [HookName.PrettierNonJs]: createLockableHook({
    action: sources =>
      run([
        "prettier",
        ...PRETTIER_OPTIONS,
        "--trailing-comma",
        "all",
        ...sources,
      ]),
    dependsOn: [HookName.WhitespaceFixer],
    include: /\.(html?|markdown|md|tsx?|ya?ml)$/,
  }),
  [HookName.Svgo]: createLockableHook({
    action: sources =>
      run([
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
      ]),
    dependsOn: [HookName.WhitespaceFixer],
    include: /\.svg$/,
  }),
  [HookName.TerraformFmt]: createLockableHook({
    action: async sources => {
      const dirs = Array.from(new Set(sources.map(source => dirname(source))));
      await Promise.all(
        dirs.map(dir => run(["terraform", "fmt", "-write=true", dir])),
      );
    },
    dependsOn: [HookName.WhitespaceFixer],
    include: /\.tf$/,
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
const GLOBAL_EXCLUDES = /(^|\/)(build|node_modules)\/|\.proto$/;

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
    if (hook.dependsOn) {
      hook.locksToWaitFor = Promise.all(
        hook.dependsOn.map(hookName => HOOKS[hookName].lock),
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

#!/usr/bin/env node

import { exec } from "child_process";
import { readFile, writeFile } from "fs";
import { dirname } from "path";

/** Maximum characters per line in Python */
const PYTHON_LINE_LENGTH = 100;

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
      if (err) {
        reject(err);
        return;
      }
      const after = transform(data);
      data === after || data === ""
        ? resolve()
        : writeFile(path, after, "utf8", err =>
            err ? reject(err) : resolve(),
          );
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
  WhitespaceTrimmer = "Whitespace trimmer",
}

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
  action: (sources: string[]) => Promise<unknown>;
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
    action: async sources => {
      // Detect Python 2 based on its syntax and common functions
      let pythonVersionArgs: string[];
      try {
        // Would just use `git grep -q` but it doesn't seem to exit early?!
        (await run(
          `git grep -E "^([^#]*[^#.]\\b(basestring|(iter(items|keys|values)|raw_input|unicode|xrange)\\()| *print ['\\"])" '*.py' | grep -qE .`,
        )).trim().length;
        pythonVersionArgs = ["--fast", "--target-version", "py27"];
      } catch (ex) {
        pythonVersionArgs = ["--target-version", "py36"];
      }

      await run([
        "black",
        "--line-length",
        `${PYTHON_LINE_LENGTH}`,
        "--quiet",
        ...pythonVersionArgs,
        ...sources,
      ]);
    },
    dependsOn: [HookName.WhitespaceTrimmer],
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
    dependsOn: [HookName.WhitespaceTrimmer],
    include: /\.java$/,
  }),
  [HookName.Ktlint]: createLockableHook({
    action: async sources => {
      try {
        return await run([
          "/ktlint",
          "--experimental", // Enables indentation formatting
          "--format",
          ...sources,
        ]);
      } catch (ex) {
        // ktlint just failed to autocorrect some stuff, e.g. long lines
        return ex;
      }
    },
    dependsOn: [HookName.WhitespaceTrimmer],
    include: /\.kt$/,
  }),
  [HookName.PrettierJs]: createLockableHook({
    action: sources =>
      run(["prettier", "--trailing-comma", "es5", "--write", ...sources]),
    dependsOn: [HookName.WhitespaceTrimmer],
    exclude: /\b(compressed|custom|min|minified|pack|prod|production)\b/,
    include: /\.js$/,
  }),
  [HookName.PrettierNonJs]: createLockableHook({
    action: sources =>
      run(["prettier", "--trailing-comma", "all", "--write", ...sources]),
    dependsOn: [HookName.WhitespaceTrimmer],
    include: /\.(markdown|md|tsx?|ya?ml)$/,
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
    dependsOn: [HookName.WhitespaceTrimmer],
    include: /\.svg$/,
  }),
  [HookName.TerraformFmt]: createLockableHook({
    action: async sources => {
      const dirs = Array.from(new Set(sources.map(source => dirname(source))));
      return (await Promise.all(
        dirs.map(dir => run(["terraform", "fmt", "-write=true", dir])),
      )).join("\n");
    },
    dependsOn: [HookName.WhitespaceTrimmer],
    include: /\.tf$/,
  }),
  [HookName.WhitespaceTrimmer]: createLockableHook({
    action: sources =>
      Promise.all(
        sources.map(source =>
          transformFile(
            source,
            data => data.replace(/\s+$/g, "").trim() + "\n",
          ),
        ),
      ),
    include: /./,
  }),
};

/** Files that match this pattern should never be processed */
const GLOBAL_EXCLUDES = /(^|\/)(build|node_modules)\//;

/** Prefixes a string to all nonempty lines of input */
const prefixLines = (() => {
  const maxPrefixLength = Math.max(
    ...Object.keys(HOOKS).map(name => name.length),
  );
  return (prefix: string, lines: string) =>
    lines
      .split("\n")
      .filter(line => line.trim().length)
      .map(line => `[${prefix}]`.padEnd(maxPrefixLength + 3) + line)
      .join("\n");
})();

(async () => {
  // Determine list of source files to process
  const sources = process.argv.slice(2); // Strips ['/usr/bin/node', '/entry']

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
            await action(includedSources);
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

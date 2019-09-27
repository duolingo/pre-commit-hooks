#!/usr/bin/env node

import { exec } from "child_process";
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

/** Hooks expressed in a format similar to .pre-commit-config.yaml */
const HOOKS: {
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
  /** Source files to exclude */
  exclude?: RegExp;
  /** Source files to include */
  include: RegExp;
  /** Human-readable tool name */
  name: string;
}[] = [
  {
    action: async sources => {
      // Detect Python 2 based on its syntax and common functions
      let pythonVersionArgs: string[];
      try {
        // Would just use `git grep -q` but it doesn't seem to exit early?!
        (await run(
          `git grep -E "^([^#]*[^#.]\\b(basestring|(iter(items|keys|values)|raw_input|unicode|xrange)\\()| *print[ '\\"])" '*.py' | grep -qE .`,
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
    include: /\.py$/,
    name: "Black",
  },
  {
    action: sources =>
      run([
        "java",
        "-jar",
        "/google-java-format-1.7-all-deps.jar",
        "--replace",
        ...sources,
      ]),
    include: /\.java$/,
    name: "google-java-format",
  },
  {
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
    include: /\.kt$/,
    name: "ktlint",
  },
  {
    action: sources =>
      run(["prettier", "--trailing-comma", "all", "--write", ...sources]),
    include: /\.(markdown|md|tsx?|ya?ml)$/,
    name: "Prettier",
  },
  {
    action: sources =>
      run(["prettier", "--trailing-comma", "es5", "--write", ...sources]),
    exclude: /\b(compressed|custom|min|minified|pack|prod|production)\b/,
    include: /\.js$/,
    name: "Prettier",
  },
  {
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
    include: /\.svg$/,
    name: "SVGO",
  },
  {
    action: async sources => {
      const dirs = Array.from(new Set(sources.map(source => dirname(source))));
      return (await Promise.all(
        dirs.map(dir => run(["terraform", "fmt", "-write=true", dir])),
      )).join("\n");
    },
    include: /\.tf$/,
    name: "terraform fmt",
  },
];

/** Files that match this pattern should never be processed */
const GLOBAL_EXCLUDES = /(^|\/)(build|node_modules)\//;

/** Prefixes a string to all nonempty lines of input */
const prefixLines = (() => {
  const maxPrefixLength = Math.max(...HOOKS.map(hook => hook.name.length));
  return (prefix: string, lines: string) =>
    lines
      .split("\n")
      .filter(line => line.trim().length)
      .map(line => `[${prefix}]`.padEnd(maxPrefixLength + 3) + line)
      .join("\n");
})();

// Run all hooks in parallel
(async () => {
  const sources = process.argv.slice(2); // Strips ['/usr/bin/node', '/entry']
  let success = true;
  await Promise.all(
    HOOKS.map(async ({ action, exclude, include, name }) => {
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
    }),
  );
  success || process.exit(1);
})();

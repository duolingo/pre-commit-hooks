const { defineConfig } = require("eslint/config");
const jsdoc = require("eslint-plugin-jsdoc");
const sortKeys = require("eslint-plugin-sort-keys");
const unicorn = require("eslint-plugin-unicorn");
const tseslint = require("typescript-eslint");

module.exports = defineConfig([
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: { parser: tseslint.parser },
    linterOptions: {
      // Individual repos may have their own additional ESLint setups that
      // enable more rules than we do here, which means that we can't reliably
      // determine which directives are actually unused
      reportUnusedDisableDirectives: "off",
    },
    // TODO: Add more plugins: react, react-hooks. Ideally we could also add
    // prefer-arrow, but it only autofixes single-line functions :/ Most
    // popular plugins: https://www.npmjs.com/search?q=keywords%3Aeslint-plugin
    plugins: {
      jsdoc,
      "sort-keys": sortKeys,
      "@typescript-eslint": tseslint.plugin,
      unicorn,
    },
    //
    // PLEASE READ BEFORE EDITING THESE RULES!
    //
    // We must keep these rules compatible with Duolingo's internal ESLint
    // config (it could be nice to someday update our internal config to
    // inherit from this one). Every rule that we enable here must be
    // autofixable and worth its performance cost, e.g. we should disable
    // complex rules that protect against rare problems in our codebase.
    //
    // Unless stated otherwise, we include disabled rules (commented out) in
    // this file to record that we're willfully disabling them, a practice that
    // simplifies future ESLint upgrades: we can more easily identify and
    // evaluate only newly available rules instead of needing to also revisit
    // existing rules that were omitted from this file.
    //
    // The rule declarations below are organized into sections based on the
    // plugins that provide them. These sections are sorted alphabetically by
    // plugin name.
    rules: {
      // Native ESLint rules. Get the list of autofixable rules by running the
      // snippet below in the browser console at
      // https://eslint.org/docs/latest/rules/
      //
      // copy([...$$("p.rule__categories__type:nth-child(3):not([aria-hidden=true])")].map(p=>p.closest("article.rule").querySelector("a.rule__name")?.textContent).filter(x=>x).sort().join("\n"))
      "arrow-body-style": ["error", "as-needed"],
      // "capitalized-comments": "error",
      curly: ["error", "all"],
      // "dot-notation": "error",
      eqeqeq: ["error", "always"],
      // "logical-assignment-operators": "error",
      // "no-div-regex": "error",
      "no-else-return": "error",
      // "no-extra-bind": "error",
      "no-extra-boolean-cast": ["error", { enforceForInnerExpressions: true }],
      "no-extra-label": "error",
      // "no-implicit-coercion": "error",
      "no-lonely-if": "error",
      "no-regex-spaces": "error",
      "no-undef-init": "error",
      "no-unneeded-ternary": ["error", { defaultAssignment: false }],
      "no-unused-labels": "error",
      "no-useless-computed-key": ["error", { enforceForClassMembers: true }],
      "no-useless-rename": "error",
      "no-useless-return": "error",
      "no-var": "error",
      "object-shorthand": ["error", "always"],
      "one-var": ["error", "never"],
      "operator-assignment": ["error", "always"],
      "prefer-arrow-callback": "error",
      "prefer-const": "error",
      // "prefer-destructuring": "error",
      "prefer-exponentiation-operator": "error",
      "prefer-numeric-literals": "error",
      // "prefer-object-has-own": "error",
      // "prefer-object-spread": "error",
      "prefer-template": "error",
      // This only sorts members within an individual import statement, not
      // import statements ("declarations") themselves. We disable that because
      // this rule sorts in a weird way: by first member rather than by module
      // name. The `import/order` rule provided by eslint-plugin-import does
      // sort declarations by module name, but we forgo that too because it
      // groups declarations based on environmental factors (e.g. node_modules,
      // Node version) that we can't easily determine or reproduce here in a
      // repo-agnostic way. One compromise might be to use `import/order` and
      // simply disable its regrouping feature in favor of whatever groups are
      // found in the source code to be formatted, but no such option exists :/
      "sort-imports": ["error", { ignoreDeclarationSort: true }],
      "sort-vars": "error",
      // "strict": "error",
      // "unicode-bom": "error",
      yoda: ["error", "never"],

      // JSDoc rules. All autofixable rules:
      // https://github.com/gajus/eslint-plugin-jsdoc/tree/main?tab=readme-ov-file#user-content-eslint-plugin-jsdoc-rules
      "jsdoc/check-alignment": "error",
      // "jsdoc/check-line-alignment": "error",
      "jsdoc/check-param-names": "error",
      "jsdoc/check-property-names": "error",
      "jsdoc/check-tag-names": "error",
      // "jsdoc/check-types": "error",
      "jsdoc/empty-tags": "error",
      // "jsdoc/match-name": "error",
      "jsdoc/multiline-blocks": [
        "error",
        {
          // This should be long enough to account for all but the most deeply
          // nested/indented JSDoc blocks while minimizing false negatives that
          // could fit on a single line without exceeding the line length limit
          minimumLengthForMultiline: 60,
          noMultilineBlocks: true,
        },
      ],
      // "jsdoc/no-bad-blocks": "error",
      // "jsdoc/no-blank-block-descriptions": "error",
      // "jsdoc/no-blank-blocks": "error",
      // "jsdoc/no-defaults": "error",
      // "jsdoc/no-multi-asterisks": "error", // Bug: fixer deletes Markdown bullets
      "jsdoc/no-types": "error",
      "jsdoc/require-asterisk-prefix": "error",
      // "jsdoc/require-description-complete-sentence": "error",
      // "jsdoc/require-example": "error",
      // "jsdoc/require-hyphen-before-param-description": "error",
      // "jsdoc/require-jsdoc": "error",
      // "jsdoc/require-param": "error",
      // "jsdoc/require-property": "error",
      // "jsdoc/tag-lines": "error",
      // "jsdoc/text-escaping": "error",

      // sort-keys rules. https://github.com/namnm/eslint-plugin-sort-keys
      "sort-keys/sort-keys-fix": "error",

      // typescript-eslint rules. Get the list of autofixable rules by running
      // the snippet below in the browser console at
      // https://typescript-eslint.io/rules/?=xdeprecated-fixable-xtypeInformation
      //
      // copy([...$$("table td:first-child a code")].map(c=>c.textContent).sort().join("\n"))
      "@typescript-eslint/array-type": ["error", { default: "array" }],
      "@typescript-eslint/ban-tslint-comment": "error",
      // "@typescript-eslint/consistent-generic-constructors": "error",
      "@typescript-eslint/consistent-indexed-object-style": ["error", "record"],
      "@typescript-eslint/consistent-type-assertions": [
        "error",
        {
          arrayLiteralTypeAssertions: "allow-as-parameter",
          assertionStyle: "as",
          objectLiteralTypeAssertions: "allow-as-parameter",
        },
      ],
      "@typescript-eslint/consistent-type-definitions": ["error", "interface"],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { disallowTypeAnnotations: false, prefer: "type-imports" },
      ],
      "@typescript-eslint/explicit-member-accessibility": [
        "error",
        {
          accessibility: "explicit",
          overrides: { accessors: "explicit", constructors: "explicit" },
        },
      ],
      // "@typescript-eslint/method-signature-style": "error",
      "@typescript-eslint/no-array-constructor": "error",
      // "@typescript-eslint/no-dynamic-delete": "error",
      // "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-extra-non-null-assertion": "error",
      // "@typescript-eslint/no-import-type-side-effects": "error",
      "@typescript-eslint/no-inferrable-types": "error",
      // "@typescript-eslint/no-restricted-types": "error",
      "@typescript-eslint/no-useless-empty-export": "error",
      // "@typescript-eslint/no-wrapper-object-types": "error",
      "@typescript-eslint/prefer-as-const": "error",
      "@typescript-eslint/prefer-function-type": "error",
      "@typescript-eslint/prefer-namespace-keyword": "error",

      // eslint-plugin-unicorn rules. https://github.com/sindresorhus/eslint-plugin-unicorn?tab=readme-ov-file#rules
      "unicorn/better-regex": ["error", { sortCharacterClasses: false }],
      "unicorn/catch-error-name": ["error", { name: "ex" }],
      "unicorn/consistent-destructuring": "error",
      "unicorn/consistent-empty-array-spread": "error",
      // "unicorn/consistent-existence-index-check": "error",
      // "unicorn/custom-error-definition": "error",
      // "unicorn/empty-brace-spaces": "error",
      "unicorn/escape-case": "error",
      // "unicorn/explicit-length-check": "error",
      // "unicorn/new-for-builtins": "error",
      // "unicorn/no-array-for-each": "error", // Bug: fixer deletes comments
      // "unicorn/no-array-method-this-argument": "error",
      // "unicorn/no-array-push-push": "error", // Bug: fixer deletes comments
      // "unicorn/no-await-expression-member": "error",
      "unicorn/no-console-spaces": "error",
      "unicorn/no-for-loop": "error",
      // "unicorn/no-hex-escape": "error",
      // "unicorn/no-lonely-if": "error", // Bug: Moves comments around
      "unicorn/no-negated-condition": "error",
      // "unicorn/no-nested-ternary": "error",
      // "unicorn/no-new-array": "error",
      "unicorn/no-new-buffer": "error",
      // "unicorn/no-null": "error",
      "unicorn/no-single-promise-in-promise-methods": "error",
      // "unicorn/no-static-only-class": "error",
      "unicorn/no-typeof-undefined": "error",
      // "unicorn/no-unnecessary-array-splice-count": "error",
      "unicorn/no-unnecessary-await": "error",
      "unicorn/no-unreadable-array-destructuring": "error",
      "unicorn/no-useless-fallback-in-spread": "error",
      // "unicorn/no-useless-length-check": "error",
      "unicorn/no-useless-promise-resolve-reject": "error",
      "unicorn/no-useless-spread": "error",
      "unicorn/no-useless-undefined": "error",
      "unicorn/no-zero-fractions": "error",
      "unicorn/number-literal-case": "error",
      // "unicorn/numeric-separators-style": "error",
      // "unicorn/prefer-add-event-listener": "error",
      "unicorn/prefer-array-find": "error",
      // "unicorn/prefer-array-flat": "error",
      "unicorn/prefer-array-flat-map": "error",
      "unicorn/prefer-array-index-of": "error",
      "unicorn/prefer-array-some": "error",
      // "unicorn/prefer-at": "error",
      "unicorn/prefer-date-now": "error",
      // "unicorn/prefer-default-parameters": "error",
      // "unicorn/prefer-dom-node-append": "error",
      "unicorn/prefer-dom-node-dataset": "error",
      // "unicorn/prefer-dom-node-remove": "error",
      "unicorn/prefer-export-from": "error",
      // "unicorn/prefer-global-this": "error",
      // "unicorn/prefer-import-meta-properties": "error",
      "unicorn/prefer-includes": "error",
      // "unicorn/prefer-json-parse-buffer": "error",
      // "unicorn/prefer-keyboard-event-key": "error",
      "unicorn/prefer-math-min-max": "error",
      // "unicorn/prefer-math-trunc": "error",
      // "unicorn/prefer-modern-dom-apis": "error",
      // "unicorn/prefer-modern-math-apis": "error",
      // "unicorn/prefer-module": "error",
      // "unicorn/prefer-native-coercion-functions": "error",
      "unicorn/prefer-negative-index": "error",
      // "unicorn/prefer-node-protocol": "error",
      // "unicorn/prefer-number-properties": "error",
      "unicorn/prefer-object-from-entries": "error",
      "unicorn/prefer-optional-catch-binding": "error",
      // "unicorn/prefer-prototype-methods": "error",
      "unicorn/prefer-query-selector": "error",
      // "unicorn/prefer-reflect-apply": "error",
      "unicorn/prefer-regexp-test": "error",
      // "unicorn/prefer-set-has": "error",
      "unicorn/prefer-set-size": "error",
      "unicorn/prefer-spread": "error",
      // "unicorn/prefer-string-raw": "error",
      // "unicorn/prefer-string-replace-all": "error",
      "unicorn/prefer-string-slice": "error",
      "unicorn/prefer-string-starts-ends-with": "error",
      "unicorn/prefer-string-trim-start-end": "error",
      // "unicorn/prefer-switch": "error",
      "unicorn/prefer-ternary": "error",
      // "unicorn/prefer-type-error": "error",
      // "unicorn/prevent-abbreviations": "error",
      // "unicorn/relative-url-style": "error",
      // "unicorn/require-array-join-separator": "error",
      // "unicorn/require-number-to-fixed-digits-argument": "error",
      // "unicorn/string-content": "error",
      // "unicorn/switch-case-braces": "error",
      // "unicorn/template-indent": "error",
      "unicorn/text-encoding-identifier-case": "error",
      // "unicorn/throw-new-error": "error",
    },
  },
]);

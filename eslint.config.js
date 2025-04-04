const { defineConfig } = require("eslint/config");
const jsdoc = require("eslint-plugin-jsdoc");
const tseslint = require("typescript-eslint");

module.exports = defineConfig([
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: { parser: tseslint.parser },
    // TODO: Add more plugins: react, react-hooks. Ideally we could also add
    // prefer-arrow, but it only autofixes single-line functions :/
    plugins: { jsdoc, "@typescript-eslint": tseslint.plugin },
    // To simplify ESLint adoption, we should only ever enable rules that are
    // autofixable! We should also keep these rules compatible with Duolingo's
    // internal ESLint config
    rules: {
      // Native ESLint rules. The list of autofixable rules can be determined by
      // running the snippet below in the browser console at
      // https://eslint.org/docs/latest/rules/. Here we explicitly include
      // disabled rules (commented out) to indicate that we're disabling them
      // on purpose. This simplifies ESLint upgrades: we can more easily
      // identify and evaluate only newly available rules instead of needing
      // to also revisit any existing rules that were omitted from this file.
      //
      // copy([...$$("p.rule__categories__type:nth-child(3):not([aria-hidden=true])")].map(p=>p.closest("article.rule").querySelector("a.rule__name")?.textContent).filter(x=>x).sort().join("\n"))
      "arrow-body-style": ["error", "as-needed"],
      // "capitalized-comments": "error",
      curly: ["error", "all"],
      // "dot-notation": "error",
      eqeqeq: ["error", "always"],
      // "logical-assignment-operators": "error",
      // "no-div-regex": "error",
      "no-else-return": ["error", { allowElseIf: false }],
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

      // typescript-eslint rules. As with the ESLint rules above, we explicitly
      // include disabled rules (commented out) for ease of maintenance. Run
      // the snippet below at https://typescript-eslint.io/rules/?=xdeprecated-fixable-xtypeInformation
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

      // JSDoc rules. As with the ESLint rules above, we explicitly include
      // disabled rules (commented out) for ease of maintenance.
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
      "jsdoc/no-multi-asterisks": "error",
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
    },
  },
]);

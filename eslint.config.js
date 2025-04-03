const { defineConfig } = require("eslint/config");
const importPlugin = require("eslint-plugin-import");
const tseslint = require("typescript-eslint");

module.exports = defineConfig([
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: { parser: tseslint.parser },
    plugins: { import: importPlugin, "@typescript-eslint": tseslint.plugin },
    // To simplify ESLint adoption, we should only ever enable rules that are
    // autofixable! We should also keep these rules compatible with Duolingo's
    // internal ESLint config
    rules: {
      // ESLint rules. The list of autofixable rules can be determined by
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
      "sort-imports": "error",
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

      // Plugin rules

      "import/order": [
        "error",
        {
          alphabetize: { caseInsensitive: false, order: "asc" },
          groups: [
            "builtin",
            "external",
            ["internal", "parent"],
            ["sibling", "index"],
          ],
          "newlines-between": "always",
        },
      ],
    },
  },
]);

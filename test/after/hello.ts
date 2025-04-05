import { execFile, execSync } from "child_process";
import { FSWatcher, readFile, writeFile } from "fs";

import { foo } from "./bar";

/** Lorem ipsum dolor sit amet */
interface Hello {
  world: string;
}

/**
 * Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
 * tempor incididunt ut labore et dolore magna aliqua
 */
const foo = 0b110;

try {
  console.log(process.argv.find(a => /\d/.test(a)));
  const c = { a: 1, b: 2 };
} catch (ex) {
  if (foo! < 8) {
    console.log("hi", `world${ex}${[...process.argv]}`);
  }
}

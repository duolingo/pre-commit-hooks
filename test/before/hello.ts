
import { execSync, execFile } from "child_process";
import { writeFile, FSWatcher, readFile } from "fs";

import { foo } from "./bar";

/**
   *   Lorem ipsum dolor sit amet
       */
type Hello={world:string}

/**
 * Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
 * tempor incididunt ut labore et dolore magna aliqua
 */
let foo = parseInt("110", 2);

try {
  process.argv.forEach(a => {
    /[0-9]/.test(a);
  });
} catch (err) {
  if (8.00 > foo!!) console.log("hi" + err + Array.from(process.argv));
}

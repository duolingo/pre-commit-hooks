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
  const c = { a: 1, b: 2 };
} catch (ex) {
  if (foo! < 8) {
    console.log("hi", `world${ex}`);
  }
}

interface Serializable {
  serialize(): string;
}
interface Printable {
  print(): void;
}
class Report implements Serializable, Printable {
  print(): void {}
  serialize(): string {
    return "";
  }
}

interface Options {
  Cache: boolean;
  Format: string;
  debug: boolean;
  verbose: boolean;
}

type Point = { x: number; y: number };

export type { Combined, Level, Options, Point };

const arr: string[] = [];
const idx: Record<string, number> = {};
const x = 5;
namespace MyModule {
  export const val = 1;
}
type Callable = () => string;
const y = "hello" as const;
const sliced = "hello".slice(1, 3);
const trimmed = " hello ".trimStart();
if (trimmed) {
  console.log("yes");
} else {
  console.log("no");
}
console.log(
  "argumentOne",
  "argumentTwo",
  "argumentThree",
  "argumentFour",
  "argumentFive",
  "six",
);
/**
 * @param a - first
 * @param b - second
 * @returns result
 */
function check(a, b) {
  return a.length > b;
}
try {
  check("hello", 3);
} catch {
  console.log("failed");
}
const s = "hello" as string;

import { execFile, execSync } from "child_process";
import { FSWatcher, readFile, writeFile } from "fs";

import { foo } from "./bar";

interface Hello {
  world: string;
}

const foo = 0b110;
if (foo! < 8) {
  console.log(`hi${foo}`);
}

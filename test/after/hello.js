const b = 0b111;
let a = 2 ** 3;
let undef;
const items = [1, 2, 3];
const obj = { a: 2, key: true, z: 1 };
const greeting = `hello ${a}`;
for (const item of items) {
  console.log(item);
}
items.map(x => x);
const fn = x => x;
if (a === 8) {
  a += b;
} else if (b) {
  a = b;
}
try {
  undef = fn(a);
} catch (ex) {
  console.log(ex);
}
if (!a) {
  console.log(obj, fn, undef, greeting);
}
const name = "test";
const o = {
  method() {
    if (a) {
      return true;
    }
    return false;
  },
  name,
};
console.log(o);
console.log(
  "argumentOne",
  "argumentTwo",
  "argumentThree",
  "argumentFour",
  "argumentFive",
  "six"
);
const ts = Date.now();
if (ts === undefined) {
  console.log(1, 2, 3);
}

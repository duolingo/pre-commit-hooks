const x = "world";
[1, 2].map(i => <span key={i}>Hello {x}</span>);
if (x === "world") {
  console.log(<span>Hello world</span>);
}

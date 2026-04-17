class Foo(val x: Int) {
  fun bar() {
    val a = emptyArray()
    val l = emptyList()
    val m = emptyMap()
    val q = emptySequence()
    val s = emptySet()
    println(a.size + l.size + m.size + q.count() + s.size + x)
  }
}

fun main() {
  println("Hello world")
}

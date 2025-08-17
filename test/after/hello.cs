using System;
using System.Collections.Generic;

namespace HelloWorld
{
  public class Program
  {
    public static void Main(string[] args)
    {
      Console.WriteLine("Hello, World!");
      var numbers = new List<int> { 1, 2, 3 };
      foreach (var number in numbers)
      {
        Console.WriteLine($"Number: {number}");
      }
    }
  }
}